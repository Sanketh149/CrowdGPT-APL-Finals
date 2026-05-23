"""
Fixes the patched excalidraw file:
1. Removes all broken patch_ elements (bad indices, broken arrows)
2. Re-applies only safe changes: text renames + rectangle+text nodes with valid indices
3. No arrows added (too complex to generate valid bindings without exact coords)
"""
import json, random, time, copy

SRC = "AI Crowd Monitoring.excalidraw"

with open(SRC) as f:
    data = json.load(f)

elements = data["elements"]

# ── Step 1: Remove all broken patch_ elements ─────────────────────────────────
elements = [e for e in elements if not str(e.get("id", "")).startswith("patch_")]

# ── Step 2: Generate valid sequential indices after last existing one ──────────
# Excalidraw uses base-36 fractional indices like "a0", "b14", etc.
# We'll append after "b14" → "b15", "b16", etc.
def next_index(last: str, offset: int) -> str:
    # Parse last index as base36 integer, add offset, re-encode
    val = int(last, 36) + offset
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    while val > 0:
        result = chars[val % 36] + result
        val //= 36
    return result or "0"

last_idx = "b14"
idx_counter = [0]

def new_idx():
    idx_counter[0] += 1
    return next_index(last_idx, idx_counter[0])

def uid(suffix=""):
    return f"cgc_{random.randint(100000,999999)}{suffix}"

ts = int(time.time() * 1000)

# ── Step 3: Text renames on existing elements ──────────────────────────────────
for e in elements:
    txt = e.get("text", "")
    if txt == "Video Processing":
        e["text"] = "Video Processing & ML"
        e["originalText"] = "Video Processing & ML"
    if txt == "Orchestration & Parallel Agents":
        e["text"] = "Multi-Agent Orchestration (Google ADK)"
        e["originalText"] = "Multi-Agent Orchestration (Google ADK)"
    if txt == "Sequential Response Chain":
        e["text"] = "SequentialAgent — Response Chain"
        e["originalText"] = "SequentialAgent — Response Chain"
    if "News Agent" in txt or "news_gatherer" in txt.lower() or "News Gatherer" in txt:
        e["isDeleted"] = True

# ── Step 4: Find Video Processing zone to position new nodes ──────────────────
proc_zone = next((e for e in elements
                  if e.get("customData", {}).get("groupId") == "group_processing"
                  and e.get("type") == "rectangle"
                  and e.get("customData", {}).get("isGroupContainer")), None)

if proc_zone:
    px, py = proc_zone["x"], proc_zone["y"]
    # Expand zone to fit new nodes
    proc_zone["height"] = max(proc_zone.get("height", 212), 360)
    proc_zone["width"] = max(proc_zone.get("width", 458), 500)
else:
    px, py = 816, 40

def make_node_pair(x, y, w, h, title, subtitle, bg, stroke, idx_r, idx_t):
    rid = uid("_r")
    tid = uid("_t")
    rect = {
        "id": rid, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "groupIds": [], "frameId": None, "index": idx_r,
        "isDeleted": False,
        "boundElements": [{"id": tid, "type": "text"}],
        "updated": ts, "link": None, "locked": False,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1000, 9999),
        "customData": {"nodeId": rid},
        "strokeColor": stroke, "backgroundColor": bg, "fillStyle": "solid",
        "strokeWidth": 1.5, "strokeStyle": "solid",
        "roundness": {"type": 3}, "roughness": 0, "opacity": 100
    }
    label = f"{title}\n{subtitle}"
    text = {
        "id": tid, "type": "text",
        "x": x + 8, "y": y + 6, "width": w - 16, "height": 40,
        "angle": 0, "fontSize": 12, "fontFamily": 2,
        "textAlign": "center", "verticalAlign": "middle",
        "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": None,
        "groupIds": [], "frameId": None, "index": idx_t,
        "isDeleted": False, "boundElements": [],
        "updated": ts, "link": None, "locked": False,
        "text": label, "originalText": label,
        "containerId": rid, "lineHeight": 1.25, "autoResize": True,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1000, 9999),
        "customData": {"nodeId": rid}
    }
    return rect, text

def make_label(x, y, w, text_str, color, idx):
    eid = uid("_lbl")
    return {
        "id": eid, "type": "text",
        "x": x, "y": y, "width": w, "height": 14,
        "angle": 0, "fontSize": 12, "fontFamily": 2,
        "textAlign": "left", "verticalAlign": "top",
        "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "roundness": None,
        "groupIds": [], "frameId": None, "index": idx,
        "isDeleted": False, "boundElements": [],
        "updated": ts, "link": None, "locked": False,
        "text": text_str, "originalText": text_str,
        "containerId": None, "lineHeight": 1.2, "autoResize": True,
        "version": 1, "versionNonce": random.randint(1, 999999), "seed": random.randint(1000, 9999)
    }

new_nodes = []

# YOLOv8 node
r, t = make_node_pair(
    x=px + 20, y=py + 140, w=175, h=56,
    title="YOLOv8 Detector",
    subtitle="Person detection · Flow vectors",
    bg="#FFFDE7", stroke="#F57F17",
    idx_r=new_idx(), idx_t=new_idx()
)
new_nodes += [r, t]

# LSTM node
r, t = make_node_pair(
    x=px + 210, y=py + 140, w=185, h=56,
    title="LSTM Anomaly Detector",
    subtitle="Time-series risk scoring (30-frame)",
    bg="#FCE4EC", stroke="#C62828",
    idx_r=new_idx(), idx_t=new_idx()
)
new_nodes += [r, t]

# Simulation Engine node
r, t = make_node_pair(
    x=px + 20, y=py + 215, w=175, h=56,
    title="Simulation Engine",
    subtitle="Video loop / Synthetic feed",
    bg="#E8F5E9", stroke="#2E7D32",
    idx_r=new_idx(), idx_t=new_idx()
)
new_nodes += [r, t]

# "ML Pipeline:" sub-label
new_nodes.append(make_label(px + 20, py + 124, 200, "ML Pipeline ↓", "#E65100", new_idx()))

# ParallelAgent label in orchestration zone
orch_zone = next((e for e in elements
                  if e.get("customData", {}).get("groupId") == "group_orchestration"
                  and e.get("type") == "rectangle"
                  and e.get("customData", {}).get("isGroupContainer")), None)
if orch_zone:
    ox, oy = orch_zone["x"], orch_zone["y"]
    new_nodes.append(make_label(ox + 20, oy + 88, 300,
        "⟳ ParallelAgent: Crowd Density · Gate Sensor · Weather",
        "#1565C0", new_idx()))
    new_nodes.append(make_label(ox + 20, oy + 108, 300,
        "→ SequentialAgent: Route → Threat → Emergency → Notify",
        "#C62828", new_idx()))

elements += new_nodes
data["elements"] = elements

with open(SRC, "w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Fixed {SRC}")
print(f"   Removed all broken patch_ elements")
print(f"   Applied text renames")
print(f"   Added {len(new_nodes)} new elements with valid indices")
print(f"   No arrows (safe) — YOLO→LSTM→Orchestrator flow shown as labels")
