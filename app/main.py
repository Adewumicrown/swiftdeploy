import os
import time
import random
import threading
from flask import Flask, request, jsonify, g

app = Flask(__name__)

# ── Runtime config ────────────────────────────────────────────────────────────
MODE        = os.environ.get("MODE", "stable")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT    = int(os.environ.get("APP_PORT", 3000))
START_TIME  = time.time()

# ── Chaos state (canary only) ─────────────────────────────────────────────────
chaos_lock  = threading.Lock()
chaos_state = {"mode": None, "duration": 0, "rate": 0.0}


def is_canary() -> bool:
    return MODE == "canary"


def apply_chaos_headers(response):
    """Attach X-Mode header on every response when running in canary mode."""
    if is_canary():
        response.headers["X-Mode"] = "canary"
    return response


@app.after_request
def after_request(response):
    return apply_chaos_headers(response)


# ── Chaos middleware ──────────────────────────────────────────────────────────
@app.before_request
def check_chaos():
    """Apply active chaos effects before handling the real request."""
    if not is_canary():
        return

    with chaos_lock:
        state = dict(chaos_state)

    if state["mode"] == "slow":
        time.sleep(state["duration"])

    elif state["mode"] == "error":
        if random.random() < state["rate"]:
            resp = jsonify({"error": "chaos-induced server error", "mode": "error"})
            resp.status_code = 500
            return resp


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": f"Welcome to SwiftDeploy API — running in {MODE} mode",
        "mode":    MODE,
        "version": APP_VERSION,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({
        "status": "ok",
        "mode":   MODE,
        "uptime": round(time.time() - START_TIME, 2),
    })


@app.route("/chaos", methods=["POST"])
def chaos():
    if not is_canary():
        return jsonify({"error": "chaos endpoint only available in canary mode"}), 403

    body = request.get_json(silent=True) or {}
    mode = body.get("mode")

    if mode == "slow":
        duration = int(body.get("duration", 1))
        with chaos_lock:
            chaos_state.update({"mode": "slow", "duration": duration, "rate": 0.0})
        return jsonify({"chaos": "slow", "duration": duration})

    elif mode == "error":
        rate = float(body.get("rate", 0.5))
        with chaos_lock:
            chaos_state.update({"mode": "error", "duration": 0, "rate": rate})
        return jsonify({"chaos": "error", "rate": rate})

    elif mode == "recover":
        with chaos_lock:
            chaos_state.update({"mode": None, "duration": 0, "rate": 0.0})
        return jsonify({"chaos": "recovered"})

    else:
        return jsonify({"error": "unknown chaos mode", "valid_modes": ["slow", "error", "recover"]}), 400


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[swiftdeploy] Starting API service  mode={MODE}  version={APP_VERSION}  port={APP_PORT}")
    app.run(host="0.0.0.0", port=APP_PORT)
