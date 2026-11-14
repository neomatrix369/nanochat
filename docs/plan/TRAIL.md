# TRAIL

| slice_id | plan | state | notes |
|----------|------|-------|-------|
| fix-forward-mac-phase1 | [2026-11-13-fix-forward-mac.md](2026-11-13-fix-forward-mac.md) Phase 1 | PASSED (merged) | [PR #4](https://github.com/neomatrix369/nanochat/pull/4) + follow-up [PR #5](https://github.com/neomatrix369/nanochat/pull/5) |
| fix-forward-mac-phase2 | same plan Phase 2 | PASSED (merged) | [PR #6](https://github.com/neomatrix369/nanochat/pull/6) merged `f8d7174` |
| fix-forward-mac-phase15 | [2026-11-13-fix-forward-mac-phase15.md](2026-11-13-fix-forward-mac-phase15.md) | PASSED (merged) | [PR #8](https://github.com/neomatrix369/nanochat/pull/8) merged `3054e4a` |
| fix-mps-skip-inductor | (hotfix; see GROWTH / RUNNING §7) | PASSED (merged) | [PR #10](https://github.com/neomatrix369/nanochat/pull/10) merged `f6ef779`: skip Inductor on MPS, MPS AdamW/Muon, progress flush, `.train_ok` + CUDA hard-fail, RoPE grow-on-demand |
| modal-nanochat-minimum | [2026-11-14-modal-nanochat-minimum.md](2026-11-14-modal-nanochat-minimum.md) | MERGED — live run pending | [PR #14](https://github.com/neomatrix369/nanochat/pull/14) merged `5225a3d`. Live Modal run (image, prefetch, 8×H100 train, volume get, billing stop) not yet executed; needs explicit go-ahead (~$40–60) |
