#!/bin/bash

# Peek at Modal runs from the terminal. Read-only: it lists, reads logs and downloads the run
# report. It never stops or changes anything (stop with `modal app stop <app-id>` by hand).
#
# If you leave out an app or container id, the script picks the current run: the newest
# nanochat app that is running (preferring one with tasks), else the newest nanochat app.
# It prints which one it picked.
#
# Usage:
#   bash runs/modal_peek.sh status                 running apps + active containers
#   bash runs/modal_peek.sh past [N]               last N apps, incl. recently stopped (default 10)
#   bash runs/modal_peek.sh info [app-id]          lifecycle, functions, state of an app
#   bash runs/modal_peek.sh logs [app-id] [N] [-f]      last N log lines of an app (default 100); -f streams live
#   bash runs/modal_peek.sh container [ta-id] [N] [-f] last N log lines of a container; -f streams live
#   bash runs/modal_peek.sh report                 CPU run report saved on the Volume (run_stats)
#   bash runs/modal_peek.sh cost [PERIOD]          billing summary, e.g. "this month" or "last month"

set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v modal &>/dev/null; then
    echo "ERROR: 'modal' not found on PATH. Install with: uv tool install modal" >&2
    exit 1
fi

VOLUME="nanochat-modal"
REPORT_REMOTE="run_stats/cpu_train.json"

usage() {
    sed -n 3,18p "$0" | sed 's/^# \{0,1\}//'
}

# Print "<app-id>\t<state>\t<created_at>" for the current nanochat run. Exit 1 if none.
pick_app() {
    modal app list --json | python3 -c '
import json, sys
apps = [a for a in json.load(sys.stdin) if a["description"].startswith("nanochat")]
running = [a for a in apps if a["state"] == "ephemeral"]
busy = [a for a in running if str(a["tasks"]) != "0"]
pool = busy or running or apps
if not pool:
    sys.exit(1)
best = max(pool, key=lambda a: a["created_at"])
print(best["app_id"], best["state"], best["created_at"], sep="\t")
'
}

# Print the id of the first container belonging to app $1. Exit 1 if none.
pick_container() {
    modal container list --json | python3 -c '
import json, sys
app = sys.argv[1]
found = [c for c in json.load(sys.stdin) if c["app_id"] == app]
if not found:
    sys.exit(1)
print(found[0]["container_id"])
' "$1"
}

# Resolve the app id: use $1 if given, else the current run (and say which one).
resolve_app() {
    if [ -n "${1:-}" ]; then
        echo "$1"
        return
    fi
    local line
    line=$(pick_app) || { echo "No nanochat app found. Pass an app id, or run: bash runs/modal_peek.sh past" >&2; exit 1; }
    local app state created
    IFS=$'\t' read -r app state created <<<"$line"
    echo "Using app $app (state: $state, created $created). Pass an app id to choose another." >&2
    echo "$app"
}

cmd="${1:-status}"
shift || true

# -f anywhere in the args means "follow": stream logs live instead of a snapshot.
follow=0
rest=()
for arg in "$@"; do
    if [ "$arg" = "-f" ]; then follow=1; else rest+=("$arg"); fi
done
set -- ${rest[@]+"${rest[@]}"}

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
        app=$(resolve_app "${1:-}")
        modal app info "$app"
        ;;
    logs)
        # Args: [app-id] [N]. A leading ap- id picks the app; otherwise the arg is N.
        if [[ "${1:-}" == ap-* ]]; then
            app=$(resolve_app "$1"); n="${2:-100}"
        else
            app=$(resolve_app ""); n="${1:-100}"
        fi
        if [ "$follow" = 1 ]; then
            modal app logs "$app" -f
        else
            modal app logs "$app" | tail -n "$n"
        fi
        ;;
    container)
        # Args: [ta-id] [N]. A leading ta- id picks the container; otherwise the current run's.
        if [[ "${1:-}" == ta-* ]]; then
            ctr="$1"; n="${2:-100}"
        else
            app=$(resolve_app "")
            ctr=$(pick_container "$app") || { echo "No active container for app $app (the run may have finished)." >&2; exit 1; }
            echo "Using container $ctr." >&2
            n="${1:-100}"
        fi
        if [ "$follow" = 1 ]; then
            modal container logs "$ctr" -f
        else
            modal container logs "$ctr" | tail -n "$n"
        fi
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
