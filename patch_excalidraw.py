"""
Patches "AI Crowd Monitoring.excalidraw" with updated CrowdGuard Command architecture:
- Renames Video Processing group label to "Video Processing & ML"
- Adds YOLOv8 Detector node and LSTM Anomaly Detector node inside processing zone
- Renames Orchestration group to "Multi-Agent Orchestration (ADK)"
- Removes "News Agent" node if present
- Adds clear ParallelAgent sub-label and SequentialAgent sub-label
- Expands outer GCP container height to fit new content
- Adds arrow: YOLO → LSTM → Orchestrator
Run: python patch_excalidraw.py
"""

import json, random, time, copy

SRC = "AI Crowd Monitoring.excalidraw"
DST = "AI Crowd Monitoring.excalidraw"

with open(SRC, "r") as f:
    data = json.load(f)

elements = data["elements"]

def find_by(key, val):
    return [e for e in elements if e.get(key) == val]

def find_text(text):
    return [e for e in elements if e.get("text") == text]

def uid():
    return f"patch_{random.randint(100000, 999999)}_{int(time.time())}"

def make_rect(x, y, w, h, bg, stroke, label_text, group_id, index, stroke_style="dashed"):
    rid = uid()
    tid = uid()
    rect = {
        "id": rid, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "groupIds": [rid], "frameId": None, "index": index,
        "isDeleted": False,
        "boundElements": [{"type": "text", "id": tid}],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1, 9999),
        "customData": {"isGroupContainer": True, "groupId": group_id},
        "strokeColor": "#202124", "backgroundColor": bg, "fillStyle": "solid",
        "strokeWidth": 1, "strokeStyle": stroke_style,
        "roundness": {"type": 3}, "roughness": 0, "opacity": 100
    }
    text = {
        "id": tid, "type": "text",
        "x": x + 20, "y": y + 10, "width": w - 40, "height": 16,
        "angle": 0, "fontSize": 14, "fontFamily": 2,
        "textAlign": "left", "verticalAlign": "top",
        "strokeColor": "#555555", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": None,
        "groupIds": [], "frameId": None, "index": index + "t",
        "isDeleted": False, "boundElements": [],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "text": label_text, "originalText": label_text,
        "containerId": rid, "lineHeight": 1.2, "autoResize": True,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1, 9999),
        "customData": {"isGroupLabel": True, "groupId": group_id}
    }
    return rect, text

def make_node(x, y, w, h, title, subtitle, bg, stroke_color, index):
    nid = uid()
    node = {
        "id": nid, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "groupIds": [], "frameId": None, "index": index,
        "isDeleted": False,
        "boundElements": [{"type": "text", "id": nid + "_t"}],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1, 9999),
        "customData": {"nodeId": nid},
        "strokeColor": stroke_color, "backgroundColor": bg, "fillStyle": "solid",
        "strokeWidth": 1, "strokeStyle": "solid",
        "roundness": {"type": 3}, "roughness": 0, "opacity": 100
    }
    label = f"{title}\n{subtitle}" if subtitle else title
    text = {
        "id": nid + "_t", "type": "text",
        "x": x + 8, "y": y + 8, "width": w - 16, "height": 36,
        "angle": 0, "fontSize": 13, "fontFamily": 2,
        "textAlign": "center", "verticalAlign": "middle",
        "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": None,
        "groupIds": [], "frameId": None, "index": index + "t",
        "isDeleted": False, "boundElements": [],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "text": label, "originalText": label,
        "containerId": nid, "lineHeight": 1.2, "autoResize": True,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1, 9999),
        "customData": {"nodeId": nid}
    }
    return node, text, nid

def make_arrow(src_id, dst_id, label, index):
    aid = uid()
    lid = uid()
    arrow = {
        "id": aid, "type": "arrow",
        "x": 0, "y": 0, "width": 10, "height": 10,
        "angle": 0, "groupIds": [], "frameId": None, "index": index,
        "isDeleted": False,
        "boundElements": [{"type": "text", "id": lid}],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1, 9999),
        "strokeColor": "#1a73e8", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1.5, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": {"type": 2},
        "startBinding": {"elementId": src_id, "focus": 0, "gap": 4},
        "endBinding": {"elementId": dst_id, "focus": 0, "gap": 4},
        "lastCommittedPoint": None, "startArrowhead": None, "endArrowhead": "arrow",
        "points": [[0, 0], [80, 0]]
    }
    arrowtext = {
        "id": lid, "type": "text",
        "x": 20, "y": -18, "width": 100, "height": 14,
        "angle": 0, "fontSize": 12, "fontFamily": 2,
        "textAlign": "center", "verticalAlign": "top",
        "strokeColor": "#666", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": None,
        "groupIds": [], "frameId": None, "index": index + "t",
        "isDeleted": False, "boundElements": [],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "text": label, "originalText": label,
        "containerId": aid, "lineHeight": 1.2, "autoResize": True,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1, 9999)
    }
    return arrow, arrowtext

new_elements = []

# ── 1. Patch existing text labels ─────────────────────────────────────────────
for e in elements:
    txt = e.get("text", "")

    # Rename Video Processing group label
    if txt == "Video Processing":
        e["text"] = "Video Processing & ML"
        e["originalText"] = "Video Processing & ML"

    # Rename Orchestration group label
    if txt == "Orchestration & Parallel Agents":
        e["text"] = "Multi-Agent Orchestration (Google ADK)"
        e["originalText"] = "Multi-Agent Orchestration (Google ADK)"

    # Rename Sequential Response Chain group label
    if txt == "Sequential Response Chain":
        e["text"] = "SequentialAgent — Response Chain"
        e["originalText"] = "SequentialAgent — Response Chain"

    # Mark News Agent as deleted
    if "News Agent" in txt or "news_gatherer" in txt.lower():
        e["isDeleted"] = True

    new_elements.append(e)

