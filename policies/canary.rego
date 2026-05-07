package swiftdeploy.canary

decision := {
    "allow":      allow,
    "violations": violations,
    "domain":     "canary",
    "checked_at": input.checked_at,
}

allow := count(violations) == 0

violations := [msg | some msg in violation_messages]

violation_messages contains msg if {
    input.metrics.error_rate_pct > input.thresholds.max_error_rate_pct
    msg := sprintf("Error rate %.2f%% exceeds maximum %.2f%%",
        [input.metrics.error_rate_pct, input.thresholds.max_error_rate_pct])
}

violation_messages contains msg if {
    input.metrics.p99_latency_ms > input.thresholds.max_p99_latency_ms
    msg := sprintf("P99 latency %.1f ms exceeds maximum %.1f ms",
        [input.metrics.p99_latency_ms, input.thresholds.max_p99_latency_ms])
}

violation_messages contains msg if {
    input.metrics.sample_count < 10
    msg := sprintf("Insufficient samples (%d) - need at least 10 before promoting",
        [input.metrics.sample_count])
}
