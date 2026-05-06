import os
import time
import random
import threading
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# ── Runtime config ────────────────────────────────────────────────────────────
MODE        = os.environ.get("MODE", "stable")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT    = int(os.environ.get("APP_PORT", 3000))
START_TIME  = time.time()

# ── Chaos state ───────────────────────────────────────────────────────────────
chaos_lock  = threading.Lock()
chaos_state = {"mode": None, "duration": 0, "rate": 0.0}

# ── Metrics state ─────────────────────────────────────────────────────────────
metrics_lock = threading.Lock()

# http_requests_total{method, path, status_code}
request_counts = {}

# http_request_duration_seconds histogram buckets
BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
duration_buckets = {}   # key=(method,path) → list of counts per bucket
duration_sum     = {}   # key=(method,path) → total seconds
duration_count   = {}   # key=(method,path) → total requests


def record_request(method, path, status_code, duration):
    key      = (method, path, str(status_code))
    hist_key = (method, path)
    with metrics_lock:
        request_counts[key] = request_counts.get(key, 0) + 1
        if hist_key not in duration_buckets:
            duration_buckets[hist_key] = [0] * len(BUCKETS)
            duration_sum[hist_key]     = 0.0
            duration_count[hist_key]   = 0
        for i, b in enumerate(BUCKETS):
            if duration <= b:
                duration_buckets[hist_key][i] += 1
        duration_sum[hist_key]   += duration
        duration_count[hist_key] += 1


def is_canary():
    return MODE == "canary"


def chaos_active_value():
    with chaos_lock:
        m = chaos_state["mode"]
    if m == "slow":  return 1
    if m == "error": return 2
    return 0


# ── Middleware ────────────────────────────────────────────────────────────────
@app.before_request
def before():
    request._start_time = time.time()
    if request.path == "/metrics":
        return
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


@app.after_request
def after(response):
    if is_canary():
        response.headers["X-Mode"] = "canary"
    # record metrics (skip /metrics itself to avoid noise)
    if request.path != "/metrics":
        duration = time.time() - getattr(request, "_start_time", time.time())
        record_request(request.method, request.path, response.status_code, duration)
    return response


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


@app.route("/metrics", methods=["GET"])
def metrics():
    lines = []
    uptime = time.time() - START_TIME
    mode_val = 1 if is_canary() else 0

    # app_uptime_seconds
    lines.append("# HELP app_uptime_seconds Total uptime of the application in seconds")
    lines.append("# TYPE app_uptime_seconds gauge")
    lines.append(f"app_uptime_seconds {uptime:.2f}")

    # app_mode
    lines.append("# HELP app_mode Current deployment mode (0=stable, 1=canary)")
    lines.append("# TYPE app_mode gauge")
    lines.append(f"app_mode {mode_val}")

    # chaos_active
    lines.append("# HELP chaos_active Current chaos state (0=none, 1=slow, 2=error)")
    lines.append("# TYPE chaos_active gauge")
    lines.append(f"chaos_active {chaos_active_value()}")

    # http_requests_total
    lines.append("# HELP http_requests_total Total HTTP requests by method, path, status_code")
    lines.append("# TYPE http_requests_total counter")
    with metrics_lock:
        for (method, path, status_code), count in request_counts.items():
            lines.append(f'http_requests_total{{method="{method}",path="{path}",status_code="{status_code}"}} {count}')

    # http_request_duration_seconds histogram
    lines.append("# HELP http_request_duration_seconds Request duration in seconds")
    lines.append("# TYPE http_request_duration_seconds histogram")
    with metrics_lock:
        for (method, path), counts in duration_buckets.items():
            cumulative = 0
            for i, b in enumerate(BUCKETS):
                cumulative += counts[i]
                lines.append(f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{b}"}} {cumulative}')
            lines.append(f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {duration_count[(method,path)]}')
            lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {duration_sum[(method,path)]:.6f}')
            lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {duration_count[(method,path)]}')

    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[swiftdeploy] Starting API  mode={MODE}  version={APP_VERSION}  port={APP_PORT}")
    app.run(host="0.0.0.0", port=APP_PORT)
