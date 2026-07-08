# TTS-SFT / SqueezeEvolve — analysis outputs

Analysis & data-verification companion to the code repo **[mianwu01/tts-sft](https://github.com/mianwu01/tts-sft)**.
All results are **oracle-labeled** (full-test grading cache, matching the frontier CSV) and **reproducible from the
included scripts**. No model inference is required to rebuild the tables/figures (only the cached artifacts + scripts).

## Contents

### `data_verification/dynamic_bucket_transition/`
Dynamic **loop0 → loop1 → loop2** bucket-transition analysis (vs. the static loop0-bucket heatmap).
- `dynamic_bucket_transition_summary.md` — main report (transition matrices, native-1 vs discovered-0→1, hard-zero discovery timing).
- `boundary_like_claim_audit.md` — statistical audit (TV distance, bootstrap CIs) of the "discovered-0→1 behaves like native-1/16" claim.
- `sewon_focused_followup/` — strict native-1 vs discovered-0→1 comparison + where canonical-unique density gains come from (by previous-loop bucket).
- `tables/`, `figures/`, `scripts/` — per-problem/-loop counts, transition matrices, and the re-runnable analysis code.

### `data_verification/oss120b_generation_cost_estimate/`
gpt-oss-120B **SqueezeEvolve-generation token & cost estimate** from the actual loop0–2 artifacts.
- `oss120b_generation_cost_estimate.md` — method, measured token distributions, extrapolation to 44k, parametric cost table.
- `provider_landscape_and_switch_plan.md` — real 2026-07 provider prices (incl. batch tiers), 5-loop cost recompute, Qwen3-4B acceleration options, alternative models (gpt-oss-20b / Qwen3-30B-A3B), migration + science caveats.
- `runtime_throughput_estimate.md`, `sewon_reply_draft.md`, `cost_table.csv`, `token_stats_summary.json`, `tables/`, `scripts/`.

### `data_verification/unique_correct_audit/`
Canonical-unique-correct density audit (raw vs exact-unique vs canonical-unique).
- Note: the 80M `per_problem_hashes.json` is **gitignored** (regenerable via `scripts/harvest_correct_hashes.py`).

### `oss_density_work/`
gpt-oss-120B **self-verification density estimate + gold-free stopping-rule simulation** + generation-speed benchmark.
- `OSS_DENSITY_STOPPING_RULE_RESULTS.md` — findings (best estimator = trace prompt; freeze rule ~replaces the oracle).
- `phase_a_sweep.py` / `phase_a2.py` / `phase_b_sim.py` / `gen_speed_bench.py` — harnesses; `*_results.json` + `calls_cache.jsonl` — measured outputs.

### `data_verification/{manifests,deck,scripts}/`
Supporting manifests, the Sewon slide deck, and shared verification scripts.

---
*Generated with [Claude Code](https://claude.com/claude-code). Companion to the pipeline in `mianwu01/tts-sft`.*
