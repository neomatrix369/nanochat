# HANDOFF — modal-nanochat-minimum

Repo: `/Users/swami/git-repos/ai-ml-dl-stuff/playgroups/nanochat`
Plan (SSOT): `docs/plan/2026-11-14-modal-nanochat-minimum.md`
Tracker: `docs/plan/PROGRESS.md` and `docs/plan/TRAIL.md`

## Where things stand (2026-11-14)

- **Code is merged.** PR #14 merged into `master` as merge commit `5225a3d`.
  Branch commits: `4d60902` (env opt-in shell), `afb79e9` (Modal wrapper), `8a0e51e` (review fixes), `4451811` (gitignore), `03d0c4d` (retry pacing and idle clock).
- **Reviews:** nWave code, platform and architecture/docs reviewers all APPROVED. `03d0c4d` was made after approval and was NOT re-reviewed. Ask a reviewer to check it.
- **Local checks pass:** `bash -n` on all `runs/*.sh`, `python3 -m py_compile runs/modal_run.py`, and `uv run python3 -m pytest -q` → 142 passed, 16 skipped.
- **Not verified (needs a real Modal run):** image build, prefetch, 8×H100 train, `modal volume get --force`, chat tip on the Mac, and whether `modal app stop` ends billing.
- **Modal account:** signed in to the `neomatrix369` workspace (token verified). Modal CLI installed as a uv tool at `~/.local/bin/modal` (client 1.6.4). The project venv is untouched.

## Decisions that must hold

- `SKIP_SETUP=1` ALWAYS runs `source .venv/bin/activate`. No PATH fallback. The image must provide `/root/nanochat/.venv`.
- Use `python3`, never bare `python`, in every command and script.
- Modal image: `pip_install("uv")`, copy `pyproject.toml` and `uv.lock`, run `uv sync --no-install-project --extra gpu --frozen` into `/root/nanochat/.venv`, then `add_local_dir` as the LAST layer. The SDK's `Image.uv_sync` is NOT used, because it puts the venv at `/.uv/.venv`.
- Image PATH is a literal string, not `$PATH`.
- Commit failure: the daemon writes `.modal_commit_failed` and keeps the request file. The hook fails on that marker.
- Never `--no-verify`. Never commit to `master`. PRs target `neomatrix369/nanochat`.

## Next steps, in order

1. **Get a go-ahead from the user** for the first billable run. Estimated cost: about $40–60, about 1.5–2 h, plus image build. Nothing billable runs without it.
2. **Confirm the entitlement cheaply first:** `modal profile current` and check the 8×H100 quota in the Modal dashboard. The first real run is the test if the dashboard isn't clear.
3. **Build the image only** (no GPU, no training) to catch layer errors: run `modal run runs/modal_run.py::prefetch` only after going ahead on prefetch cost (CPU, but still billable). If that's not wanted, stop at a local build check.
4. **Run the pipeline** with `RUNMODAL_YES=1 bash runs/runmodal.sh` only once the user says go. Watch the logs for:
   - prefetch elapsed > 300 s and exit 0
   - `NANOCHAT_BASE_DIR=/data/nanochat-modal` printed at GPU start
   - `base_checkpoints/.train_ok` written to the Volume after `base_train`
5. **Verify billing stops:** after Ctrl-C, run `modal app list`, then `modal app stop <app>`. Update `docs/MODAL.md` (Stopping section) with what actually happened.
6. **Verify the chat tip** on the Mac: `NANOCHAT_BASE_DIR=~/.cache/nanochat-modal python3 -m scripts.chat_cli -p "Why is the sky blue?"` must return a non-empty answer.
7. **Second run:** confirm `modal volume get --force` refreshes the local chat dir and shards skip.
8. **Failure check:** kill after a stage, confirm the next run SKIPs finished stages.
9. **Reviews:** have a reviewer check `03d0c4d`.
10. **Progress:** after the live run, update `docs/plan/PROGRESS.md` and `TRAIL.md` (slice → PASSED with the real numbers), and delete this HANDOFF file.

## Known gaps (not blockers for the first run)

- `pytest` must be run as `uv run python3 -m pytest`. Bare `uv run pytest` fails collection (`No module named nanochat`). This is an existing setup issue.
- `pytest-cov` is not in the project env. Coverage runs need `uv run --with pytest-cov python3 -m pytest …`.
- Ruff: `runs/modal_run.py` should now be clean. Re-check after the next edit.
- The README file-structure table lists only four `runs/` files. Add the Modal ones when next editing README.
- Quality gates were not captured in the PR (not a `slice/*` branch).

## Out of scope for the first run

- miniseries and scaling_laws on Modal (later)
- `runcpu.sh` on Modal (never)
- SMOKE / 1×H100 path (not documented; excluded from MVP)
- wandb (default dummy)
