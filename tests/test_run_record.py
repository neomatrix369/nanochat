"""
Author: nanochat run-record slice (Claude)
Created: 2026-11-14
Scope: nanochat/run_record.py. Run folders for local and Modal runs: recording, summary, compare.
"""

import json
from pathlib import Path

import pytest

from nanochat.run_record import (
    EVENTS_JSONL,
    RUN_JSON,
    SUMMARY_JSON,
    RunRecorder,
    append_event,
    compare_table,
    find_run_dirs,
    make_run_logger,
    percentile,
    read_events,
    summarize,
)


def _span(name: str, dur: float, status: str = "ok") -> dict:
    return {"type": "span", "name": name, "dur_s": dur, "status": status, "t": 0}


def _metric(t: float, **data) -> dict:
    return {"type": "metric", "t": t, "data": data}


def test_percentile_uses_nearest_rank_and_handles_empty() -> None:
    """
    Scenario: p50 and p95 of step times; empty input gives None.
    Slice: latency percentiles in summaries.
    """
    # ### Given / ### When / ### Then
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 95) == 4
    assert percentile([], 50) is None


def test_summarize_reads_spans_metrics_and_quality(tmp_path: Path) -> None:
    """
    Scenario: a finished run with two stages, a hook wait, metrics and a validation score.
    Slice: summary carries durations, latency, throughput and quality.
    """
    # ### Given
    run_dir = tmp_path / "20261114-000000-local-cpu"
    run_dir.mkdir()
    (run_dir / RUN_JSON).write_text(json.dumps({
        "run_id": "20261114-000000-local-cpu", "mode": "local-cpu", "status": "ok",
        "started_at": 1000.0, "ended_at": 4600.0, "code_rev": "abc1234", "code_dirty": False,
        "config": {"device_type": "mps"},
    }))
    append_event(str(run_dir), _span("stage:base_train", 3000.0))
    append_event(str(run_dir), _span("hook:base_train", 2.5))
    append_event(str(run_dir), _metric(1010.0, step=100, **{"train/dt": 1.0, "train/tok_per_sec": 9000}))
    append_event(str(run_dir), _metric(1020.0, step=200, **{"train/dt": 3.0, "train/tok_per_sec": 8000, "val/bpb": 1.2}))
    append_event(str(run_dir), _metric(1030.0, step=300, **{"val/bpb": 1.1, "core_metric": 0.05}))

    # ### When
    summary = summarize(str(run_dir))

    # ### Then
    assert summary["status"] == "ok"
    assert summary["device"] == "mps"
    assert summary["wall_s"] == 3600.0
    assert summary["first_metric_latency_s"] == 10.0
    assert summary["stages_s"] == {"base_train": 3000.0}
    assert summary["hook_wait_s"] == 2.5
    assert summary["steps_done"] == 300
    assert summary["step_time_s_p50"] == 1.0
    assert summary["step_time_s_p95"] == 3.0
    assert summary["tok_per_sec_last"] == 8000
    assert summary["val_bpb_min"] == 1.1
    assert summary["val_bpb_last"] == 1.1
    assert summary["core_metric_last"] == 0.05


def test_read_events_skips_a_partly_written_last_line(tmp_path: Path) -> None:
    """
    Scenario: a run was killed mid-write, leaving a truncated JSON line.
    Slice: summaries of killed runs still work.
    """
    # ### Given
    append_event(str(tmp_path), _metric(1.0, step=1))
    (tmp_path / EVENTS_JSONL).open("a").write('{"type": "metric", "t": 2')

    # ### When
    events = read_events(str(tmp_path))

    # ### Then
    assert len(events) == 1
    assert events[0]["data"]["step"] == 1


