package swiftdeploy.canary

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Entry point – always return a structured decision object, never a bare bool
# ---------------------------------------------------------------------------
decision := {
    "allow":      allow,
    "violations": violations,
    "domain":     "canary",
    "checked_at": input.checked_at,
} if {
    true  # unconditional – always produce the object
}

# ---------------------------------------------------------------------------
# Allow only when there are no violations
# ---------------------------------------------------------------------------
allow if count(violations) == 0

# ---------------------------------------------------------------------------
# Collect all violations
# ---------------------------------------------------------------------------
violations := {msg | some msg in violation_messages}

# ---------------------------------------------------------------------------
# Individual violation rules
# ---------------------------------------------------------------------------
violation_messages[msg] if {
    error_rate_pct > input.thresholds.max_error_rate_pct
    msg := sprintf(
        "Error rate %.2f%% exceeds maximum %.2f%%",
        [error_rate_pct, input.thresholds.max_error_rate_pct],
    )
}

violation_messages[msg] if {
    p99_latency_ms > input.thresholds.max_p99_latency_ms
    msg := sprintf(
        "P99 latency %.1f ms exceeds maximum %.1f ms",
        [p99_latency_ms, input.thresholds.max_p99_latency_ms],
    )
}

violation_messages[msg] if {
    input.metrics.sample_count < 10
    msg := sprintf(
        "Insufficient samples (%d) – need at least 10 before promoting",
        [input.metrics.sample_count],
    )
}

# ---------------------------------------------------------------------------
# Helpers – extract metrics from input
# ---------------------------------------------------------------------------
error_rate_pct := input.metrics.error_rate_pct
p99_latency_ms := input.metrics.p99_latency_ms

