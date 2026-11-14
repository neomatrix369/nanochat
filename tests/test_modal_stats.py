"""
Author: nanochat Modal slice (Claude)
Created: 2026-11-14
Scope: runs/modal_stats.py resource verdicts (over/under-provisioned cores and memory).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from modal_stats import core_verdict, memory_verdict, parse_memory_max, summarize_run

GIB = 2**30


def test_parse_memory_max_reads_bytes_and_treats_max_as_no_limit() -> None:
    """
    Scenario: cgroup memory.max is a byte count, or 'max' when unlimited.
    Slice: reading the container memory limit.
    """
    # ### Given / ### When / ### Then
    assert parse_memory_max("137438953472\n") == 128 * GIB
    assert parse_memory_max("max\n") is None
    assert parse_memory_max("") is None


def test_core_verdict_flags_underuse_saturation_and_ok() -> None:
    """
    Scenario: 64 cores requested; busy cores decide the verdict.
    Slice: core right-sizing.
    """
    # ### Given
    requested = 64

    # ### When / ### Then
    assert core_verdict(10.0, requested).startswith("over-provisioned cores")
    assert core_verdict(60.0, requested).startswith("cores saturated")
    assert core_verdict(40.0, requested).startswith("cores ok")


def test_memory_verdict_flags_tight_loose_and_unknown_limit() -> None:
    """
    Scenario: 128 GiB limit; peak RSS decides tight, loose, ok, or no-limit.
    Slice: memory right-sizing.
    """
    # ### Given
    limit = 128 * GIB

    # ### When / ### Then
    assert memory_verdict(120 * GIB, limit).startswith("memory tight")
    assert memory_verdict(10 * GIB, limit).startswith("memory loose")
    assert memory_verdict(60 * GIB, limit).startswith("memory ok")
    assert memory_verdict(10 * GIB, None).startswith("memory peak")


def test_summarize_run_reports_timing_and_both_verdicts() -> None:
    """
    Scenario: a 1 h run on 64 requested cores using 6 cores on average, peak 20 GiB of 128 GiB.
    Slice: full run report that tells the user what to change.
    """
    # ### Given / ### When
    report = summarize_run(
        wall_s=3600.0,
        child_cpu_s=6 * 3600.0,
        cores_requested=64,
        peak_rss_kb=20 * 1024 * 1024,
        memory_limit_bytes=128 * GIB,
        timeout_s=3 * 3600,
    )

    # ### Then
    assert report["avg_cores_busy"] == 6.0
    assert report["peak_rss_gib"] == 20.0
    assert report["timeout_share"] == round(1 / 3, 3)
    assert report["verdicts"][0].startswith("over-provisioned cores")
    assert report["verdicts"][1].startswith("memory loose")
