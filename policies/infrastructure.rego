package swiftdeploy.infrastructure

decision := {
    "allow":      allow,
    "violations": violations,
    "domain":     "infrastructure",
    "checked_at": input.checked_at,
}

allow := count(violations) == 0

violations := [msg | some msg in violation_messages]

violation_messages contains msg if {
    input.stats.disk_free_gb < input.thresholds.min_disk_free_gb
    msg := sprintf("Disk free %.2f GB is below minimum %.2f GB",
        [input.stats.disk_free_gb, input.thresholds.min_disk_free_gb])
}

violation_messages contains msg if {
    input.stats.cpu_load > input.thresholds.max_cpu_load
    msg := sprintf("CPU load %.2f exceeds maximum %.2f",
        [input.stats.cpu_load, input.thresholds.max_cpu_load])
}

violation_messages contains msg if {
    input.stats.mem_available_pct < input.thresholds.min_mem_available_pct
    msg := sprintf("Memory available %.1f%% is below minimum %.1f%%",
        [input.stats.mem_available_pct, input.thresholds.min_mem_available_pct])
}
