"""
CrowdGuard Command — Video Processor Service
FastAPI service that accepts video uploads, runs YOLOv8 person detection,
computes optical flow, and writes aggregated crowd stats to GCS.
"""

import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from crowd_stats import aggregate_crowd_stats, CrowdStatsSchema
from flow_vectors import compute_optical_flow
from yolo_analyzer import YoloAnalyzer

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CrowdGuard — Video Processor",
    description="YOLOv8-based crowd detection and flow analysis for stadium video feeds",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

yolo = YoloAnalyzer(model_size=os.getenv("YOLO_MODEL_SIZE", "yolov8n"))


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "crowdguard-video-processor", "timestamp": datetime.utcnow().isoformat()}


@app.post("/analyze/frame")
async def analyze_frame(
    file: UploadFile = File(...),
    zone_id: str = Form("unknown"),
    camera_id: str = Form("cam_01"),
    phase: str = Form("mid_match"),
):
    """
    Accepts a single JPEG/PNG frame from a stadium camera.
    Runs YOLOv8 detection and returns person count + bounding boxes per zone.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")

    tmp_path = None
    try:
        suffix = ".jpg" if "jpeg" in file.content_type else ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        detection_result = yolo.detect_persons(tmp_path, zone_id=zone_id)
        stats = aggregate_crowd_stats(
            detections=detection_result,
            zone_id=zone_id,
            camera_id=camera_id,
            phase=phase,
        )

        # Write to GCS asynchronously
        _write_stats_to_gcs(stats, zone_id)

        return {
            "success": True,
            "zone_id": zone_id,
            "camera_id": camera_id,
            "person_count": detection_result["person_count"],
            "bounding_boxes": detection_result["bounding_boxes"],
            "crowd_stats": stats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Frame analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/analyze/video")
async def analyze_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    zone_id: str = Form("unknown"),
    phase: str = Form("mid_match"),
    sample_interval_sec: float = Form(2.0),
):
    """
    Accepts a video file (MP4/AVI). Processes it in the background,
    sampling frames every `sample_interval_sec` seconds.
    Returns a job_id to poll for results.
    """
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video files are accepted")

    job_id = str(uuid.uuid4())[:8]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    background_tasks.add_task(
        _process_video_background,
        job_id=job_id,
        video_path=tmp_path,
        zone_id=zone_id,
        phase=phase,
        sample_interval_sec=sample_interval_sec,
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"Video queued for analysis — poll /jobs/{job_id} for results",
    }


# In-memory job store (use Redis in production)
_job_results = {}


@app.get("/jobs/{job_id}")
async def get_job_result(job_id: str):
    """Poll for background video processing results."""
    if job_id not in _job_results:
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "status": "processing", "progress": "unknown"},
        )
    return _job_results[job_id]


@app.get("/zones/{zone_id}/latest")
async def get_zone_latest(zone_id: str):
    """Return the most recently processed crowd stats for a zone."""
    from tools_helpers import read_latest_stats

    stats = read_latest_stats(zone_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"No stats found for zone {zone_id}")
    return stats


def _write_stats_to_gcs(stats: dict, zone_id: str) -> None:
    """Write crowd stats JSON to GCS blob path crowd_stats/{zone_id}/latest.json."""
    import json

    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"crowd_stats/{zone_id}/latest.json")
        blob.upload_from_string(json.dumps(stats, indent=2), content_type="application/json")
        logger.info(f"Stats written to gs://{bucket_name}/crowd_stats/{zone_id}/latest.json")
    except Exception as e:
        logger.warning(f"GCS write failed: {e}")


async def _process_video_background(
    job_id: str,
    video_path: str,
    zone_id: str,
    phase: str,
    sample_interval_sec: float,
) -> None:
    """Background task: process a video file frame by frame."""
    import cv2

    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = int(fps * sample_interval_sec)

        all_stats = []
        frame_idx = 0
        prev_frame = None

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                tmp_frame_path = f"/tmp/crowdguard_frame_{job_id}_{frame_idx}.jpg"
                cv2.imwrite(tmp_frame_path, frame)

                detection = yolo.detect_persons(tmp_frame_path, zone_id=zone_id)
                flow = None
                if prev_frame is not None:
                    flow = compute_optical_flow(prev_frame, frame)

                stats = aggregate_crowd_stats(
                    detections=detection,
                    zone_id=zone_id,
                    camera_id=f"video_{job_id}",
                    phase=phase,
                    flow_data=flow,
                )
                all_stats.append(stats)

                if os.path.exists(tmp_frame_path):
                    os.unlink(tmp_frame_path)

                prev_frame = frame

            frame_idx += 1

        cap.release()
        os.unlink(video_path)

        _job_results[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "zone_id": zone_id,
            "frames_processed": len(all_stats),
            "summary": all_stats[-1] if all_stats else {},
            "timeline": all_stats,
        }

    except Exception as e:
        logger.error(f"Video processing job {job_id} failed: {e}", exc_info=True)
        _job_results[job_id] = {"job_id": job_id, "status": "failed", "error": str(e)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
