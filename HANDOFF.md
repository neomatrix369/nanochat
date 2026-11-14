# HANDOFF — modal-nanochat-minimum

Branch: `feat/modal-nanochat-minimum` (pushed)
Plan (SSOT): `docs/plan/2026-11-14-modal-nanochat-minimum.md`
Tracker: `docs/plan/PROGRESS.md` and `docs/plan/TRAIL.md`

## Where things stand (2026-11-14)

- **Code merged:** PR #14 is on `master` (merge `5225a3d`).
- **Fix pushed:** `9eed864` moves `.env()` above the `add_local_dir` layer. Modal rejects build steps after local files, so the first image build failed. The image now builds in about 1.4 s after cache.
- **Tracker commit:** `fcf3de0` marks the slice "MERGED — live run pending". PR #16 is open for it against `master`.
- **Local checks pass:** 140 passed / 18 skipped, ruff clean, `py_compile` clean. Earlier runs showed 142 / 16. There are no test changes against `master`, so the difference is environmental (FA3 skip logic).
- **Reviews:** nWave reviewers approved before `03d0c4d`. `03d0c4d` and `9eed864` were not re-reviewed.

## Blocker (must fix before any run)

**Modal refuses H100 functions until a payment method is added.** The prefetch run stopped with `Please add a payment method to use H100 GPU functions`. Prefetch itself never ran.

- Fix: add a card at Modal (Settings → Billing) for the `neomatrix369` workspace.
- Then confirm the account can run 8×H100 (quota). This is the entitlement check.
- Don't work around it. The GPU function is declared at app load, so the whole app is blocked.

## Next steps, in order

1. **Add a payment method** on Modal (see Blocker). You do this in the dashboard.
2. **Re-run prefetch** (CPU, billable but small): `modal run runs/modal_run.py::prefetch`. Needs your go-ahead.
3. **Get explicit approval for the full run** (about $40–60, about 1.5–2 h). Then `RUNMODAL_YES=1 bash runs/runmodal.sh`.
4. **Watch the logs for:**
   - prefetch elapsed > 300 s and exit 0
   - `NANOCHAT_BASE_DIR=/data/nanochat-modal` at GPU start
   - `base_checkpoints/.train_ok` on the Volume after `base_train`
5. **Verify billing stops:** after any Ctrl-C, run `modal app list`, then `modal app stop <app>`. Record the result in `docs/MODAL.md` (Stopping section).
6. **Chat tip on the Mac** (needs a checkpoint): `NANOCHAT_BASE_DIR=~/.cache/nanochat-modal python3 -m scripts.chat_cli -p "Why is the sky blue?"` should give a non-empty answer.
7. **Second run:** `modal volume get --force` refreshes the chat dir and shards skip.
8. **Failure check:** kill after a stage, confirm the next run SKIPs finished stages.
9. **Review** `03d0c4d` and `9eed864` with a reviewer.
10. **Progress:** after the live run, update `PROGRESS.md` and `TRAIL.md` with real numbers. Then delete this file.

## Known gaps (not blockers)

- Run pytest as `uv run python3 -m pytest`. Bare `uv run pytest` fails collection.
- `pytest-cov` is not in the project env. Use `uv run --with pytest-cov python3 -m pytest`.
- `ruff` is not in the project env. Use `uvx ruff check runs/`.
- The README `runs/` table lists four files. Add the Modal ones next time README is edited.
- Modal SDK warns about `Sourcery` suggestions (`contextlib.suppress`) in `runs/modal_run.py`. Cosmetic.

## Out of scope for the first run

- miniseries and scaling_laws on Modal (later)
- `runcpu.sh` on Modal (never)
- SMOKE / 1×H100 path (not documented; excluded from MVP)
- wandb (default dummy)
