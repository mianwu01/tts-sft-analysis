# Phase 9 — Oracle-use and leakage audit

Inspected: generation configs (`se16/sh*/config.yaml`, `sharded_qwen3_4b/sh*/{fb,loop0b}.yaml`,
`svd_pilot_100/se_nofb/sh*/config.yaml`), operators (`recombination:` values), selection driver
(`scripts/run_self_verification_selection.py` + `src/tts_sft/selection/pools.py`), SFT builders
(`scripts/build_*sft*.py`, `data/sft/*.summary.json`), eval scripts (`eval_ckpt_lcbv6_nonthinking.sh`,
`collect_lcbv6_sweep.py`), contamination artifact
(`outputs/openthoughts114k_codeforces_contamination_check/summary.json`), pool schema fields.

## Leakage-risk table

| # | channel | finding | risk |
|---|---|---|---|
| 1 | Gold tests inside SE generation loop | Headline arms (se16, pop-8 nofb, loop0b, selection SE pool) use `recombination: livecodebench-aggregate`, `evaluation: livecodebench-none`, `fitness: diversity`, `confidence_percentiles: []` → **verifier-free, no tests in prompts**; tests touched only by post-hoc graders. VERIFIED from configs. | **low** |
| 2 | The **fb arm** (`sharded_qwen3_4b/sh*/fb_out.jsonl`, `recombination: livecodebench-feedback-canonical`) injects full codeforces test RESULTS into recombination prompts | Tests leaked into generation **by design** (datagen-only arm). It is NOT part of any headline frontier/SE-vs-BoN number (verified: `reachability_se_vs_bon.py` reads `nofb_out.jsonl`). Any future use of fb outputs for frontier claims would be **high**; for SFT-data generation it is defensible but must be disclosed. | **medium (if reused)** |
| 3 | Oracle correctness used to SELECT training data | YES by design: all SFT arms train on **full-pass (oracle-verified)** candidates; best-per-problem = oracle-verified + consensus-shortest. This is STaR/rejection-sampling-style **train-side oracle use**, not eval leakage (eval is a disjoint benchmark). Papers must not describe these SFT arms as "test-free". Test-free selection exists only in the Phase-6 pilots (judges never see tests — verified in pools/driver code). | **low, disclose** |
| 4 | Train/eval problem overlap | Training pool = codeforces (1,617); eval = LCBv6-131 = **82 atcoder + 49 leetcode, zero codeforces**. 8-shingle containment ≥0.5: **0 flagged /1,617**, whole histogram in [0,0.1). VERIFIED artifact. (Statement-level dedup only; does not rule out semantic near-duplicates across platforms — standard caveat.) | **low** |
| 5 | Held-out eval solutions in SFT data | SFT rows are the model's own codeforces solutions; no LCBv6 problems/solutions present (disjoint by #4). Pool `do_not_use_fields` excludes `ground_truth_solution`/`deepseek_solution`/`deepseek_reasoning` from prompts; per-record `leakage_note: question_and_tests_only_no_solution_or_reasoning`. | **low** |
| 6 | Self-verifier / strong-judge labels in-loop | None anywhere: SE runs are verifier-free; judge pilots are offline post-hoc; no SFT arm uses judge-filtered data yet. (If gpt-oss-SVD filtering is later used to build SFT data, its 0.956 precision / false-positive rate must be reported.) | **low (today)** |
| 7 | Same-oracle circularity in the frontier diagnostic | The ref-244 "impossible" set is defined by the same codeforces suites used to grade SE solves. Unavoidable for this diagnostic; mitigated: two INDEPENDENT 16-draws agree on 243/244 hard-zeros, and grading-flake rate measured ≈ ±1 problem (spot re-executions 30/30 + 1 adjudicated flake). | **low** |
| 8 | code_contests extension | `manifest.json`: `cc_reference_pass: "not_validated"`; "93% gradeable / ~7% test-broken impossibles" are `RESULT-DEPENDENT` claims not re-verified here → cc "impossible 0/8" class is contaminated by broken tests to an unmeasured-here degree. | **medium (for cc claims)** |
| 9 | Benchmark-specific tests in prompts | No LCBv6 tests appear anywhere in training or generation. fb arm leaks *codeforces* tests only (see #2). | low |

## Answers to the audit questions

- **Oracle only for offline eval?** No — also for (a) training-data filtering/selection (disclosed,
  STaR-style) and (b) pool classification (saturated/impossible). Never inside generation prompts
  except the explicit fb arm.
- **Verifier labels in-loop?** No. **Judge labels in-loop?** No.
- **Train/eval overlap?** None detected (0/1,617 at 0.5 containment; disjoint platforms).
- **Selection-for-training vs final-eval oracle:** different test suites (codeforces vs LCBv6) — no shared oracle.

## Paper-safe clarifications (recommended wording)

1. "Evolution is verifier-free; hidden tests are used only for post-hoc grading and for selecting
   *training* data (rejection-sampling style), never inside generation prompts." (fb arm excluded or
   explicitly disclosed if used for datagen.)
2. "The held-out benchmark (LiveCodeBench-v6) shares no problems or platforms with the training pool
   (8-shingle containment 0/1,617)."
3. "Self-verification experiments are strictly test-free at selection time; test-based grading is used
   only to score the selections afterwards."

## TODOs

- If cc frontier claims will be made: validate cc test suites (`cc_reference_pass`) and quantify the
  test-broken fraction inside the 0/8 class before calling them "impossible".
- If judge-filtered SFT is run: keep LCBv6 untouched and report the 4.4% false-positive exposure.
- Semantic (embedding-level) train/eval dedup is a cheap robustness add-on for the paper.
