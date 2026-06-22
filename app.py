"""
FE Demo — Web chat cho Vinmec ReAct Agent (Flask).

Chạy:
    python app.py
Mở: http://127.0.0.1:5000
Provider lấy từ .env (DEFAULT_PROVIDER). Cần đặt DEFAULT_PROVIDER=google + GEMINI_API_KEY.
"""

import os
import re
import sys
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import get_provider
from src.agent.agent import ReActAgent
from src.tools.vinmec_tools import (TOOLS, emergency_info, maps_directions_url,
                                    nearest_vinmec_info, set_location_override)
from src.telemetry.metrics import tracker
from src.telemetry.logger import logger

ERROR_MESSAGE = "Hiện tại hệ thống đang lỗi, bạn thử lại sau nhé 🙏"

# ---- Chống spam (rate limit theo IP) ----
MIN_INTERVAL_SEC = 2      # tối thiểu 2 giây giữa 2 tin nhắn
MAX_PER_MINUTE = 15       # tối đa 15 tin nhắn / phút
MAX_MESSAGE_LEN = 500     # độ dài tối đa 1 tin nhắn
_req_log = defaultdict(deque)   # ip -> deque[timestamp]


def _rate_limited(ip: str):
    """Trả về thông báo nếu IP vượt giới hạn, ngược lại None."""
    now = time.time()
    dq = _req_log[ip]
    while dq and now - dq[0] > 60:   # bỏ timestamp cũ hơn 60s
        dq.popleft()
    if dq and now - dq[-1] < MIN_INTERVAL_SEC:
        return "Bạn gửi hơi nhanh, vui lòng chờ vài giây rồi thử lại nhé 🙏"
    if len(dq) >= MAX_PER_MINUTE:
        return "Bạn đã gửi quá nhiều yêu cầu trong 1 phút. Vui lòng nghỉ một lát rồi quay lại nhé 🙏"
    dq.append(now)
    return None

load_dotenv()

app = Flask(__name__)
llm = get_provider()
agent = ReActAgent(llm, TOOLS, max_steps=8)


@app.route("/")
def index():
    tool_names = [t["name"] for t in TOOLS]
    return render_template("index.html", model=llm.model_name, tools=tool_names)


def _origin_from_trace(trace):
    """Lấy toạ độ người dùng từ trace (get_current_location / find_nearest / get_emergency_contact)."""
    origin = None
    for s in trace:
        act = s.get("action") or ""
        obs = s.get("observation") or ""
        if act.startswith("get_current_location"):
            m = re.search(r"lat=([\d.\-]+),\s*lon=([\d.\-]+)", obs)
            if m:
                origin = (float(m.group(1)), float(m.group(2)))
        elif act.startswith(("find_nearest_vinmec", "get_emergency_contact")):
            m = re.search(r"lat\s*=\s*([\d.\-]+).*?lon\s*=\s*([\d.\-]+)", act)
            if m:
                origin = (float(m.group(1)), float(m.group(2)))
    return origin


def _build_map_info(trace, fallback_origin=None):
    """Nếu agent đã định vị người dùng, dựng link Google Maps chỉ đường tới Vinmec gần nhất."""
    origin = _origin_from_trace(trace) or fallback_origin
    if not origin:
        return None
    fac, dist = nearest_vinmec_info(*origin)
    return {
        "label": fac["name"],
        "address": fac["address"],
        "distance_km": round(dist, 1),
        "url": maps_directions_url(origin[0], origin[1], f"{fac['name']}, {fac['address']}"),
    }


def _build_emergency_info(trace, fallback_origin=None):
    """Nếu agent đã gọi get_emergency_contact / get_first_aid, trả thông tin cấp cứu + sơ cứu cho FE."""
    actions = [(s.get("action") or "") for s in trace]
    if not any(a.startswith(("get_emergency_contact", "get_first_aid")) for a in actions):
        return None
    origin = _origin_from_trace(trace) or fallback_origin
    info = emergency_info(*origin) if origin else emergency_info()
    # Lấy các bước sơ cứu (verbatim) từ observation của get_first_aid
    for s in trace:
        if (s.get("action") or "").startswith("get_first_aid") and s.get("observation"):
            steps = [ln.lstrip("• ").strip() for ln in s["observation"].splitlines()
                     if ln.strip().startswith("•")]
            if steps:
                info["first_aid"] = steps
            break
    return info


@app.route("/api/reset", methods=["POST"])
def reset():
    agent.reset()
    return jsonify({"ok": True})


@app.route("/api/chat", methods=["POST"])
def chat():
    # Chống spam: giới hạn tần suất theo IP
    ip = request.remote_addr or "unknown"
    limited = _rate_limited(ip)
    if limited:
        return jsonify({"error": limited}), 429

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Tin nhắn trống"}), 400
    if len(message) > MAX_MESSAGE_LEN:
        return jsonify({"error": f"Tin nhắn quá dài (tối đa {MAX_MESSAGE_LEN} ký tự)."}), 400

    # Toạ độ GPS chính xác do trình duyệt gửi lên (nếu người dùng cho phép)
    lat, lon = data.get("lat"), data.get("lon")
    set_location_override(lat, lon)

    before = len(tracker.session_metrics)
    try:
        answer = agent.run(message)
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        return jsonify({"error": ERROR_MESSAGE}), 200
    finally:
        set_location_override(None, None)  # xóa override sau mỗi request
    new_metrics = tracker.session_metrics[before:]

    # Toạ độ request làm fallback (vd cấp cứu: agent không gọi get_current_location)
    fb_origin = None
    try:
        if lat is not None and lon is not None:
            fb_origin = (float(lat), float(lon))
    except (TypeError, ValueError):
        fb_origin = None

    return jsonify({
        "answer": answer,
        "trace": agent.last_trace,
        "map": _build_map_info(agent.last_trace, fb_origin),
        "emergency": _build_emergency_info(agent.last_trace, fb_origin),
        "metrics": {
            "steps": len(new_metrics),
            "tokens": sum(m["total_tokens"] for m in new_metrics),
            "latency_ms": sum(m["latency_ms"] for m in new_metrics),
            "cost": round(sum(m["cost_estimate"] for m in new_metrics), 4),
        },
    })


if __name__ == "__main__":
    print(f"\n>>> Vinmec Agent Demo | model: {llm.model_name}")
    print(">>> Mở http://127.0.0.1:5000\n")
    # extra_files: reload cả khi sửa data JSON (mặc định reloader chỉ theo dõi .py)
    data_json = os.path.join("src", "tools", "vinmec_data.json")
    app.run(debug=True, port=5000, extra_files=[data_json])
