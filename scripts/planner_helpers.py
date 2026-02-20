"""Compatibility shim — re-exports from luna_os."""
import os
env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from luna_os.store.postgres import PostgresBackend
from luna_os.planner import format_plan, build_plan_summary, Planner
from luna_os.timeline import steps_to_graph_data, generate_html, render_png

def get_store():
    return PostgresBackend()

def send_lark(chat_id, text):
    from lark_toolkit import LarkClient
    c = LarkClient()
    c.send_message(chat_id, text)

def send_lark_image(chat_id, png_path):
    from lark_toolkit import LarkClient
    c = LarkClient()
    image_key = c.upload_image(png_path)
    c.send_image(chat_id, image_key)

def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def _short_desc(text, max_len=60):
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:max_len] + "..." if len(text) > max_len else text

def generate_dependency_graph(steps, plan_id="", goal=""):
    """Compatibility wrapper for the old generate_dependency_graph function."""
    import tempfile
    step_data = []
    for i, s in enumerate(steps):
        if hasattr(s, 'to_dict'):
            d = s.to_dict()
        elif isinstance(s, dict):
            d = s
        else:
            d = {"step_num": i + 1, "title": str(s), "depends_on": [], "status": "pending"}
        step_data.append({
            "id": d.get("step_num", i + 1),
            "title": d.get("title", f"Step {i+1}"),
            "deps": d.get("depends_on") or [],
            "status": d.get("status", "pending"),
            "tid": d.get("task_id", ""),
        })
    html = generate_html(step_data, title=goal or "Plan Timeline")
    out_dir = tempfile.mkdtemp(prefix="planner-graph-")
    png_path = os.path.join(out_dir, "plan.png")
    try:
        return render_png(html, png_path)
    except Exception:
        return None

DRY_RUN = False
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
from datetime import timezone, timedelta
SGT = timezone(timedelta(hours=8))
