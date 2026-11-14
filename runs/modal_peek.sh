#!/bin/bash

# Peek at Modal runs from the terminal. Read-only: it lists, reads logs and downloads the run
# report. It never stops or changes anything (stop with `modal app stop <app-id>` by hand).
#
# Usage:
#   bash runs/modal_peek.sh status              running apps + active containers
#   bash runs/modal_peek.sh past [N]            last N apps, incl. recently stopped (default 10)
#   bash runs/modal_peek.sh info <app-id>       lifecycle, functions, state of one app
#   bash runs/modal_peek.sh logs <app-id> [N]   last N log lines of an app (default 100)
#   bash runs/modal_peek.sh container <ta-id> [N]  last N log lines of one container
#   bash runs/modal_peek.sh report              CPU run report saved on the Volume (run_stats)
#   bash runs/modal_peek.sh cost [PERIOD]       billing summary, e.g. "this month" or "last month"

set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v modal &>/dev/null; then
    echo "ERROR: 'modal' not found on PATH. Install with: uv tool install modal" >&2
    exit 1
fi

VOLUME="nanochat-modal"
REPORT_REMOTE="run_stats/cpu_train.json"

usage() {
    sed -n 3,13p "$0" | sed 's/^# \{0,1\}//'
}

cmd="${1:-status}"
shift || true

case "$cmd" in
    status)
        echo "== Running apps =="
        modal app list
        echo
        echo "== Active containers =="
        modal container list
        ;;
    past)
        modal app list --limit "${1:-10}"
        ;;
    info)
        [ -n "${1:-}" ] || { echo "usage: modal_peek.sh info <app-id>" >&2; exit 2; }
        modal app info "$1"
        ;;
    logs)
        [ -n "${1:-}" ] || { echo "usage: modal_peek.sh logs <app-id> [N]" >&2; exit 2; }
        modal app logs "$1" | tail -n "${2:-100}"
        ;;
    container)
        [ -n "${1:-}" ] || { echo "usage: modal_peek.sh container <ta-id> [N]" >&2; exit 2; }
        modal container logs "$1" | tail -n "${2:-100}"
        ;;
    report)
        # Downloads to stdout; nothing is written locally.
        modal volume get "$VOLUME" "$REPORT_REMOTE" - || {
            echo "No run report yet at $VOLUME:$REPORT_REMOTE (it is written when a CPU training run ends)." >&2
            exit 1
        }
        ;;
    cost)
        modal billing summary --for "${1:-this month}"
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        echo "unknown command: $cmd" >&2
        usage >&2
        exit 2
        ;;
esac