def test_running_run_without_end_is_reported_as_running(tmp_path: Path) -> None:
    """
    Scenario: run.json says running and there is no end time (still going, or killed).
    Slice: status is never reported as ok for a run that has not finished.
    """
    # ### Given
    (tmp_path / RUN_JSON).write_text(json.dumps({"status": "running", "started_at": 0.0}))

    # ### When
    summary = summarize(str(tmp_path), now=60.0)

    # ### Then
    assert summary["status"] == "running"
    assert summary["wall_s"] == 60.0


def test_recorder_writes_run_json_events_and_summary(tmp_path: Path) -> None:
    """
    Scenario: a trainer logs through the recorder, then finishes it.
    Slice: the trainer's wandb-shaped calls land in events.jsonl and summary.json.
    """
    # ### Given
    recorder = RunRecorder(str(tmp_path), config={"depth": 6})

    # ### When
    recorder.log({"step": 500, "train/dt": 0.5, "train/tok_per_sec": 1234})
    recorder.finish()

    # ### Then
    run = json.loads((tmp_path / RUN_JSON).read_text())
    assert run["status"] == "ok"
    assert run["config"]["depth"] == 6
    assert "code_rev" in run
    summary = json.loads((tmp_path / SUMMARY_JSON).read_text())
    assert summary["steps_done"] == 500


def test_make_run_logger_is_unchanged_without_a_run_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: NANOCHAT_RUN_DIR is unset, as in an existing run. The backend is returned as-is.
    Slice: recording adds nothing when it is not asked for.
    """
    # ### Given
    monkeypatch.delenv("NANOCHAT_RUN_DIR", raising=False)
    backend = object()

    # ### When / ### Then
    assert make_run_logger(backend) is backend


def test_make_run_logger_tees_to_recorder_and_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: NANOCHAT_RUN_DIR is set. Logs reach the recorder and the existing backend.
    Slice: wandb keeps working alongside the run record.
    """
    # ### Given
    monkeypatch.setenv("NANOCHAT_RUN_DIR", str(tmp_path))
    seen: list[dict] = []

    class Backend:
        def log(self, data, *args, **kwargs):
            seen.append(data)

        def finish(self, *args, **kwargs):
            pass

    logger = make_run_logger(Backend())

    # ### When
    logger.log({"step": 500})

    # ### Then
    assert seen == [{"step": 500}]
    assert read_events(str(tmp_path))[0]["data"] == {"step": 500}


def test_compare_table_lists_each_run_with_key_columns(tmp_path: Path) -> None:
    """
    Scenario: two runs under one root; the table has one row per run and the dirty flag.
    Slice: compare shows latency, quality and config at a glance.
    """
    # ### Given
    for name, dirty in [("20261114-010000-local-cpu", False), ("20261114-020000-modal-cpu", True)]:
        d = tmp_path / name
        d.mkdir()
        (d / RUN_JSON).write_text(json.dumps({"run_id": name, "mode": name.split("-", 2)[2], "status": "ok",
                                              "started_at": 0.0, "ended_at": 60.0, "code_rev": "abc", "code_dirty": dirty}))

    # ### When
    table = compare_table(find_run_dirs(str(tmp_path)))

    # ### Then
    lines = table.splitlines()
    assert lines[0].split()[0] == "run"
    assert len(lines) == 3
    assert "abc*" in lines[1] or "abc*" in lines[2]
    assert "modal-cpu" in lines[1] and "local-cpu" in lines[2]


def test_recorder_keeps_only_milestones(tmp_path: Path) -> None:
    """
    Scenario: the trainer logs every 10 steps; only every 500th step and core/ChatCORE points are written.
    Slice: the run folder stays small however often the trainer logs.
    """
    # ### Given
    recorder = RunRecorder(str(tmp_path))

    # ### When
    for step in range(10, 1001, 10):
        recorder.log({"step": step, "train/loss": 1.0})
    recorder.log({"step": 530, "core_metric": 0.1})

    # ### Then
    kept = [e["data"]["step"] for e in read_events(str(tmp_path))]
    assert kept == [500, 1000, 530]