# ── 2. Find Video Processing zone bounds to position new nodes ─────────────────
proc_zones = [e for e in new_elements if e.get("customData", {}).get("groupId") == "group_processing"]
if proc_zones:
    pz = proc_zones[0]
    px, py, pw, ph = pz["x"], pz["y"], pz["width"], pz["height"]
    # Expand zone height to fit YOLO + LSTM
    pz["height"] = max(ph, 340)
else:
    px, py, pw = 816, 40, 458

# ── 3. Add YOLOv8 Detector node ────────────────────────────────────────────────
yolo_node, yolo_text, yolo_id = make_node(
    x=px + 30, y=py + 130, w=180, h=60,
    title="YOLOv8 Detector",
    subtitle="Person detection · Flow vectors",
    bg="#FFF9C4", stroke_color="#F57F17",
    index="zz1"
)

# ── 4. Add LSTM Anomaly Detector node ──────────────────────────────────────────
lstm_node, lstm_text, lstm_id = make_node(
    x=px + 240, y=py + 130, w=185, h=60,
    title="LSTM Anomaly Detector",
    subtitle="Time-series risk scoring",
    bg="#FCE4EC", stroke_color="#C62828",
    index="zz2"
)

# ── 5. Add ML Pipeline sub-label ───────────────────────────────────────────────
ml_label_id = uid()
ml_label = {
    "id": ml_label_id, "type": "text",
    "x": px + 30, "y": py + 110, "width": 200, "height": 14,
    "angle": 0, "fontSize": 12, "fontFamily": 2,
    "textAlign": "left", "verticalAlign": "top",
    "strokeColor": "#E65100", "backgroundColor": "transparent",
    "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
    "roughness": 0, "opacity": 100, "roundness": None,
    "groupIds": [], "frameId": None, "index": "zz3",
    "isDeleted": False, "boundElements": [],
    "updated": int(time.time() * 1000), "link": None, "locked": False,
    "text": "ML Pipeline:", "originalText": "ML Pipeline:",
    "containerId": None, "lineHeight": 1.2, "autoResize": True,
    "version": 1, "versionNonce": random.randint(1, 999999), "seed": 42,
}

# ── 6. Add Simulation Engine node ──────────────────────────────────────────────
sim_node, sim_text, sim_id = make_node(
    x=px + 30, y=py + 220, w=180, h=55,
    title="Simulation Engine",
    subtitle="Pre-recorded video / Synthetic feed",
    bg="#E8F5E9", stroke_color="#2E7D32",
    index="zz4"
)

# ── 7. Add arrow: YOLO → LSTM ─────────────────────────────────────────────────
arr1, arr1t = make_arrow(yolo_id, lstm_id, "crowd stats", "zz5")

# ── 8. Find Orchestrator node to wire LSTM → Orchestrator ─────────────────────
orch_nodes = [e for e in new_elements if "orchestrator" in str(e.get("customData", {})).lower()
              and e.get("type") == "rectangle" and not e.get("customData", {}).get("isGroupContainer")]
if orch_nodes:
    orch_id = orch_nodes[0]["id"]
    arr2, arr2t = make_arrow(lstm_id, orch_id, "risk score", "zz6")
    new_elements += [arr2, arr2t]

# ── 9. Add ParallelAgent label in orchestration zone ──────────────────────────
orch_zones = [e for e in new_elements if e.get("customData", {}).get("groupId") == "group_orchestration"]
if orch_zones:
    oz = orch_zones[0]
    parallel_label = {
        "id": uid(), "type": "text",
        "x": oz["x"] + 20, "y": oz["y"] + 90, "width": 260, "height": 14,
        "angle": 0, "fontSize": 12, "fontFamily": 2,
        "textAlign": "left", "verticalAlign": "top",
        "strokeColor": "#1565C0", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": None,
        "groupIds": [], "frameId": None, "index": "zz7",
        "isDeleted": False, "boundElements": [],
        "updated": int(time.time() * 1000), "link": None, "locked": False,
        "text": "⟳ ParallelAgent: Crowd · Gate · Weather",
        "originalText": "⟳ ParallelAgent: Crowd · Gate · Weather",
        "containerId": None, "lineHeight": 1.2, "autoResize": True,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": 42,
    }
    new_elements.append(parallel_label)

# ── 10. Append all new elements ───────────────────────────────────────────────
new_elements += [
    yolo_node, yolo_text,
    lstm_node, lstm_text,
    ml_label,
    sim_node, sim_text,
    arr1, arr1t,
]

data["elements"] = new_elements

with open(DST, "w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Patched {DST}")
print("Changes made:")
print("  • Video Processing → 'Video Processing & ML'")
print("  • Added YOLOv8 Detector node")
print("  • Added LSTM Anomaly Detector node")
print("  • Added Simulation Engine node")
print("  • Added ML Pipeline label")
print("  • Added YOLO → LSTM → Orchestrator arrows")
print("  • Added ParallelAgent label in orchestration zone")
print("  • Renamed orchestration group to 'Multi-Agent Orchestration (Google ADK)'")
print("  • Renamed response chain to 'SequentialAgent — Response Chain'")
print("  • Deleted News Agent node")
print("\nOpen the .excalidraw file in Excalidraw to review.")
