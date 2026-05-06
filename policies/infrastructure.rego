package swiftdeploy.infrastructure

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Entry point – always return a structured decision object, never a bare bool
# ---------------------------------------------------------------------------
decision := {
    "allow":      allow,
    "violations": violations,
    "domain":     "infrastructure",
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
    disk_free_gb < input.thresholds.min_disk_free_gb
    msg := sprintf(
        "Disk free %.2f GB is below minimum %.2f GB",
        [disk_free_gb, input.thresholds.min_disk_free_gb],
    )
}

violation_messages[msg] if {
    cpu_load > input.thresholds.max_cpu_load
    msg := sprintf(
        "CPU load %.2f exceeds maximum %.2f",
        [cpu_load, input.thresholds.max_cpu_load],
    )
}

violation_messages[msg] if {
    mem_available_pct < input.thresholds.min_mem_available_pct
    msg := sprintf(
        "Memory available %.1f%% is below minimum %.1f%%",
        [mem_available_pct, input.thresholds.min_mem_available_pct],
    )
}

# ---------------------------------------------------------------------------
# Helper – extract stats from input with safe defaults
# ---------------------------------------------------------------------------
disk_free_gb    := input.stats.disk_free_gb
cpu_load        := input.stats.cpu_load
mem_available_pct := input.stats.mem_available_pct
