"""Run record: one folder per training run, the same shape locally and on Modal.

    <run-dir>/
      run.json      identity, config snapshot, code revision, host, status, timestamps
      events.jsonl  append-only: stage/hook spans (written by runs/_stage_lib.sh) and
                    metric points (written by the trainers through wandb_run.log)
      summary.json  derived from the two files above (durations, latency, quality)

Standard library only, so the shell scripts can call it without loading torch.

CLI:
    python3 -m nanochat.run_record start <run-dir> --mode local-cpu   # write run.json at launch
    python3 -m nanochat.run_record summary <run-dir>                  # (re)build summary.json
    python3 -m nanochat.run_record compare <root>                     # table of every run under root
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Iterable
from typing import Any

RUN_JSON = "run.json"
EVENTS_JSONL = "events.jsonl"
SUMMARY_JSON = "summary.json"

# Keep the record small: metric points only at milestones, not at every log call.
# One sample every SAMPLE_EVERY steps, plus every core / ChatCORE evaluation (both are rare).
SAMPLE_EVERY = 500
ALWAYS_KEEP_KEYS = ("core_metric", "chatcore_metric")


def is_milestone(data: dict[str, Any]) -> bool:
    """True when a metric point is worth writing to disk."""
    step = data.get("step")
    if isinstance(step, int) and step % SAMPLE_EVERY == 0:
        return True
    return any(k in data for k in ALWAYS_KEEP_KEYS)


# ─────────────────────────────────────────────────────────────────────────────
# Files


def _read_json(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def append_event(run_dir: str, event: dict[str, Any]) -> None:
    """Append one event as a JSON line. One short write per line keeps the file readable mid-run."""
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, EVENTS_JSONL), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(run_dir: str) -> list[dict[str, Any]]:
    """Read all events. A partly written last line (run still going, or killed) is skipped."""
    events: list[dict[str, Any]] = []
    try:
        with open(os.path.join(run_dir, EVENTS_JSONL), encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return events


# ─────────────────────────────────────────────────────────────────────────────
# Identity: what ran, on what, from which code


def new_run_id(mode: str, now: float | None = None) -> str:
    """UTC timestamp plus mode, e.g. 20261114-125440-local-cpu."""
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(now or time.time())) + f"-{mode}"


def git_revision(repo_dir: str = ".") -> dict[str, Any]:
    """Short commit and whether the working tree has uncommitted changes."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"code_rev": "unknown", "code_dirty": None}
    return {"code_rev": rev, "code_dirty": dirty}


def host_info() -> dict[str, Any]:
    cores = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cores_visible": cores,
    }


def env_overrides(prefix: str = "NANOCHAT_RUNCPU_") -> dict[str, str]:
    """Knobs set through the environment (Modal overrides, local tweaks) so runs record them."""
    return {k: v for k, v in sorted(os.environ.items()) if k.startswith(prefix)}


