# Phase 5 — SFT pass@1 / pass@K verification (VERIFIED from raw per-problem evals)

Sources: `outputs/sweep_lcbv6/<arm>_ck*/​{base,sft}_per_problem.jsonl` (131 LCBv6 problems × 16
samples each, full-test grading, shared base cache) — pass@k recomputed with the unbiased estimator;
every arm's numbers **match its `compare_summary.json`** and the base rows are **byte-identical across
all 8 arm evals**. Training-data provenance from `training_metadata.json` inside each checkpoint +
`data/sft/*.summary.json`. Script: `scripts/verify_sft_passk.py`.
Table: `tables/sft_passk_analysis.csv`. Plot: `figures/sft_passk_plot.png`.

## Verified table (LCBv6 all_131; raw generation — NO test-time selection anywhere in this table)

| arm | format | source | selection | train rows (probs) | pass@1 | pass@4 | pass@16 | cap-hit |
|---|---|---|---|---|---|---|---|---|
| **base (untrained)** | — | — | — | — | **0.4132** | 0.4822 | 0.5267 | 44.3% |
| E3b | code-only | loop0 indep | best/prob | 804 (804) | **0.4361** | 0.5337 | 0.5954 | 24.0% |
| E1b | code-only | **loop1 SE (pop16)** | best/prob | 872 (872) | **0.4370** | 0.5276 | 0.5878 | 26.2% |
| E3 | code-only | loop0 indep | all-unique | 3,889 (804) | 0.4103 | 0.5041 | 0.5649 | 26.0% |
| E1 | code-only | **loop1 SE (pop16)** | all-unique | 9,025 (872) | 0.3965 | 0.4938 | 0.5573 | 19.1% |
| E2 | real-CoT | loop0 indep | all-unique | 1,846 (480) | 0.1999 | 0.2533 | 0.2824 | **77.9%** |
| E4 | real-CoT | loop0 indep | best/prob | 371 (371) | 0.2032 | 0.2600 | 0.2901 | **76.8%** |
| final-only | no-think | loop1 SE (pop8) | all-unique | 16,556 | 0.1312 | 0.2162 | 0.2824 | 0.0% |

(ck282 of final-only: 0.1350 — same story. `run1_A_lora_ck424` eval was never completed — excluded.)

## Verified findings

1. **Best-per-problem selection of training data is the only pass@1 lever that beats base**:
   E3b +0.023, E1b +0.024 (vs base 0.413). All-unique *hurts* relative to best (E3 0.410, E1 0.397).
2. **SE source ≈ independent source at matched selection** — E1b 0.4370 vs E3b 0.4361 (Δ=0.0009,
   1 problem-sample equivalent ≈ noise); at all-unique, loop0 actually *beats* loop1 (0.4103 vs 0.3965).
   Note the SE arm has 68 more covered problems (872 vs 804, incl. the hard-tail solves) and 2.3× the
   unique data — none of it shows on LCBv6 transfer. (Caveats from the summary §2 — tiny pilot, one
   benchmark, loop1-only — are fair; but at THIS scale the null is verified.)
3. **pass@k: every code-only arm beats base at k≥2, including all-unique arms** — e.g. E3 pass@16
   0.5649 vs base 0.5267. SFT's most robust effect here is *reach*, not pass@1.
4. **Real-CoT collapse verified and mechanistically explained by cap-hits**: E2/E4 ≈ 0.20 pass@1 with
   **77–78% of samples hitting the 40,960-token cap** (vs base 44%, code-only 19–26%). Best-per-problem
   selection does NOT rescue real-CoT (0.2032). Training on the model's own full reasoning makes it
   think longer and truncate; training code-only nearly halves cap-hits vs base.
5. **final-only (no think tags) is catastrophic** (0.131) — trained the model to skip thinking.
6. **Durable vs selection, cleanly separated:** everything in this table is a *durable weight-level*
   effect measured by raw generation. The +0.023/+0.024 arms fold **oracle-verified, consensus-shortest**
   training targets back into weights. No verifier/judge/test-time selection contributes to any number
   here. (Test-time selection gains live in Phase 6 and are 3–10× larger at pass@1 on codeforces pools —
   do not mix the two.)

## Bookkeeping notes

- E1/E1b train files are the converted (`build_empty_think_sft.py`) versions of
  `cleaned_se_loop1_16_nonsat_fullpass_{unique,best}` — i.e. **pop-16 se16 loop1**, 9,025 unique
  candidates / 872 problems (the cleaning pipeline's 9,025 vs our grade-derived 9,015 unique differ by
  10 rows ≈ 0.1%; cleaning uses its own verify pass — immaterial but noted).
- E4: config and file agree at 371 rows (the earlier "371 vs 504" concern is resolved on disk).
- Missing cells for a full 2×2×2: loop1-all real-CoT and loop1-best real-CoT (blocked: loop1 reasoning
  is recombination-framed — "the candidate solutions provided…" — unusable as CoT targets); loop2-source
  SFT; non-LCBv6 (in-distribution codeforces) eval of any arm. Multi-loop + bigger-pool test = cf_cc run.
- Oracle-selected / verifier-selected *eval-time* numbers do not exist for these SFT checkpoints (TODO
  if wanted: run the Phase-6 selector over SFT-model generations).
