#!/bin/bash

# Modal nanochat runner. Two modes, picked with MODE (default: cpu):
#   MODE=cpu  runs/runcpu.sh on a heavy CPU machine (64 cores target, no GPU, no GPU payment gate)
#   MODE=gpu  runs/speedrun.sh on 8×H100 (needs a GPU payment method and entitlement)
# One command: bash runs/runmodal.sh          (CPU)
#              MODE=gpu bash runs/runmodal.sh (GPU, later)
# Prerequisites: Modal account, `modal setup`, local `modal` CLI.
# Skip the prompt with RUNMODAL_YES=1.

set -euo pipefail

MODE="${MODE:-cpu}"
case "$MODE" in
    cpu|gpu) ;;
    *) echo "ERROR: MODE must be cpu or gpu (got '$MODE')" >&2; exit 1 ;;
esac

# Fail-fast: require modal on PATH
if ! command -v modal &>/dev/null; then
    echo "ERROR: 'modal' not found on PATH. Install with: pip install modal (or uv tool run modal)" >&2
    echo "Then run 'modal setup'." >&2
    exit 1
fi

# Print the mode-specific header with cost and time
if [ "$MODE" = "cpu" ]; then
    cat <<'EOF'
============================================================================
 nanochat on Modal — CPU mode (runcpu profile, small model, whole pipeline)

 Machine: heavy CPU container, up to 64 cores / 128 GiB, no GPU
 Cost:    scales with cores. Check Modal's current CPU price before running.
          The first run measures real time; the cost is printed there too.
 Time:    unmeasured. Keep laptop awake; use screen/tmux (see docs/RUNNING.md)

 On completion: tokenizer + chat checkpoint downloaded to ~/.cache/nanochat-modal
   NANOCHAT_BASE_DIR=~/.cache/nanochat-modal python3 -m scripts.chat_cli
============================================================================
EOF
else
    cat <<'EOF'
============================================================================
 nanochat on Modal — GPU mode (speedrun profile, 8×H100)

 Cost: ~$40–60 (~$3/GPU/hr × 8 GPUs × ~1.5–2h). First run higher (image bake).
 Time: ~1.5–2h training + prefetch + image build. Keep laptop awake.

 On completion: tokenizer + chat checkpoint downloaded to ~/.cache/nanochat-modal
   NANOCHAT_BASE_DIR=~/.cache/nanochat-modal python3 -m scripts.chat_cli
============================================================================
EOF
fi

# Spend confirmation (unless RUNMODAL_YES=1)
if [ -z "${RUNMODAL_YES:-}" ]; then
    echo ""
    read -p "Proceed with MODE=$MODE? [y/N] " -r proceed
    if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Launch Modal app
echo ""
echo "Starting Modal run (runs/modal_run.py, mode=$MODE)..."
echo ""
NANOCHAT_MODAL_MODE="$MODE" modal run runs/modal_run.py --mode "$MODE"
