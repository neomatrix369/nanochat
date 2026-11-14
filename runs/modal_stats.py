"""Resource report for a Modal run: what was requested vs what the job actually used.

Pure functions only (no modal import) so they can be unit-tested locally.
Used by runs/modal_run.py after a training run to say whether cores and memory
were over- or under-provisioned.
"""

from __future__ import annotations

from typing import Any

# Thresholds for the verdicts. Tune after the first real measurements.
CORE_UNDERUSE = 0.5  # below this share of requested cores busy → over-provisioned cores
CORE_SATURATED = 0.9  # above this → more cores may help
MEMORY_TIGHT = 0.85  # peak RSS above this share of the limit → raise memory
MEMORY_LOOSE = 0.25  # peak RSS below this share → lower memory


def parse_memory_max(text: str) -> int | None:
    """Parse a cgroup v2 memory.max value: a byte count, or 'max' (no limit) → None."""
    value = text.strip()
    if not value or value == "max":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def core_verdict(avg_cores_busy: float, cores_requested: int) -> str:
    """Say whether the requested cores were used."""
    share = avg_cores_busy / cores_requested if cores_requested else 0.0
    if share < CORE_UNDERUSE:
        return f"over-provisioned cores: only {avg_cores_busy:.1f} of {cores_requested} busy; try fewer"
    if share > CORE_SATURATED:
        return f"cores saturated ({avg_cores_busy:.1f}/{cores_requested}); more cores may help"
    return f"cores ok ({avg_cores_busy:.1f}/{cores_requested} busy)"


def memory_verdict(peak_bytes: int, limit_bytes: int | None) -> str:
    """Say whether the memory request was right. No limit known → report only."""
    if not limit_bytes:
        return f"memory peak {peak_bytes / 2**30:.1f} GiB (no cgroup limit visible)"
    share = peak_bytes / limit_bytes
    if share > MEMORY_TIGHT:
        return f"memory tight: peak {share:.0%} of limit; raise memory"
    if share < MEMORY_LOOSE:
        return f"memory loose: peak {share:.0%} of limit; lower memory"
    return f"memory ok: peak {share:.0%} of limit"


def summarize_run(
    *,
    wall_s: float,
    child_cpu_s: float,
    cores_requested: int,
    peak_rss_kb: int,
    memory_limit_bytes: int | None,
    timeout_s: int,
) -> dict[str, Any]:
    """Build the run report: timing, core use, memory use and verdicts."""
    avg_cores_busy = child_cpu_s / wall_s if wall_s > 0 else 0.0
    peak_bytes = peak_rss_kb * 1024
    return {
        "wall_s": round(wall_s, 1),
        "timeout_s": timeout_s,
        "timeout_share": round(wall_s / timeout_s, 3) if timeout_s else None,
        "cores_requested": cores_requested,
        "avg_cores_busy": round(avg_cores_busy, 2),
        "peak_rss_gib": round(peak_bytes / 2**30, 2),
        "memory_limit_gib": round(memory_limit_bytes / 2**30, 2) if memory_limit_bytes else None,
        "verdicts": [
            core_verdict(avg_cores_busy, cores_requested),
            memory_verdict(peak_bytes, memory_limit_bytes),
        ],
    }