def start_run(run_dir: str, mode: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write run.json at launch. Safe to call again: identity is kept, config is merged."""
    existing = _read_json(os.path.join(run_dir, RUN_JSON))
    run = {
        "run_id": os.path.basename(os.path.normpath(run_dir)),
        "mode": mode,
        "status": "running",
        "started_at": time.time(),
        **git_revision(),
        **({"code_rev": os.environ["NANOCHAT_CODE_REV"]} if os.environ.get("NANOCHAT_CODE_REV") else {}),
        "host": host_info(),
        "env_overrides": env_overrides(),
        "config": {},
        **existing,
    }
    run["config"] = {**run.get("config", {}), **(config or {})}
    _write_json(os.path.join(run_dir, RUN_JSON), run)
    return run


# ─────────────────────────────────────────────────────────────────────────────
# Recording from the trainers (same .log / .finish shape as wandb)


class RunRecorder:
    """Drop-in for DummyWandb / wandb: .log(dict) records a metric point, .finish() closes the run."""

    def __init__(self, run_dir: str, config: dict[str, Any] | None = None) -> None:
        self.run_dir = run_dir
        self.run = start_run(run_dir, mode=os.environ.get("NANOCHAT_RUN_MODE", "local"), config=config)

    def log(self, data: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        if is_milestone(data):
            append_event(self.run_dir, {"type": "metric", "t": time.time(), "data": data})

    def finish(self, status: str = "ok") -> None:
        run = _read_json(os.path.join(self.run_dir, RUN_JSON))
        run.update({"status": status, "ended_at": time.time()})
        _write_json(os.path.join(self.run_dir, RUN_JSON), run)
        write_summary(self.run_dir)


class TeeLogger:
    """Send each call to the recorder and to the existing backend (wandb or dummy)."""

    def __init__(self, backends: Iterable[Any]) -> None:
        self.backends = list(backends)

    def log(self, data: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        for backend in self.backends:
            backend.log(data, *args, **kwargs)

    def finish(self, *args: Any, **kwargs: Any) -> None:
        for backend in self.backends:
            backend.finish(*args, **kwargs)


def make_run_logger(backend: Any, config: dict[str, Any] | None = None) -> Any:
    """Return the logger a trainer should use.

    NANOCHAT_RUN_DIR set (local runs and Modal runs set it) → record to that folder as well.
    Unset → the backend unchanged, so nothing new is written.
    """
    run_dir = os.environ.get("NANOCHAT_RUN_DIR")
    if not run_dir:
        return backend
    return TeeLogger([RunRecorder(run_dir, config=config), backend])


# ─────────────────────────────────────────────────────────────────────────────
# Summary: durations, latency, quality


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile, q in [0, 100]. None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, round(q / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _last(values: list[float]) -> float | None:
    return values[-1] if values else None


def summarize(run_dir: str, now: float | None = None) -> dict[str, Any]:
    """Build the summary from run.json and events.jsonl. Works on running and killed runs too."""
    run = _read_json(os.path.join(run_dir, RUN_JSON))
    events = read_events(run_dir)
    now = now or time.time()

    spans = [e for e in events if e.get("type") == "span"]
    metrics = [e.get("data", {}) for e in events if e.get("type") == "metric"]
    metric_times = [e["t"] for e in events if e.get("type") == "metric" and "t" in e]

    started = run.get("started_at")
    ended = run.get("ended_at")
    status = run.get("status", "unknown")
    wall = (ended or now) - started if started is not None else None

    def values(key: str) -> list[float]:
        return [m[key] for m in metrics if isinstance(m.get(key), (int, float))]

    steps = [int(m["step"]) for m in metrics if isinstance(m.get("step"), (int, float))]
    dts = values("train/dt")
    tok_s = values("train/tok_per_sec")
    val = values("val/bpb")
    core = values("core_metric")
    chatcore = values("chatcore_metric")
    losses = values("train/loss")

    summary = {
        "run_id": run.get("run_id", os.path.basename(os.path.normpath(run_dir))),
        "mode": run.get("mode"),
        "status": status,
        "code_rev": run.get("code_rev"),
        "code_dirty": run.get("code_dirty"),
        "device": run.get("config", {}).get("device_type") or run.get("device"),
        "wall_s": round(wall, 1) if wall is not None else None,
        "first_metric_latency_s": round(metric_times[0] - started, 1) if metric_times and started else None,
        "stages_s": {s["name"].removeprefix("stage:"): s["dur_s"] for s in spans if s["name"].startswith("stage:")},
        "hook_wait_s": round(sum(s["dur_s"] for s in spans if s["name"].startswith("hook:")), 1),
        "steps_done": max(steps) if steps else 0,
        "step_time_s_p50": percentile(dts, 50),
        "step_time_s_p95": percentile(dts, 95),
        "tok_per_sec_last": _last(tok_s),
        "train_loss_last": _last(losses),
        "val_bpb_last": _last(val),
        "val_bpb_min": min(val) if val else None,
        "core_metric_last": _last(core),
        "chatcore_last": _last(chatcore),
        "env_overrides": run.get("env_overrides", {}),
        "metric_sample_every_steps": SAMPLE_EVERY,
    }
    return summary


def write_summary(run_dir: str) -> dict[str, Any]:
    summary = summarize(run_dir)
    _write_json(os.path.join(run_dir, SUMMARY_JSON), summary)
    return summary


def compare_table(run_dirs: list[str]) -> str:
    """One aligned text table of runs, newest first, built from each run's summary."""
    header = ["run", "mode", "status", "device", "code", "wall", "steps", "s/step p50", "tok/s", "val bpb", "core", "hook wait"]
    rows = [header]
    for d in run_dirs:
        s = _read_json(os.path.join(d, SUMMARY_JSON)) or summarize(d)
        wall = s.get("wall_s")
        rows.append([
            s.get("run_id", os.path.basename(d)),
            str(s.get("mode") or "-"),
            str(s.get("status") or "-"),
            str(s.get("device") or "-"),
            str(s.get("code_rev") or "-") + ("*" if s.get("code_dirty") else ""),
            _hms(wall) if wall is not None else "-",
            str(s.get("steps_done", "-")),
            _fmt(s.get("step_time_s_p50"), "{:.2f}"),
            _fmt(s.get("tok_per_sec_last"), "{:,.0f}"),
            _fmt(s.get("val_bpb_min"), "{:.4f}"),
            _fmt(s.get("core_metric_last"), "{:.4f}"),
            _hms(s.get("hook_wait_s", 0)),
        ])
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows)


def _fmt(value: float | None, pattern: str) -> str:
    return "-" if value is None else pattern.format(value)


def _hms(seconds: float | None) -> str:
    total = max(0, round(seconds or 0))
    return f"{total // 3600}h{total % 3600 // 60:02d}m{total % 60:02d}s"


def find_run_dirs(root: str) -> list[str]:
    """Run folders under root (any folder holding a run.json), newest run id first."""
    if not os.path.isdir(root):
        return []
    dirs = [os.path.join(root, d) for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, RUN_JSON))]
    return sorted(dirs, key=os.path.basename, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m nanochat.run_record")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start", help="write run.json at launch")
    p_start.add_argument("run_dir")
    p_start.add_argument("--mode", required=True)
    p_sum = sub.add_parser("summary", help="rebuild summary.json and print it")
    p_sum.add_argument("run_dir")
    p_cmp = sub.add_parser("compare", help="table of every run under a root")
    p_cmp.add_argument("root")
    args = parser.parse_args(argv)

    if args.cmd == "start":
        start_run(args.run_dir, mode=args.mode)
        return 0
    if args.cmd == "summary":
        print(json.dumps(write_summary(args.run_dir), indent=2, sort_keys=True))
        return 0
    dirs = find_run_dirs(args.root)
    if not dirs:
        print(f"no runs under {args.root}", file=sys.stderr)
        return 1
    print(compare_table(dirs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
