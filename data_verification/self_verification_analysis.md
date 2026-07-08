# Phase 6 — Self-verification / judge analysis (VERIFIED from raw run artifacts)

**Setup (verified from `run_config.json`s + pools code):** 100-problem pilot
(`self_verification_selection/pilot_100_ids.txt`), two candidate pools of 16
(`independent16` = svd_pilot_100x16.jsonl, assembled from independent draws;
`se_loop1_16` = dedicated SE-nofb loop1 run under `svd_pilot_100/se_nofb/`).
Judges never see tests. Oracle labels: `_v1pp_analysis/grades.json` (per-candidate full-pass,
produced by executing all 3,200 candidates), cross-checked against every run's own independent
grading pass — **1 disagreement in ~1,100 cross-checked selections** (cf-00000::ind16::14),
adjudicated by fresh double re-execution → the run cache was right; grading flake rate ≈ ±1 problem.
Scripts: `scripts/verify_selection.py`; tables: `tables/self_verification_analysis.csv`,
`selection_detail.json`, `selection_auc_addendum.json`; figure: `figures/verifier_by_bucket.png`.

## 6.1 Candidate selection (top1 = selected candidate full-passes oracle)

Recomputed from `selected.jsonl` + oracle labels; every run **matches its eval.json** (one ±0.01 flake, above).

| judge | selector | independent pool | SE-loop1 pool | notes |
|---|---|---|---|---|
| — | RANDOM (mean density) | **0.573** | **0.710** | recomputed from pool grades ✓ |
| — | ORACLE (any-correct) | **0.830** | **0.860** | recomputed ✓ |
| Qwen3-4B | SVD (absolute accept) | 0.27 | 0.29 | **below random** ✓ |
| Qwen3-4B | V1 (pairwise tournament) | 0.58 | 0.74 | ✓ (0.58 verified from sharded run 28/50+30/50) |
| Qwen3-4B | V1++ lite / edge (SE pool) | — | 0.73 / 0.70 | no gain over V1 |
| Qwen3-4B | LLM-verifier | 0.55 | (0.71 older run) | ≈ random |
| gpt-oss-120b | SVD | 0.65 | 0.64 | ✓ |
| **gpt-oss-120b** | **V1** | **0.80** | **0.81** | ✓ (≈ oracle 0.83/0.86) |

Gap-recovery framing (verified): gpt-oss V1 recovers (0.80−0.573)/(0.83−0.573) = **88%** of the
random→oracle gap on the independent pool, (0.81−0.71)/(0.86−0.71) = **67%** on the SE pool
(Qwen3-4B V1: 3% / 20%). PROJECT_SUMMARY §3 table **fully verified**.

Per-candidate ranking quality (AUC; per-problem averaged — this is the method behind the summary's
numbers): Qwen SVD **0.366/0.453** (pool mean ≈ 0.41 — "anti-correct" ✓), Qwen V1 0.634/0.620 ("0.63" ✓),
gpt-oss SVD 0.826/**0.713** ("0.71" ✓ = SE pool), gpt-oss V1 0.909/**0.801** ("0.81" ✓ = SE pool).
Pairwise accuracy on mixed (correct-vs-incorrect) pairs from raw win-matrices: Qwen V1 0.751/0.622;
gpt-oss V1 **0.906/0.832**.

Difficulty dependence (figure; SE pool buckets by true correct count): selection value concentrates on
low/mid buckets; on near-saturated buckets every selector ≈ random. (Summary's "hard 2–8: 4B-V1 0.50
vs random 0.30, gpt-oss 0.79" uses a similar split — direction verified; see
`tables/selection_bucket_data.json` for our exact bucket numbers.)

## 6.2 Filtering quality (keep-all-correct use, for SFT data)

Accepted-set metrics vs oracle (recomputed from `accepted_candidate_ids`):

| judge (SVD accepts) | pool | precision | recall | F1 |
|---|---|---|---|---|
| Qwen3-4B | ind / SE | 0.546 / 0.824 | 0.123 / 0.136 | 0.20 / 0.23 |
| **gpt-oss-120b** | ind / SE | **0.967 / 0.956** | **0.677 / 0.636** | 0.80 / 0.76 |

Summary's "gpt-oss SVD = 0.96 precision / 0.64 recall" **verified** (SE pool).

## 6.3 Saturation judgment (test-free density estimation)

Estimated count = #accepted (SVD) vs true correct count, recomputed per problem:

| judge | pool | Pearson r | max over-claim (est−true) | saturation confusion @≥8/16 (TP/FP/FN/TN) |
|---|---|---|---|---|
| Qwen3-4B | ind / SE | 0.101 / 0.187 | 8 / 6 | 5/1/55/39 · 8/0/68/24 (useless) |
| gpt-oss-120b | ind / SE | 0.774 / **0.647** | 8 / **3** | 41/1/19/39 · **48/0/28/24** |

Summary's "r=0.65, never over-claims by ≥5" **verified on the SE pool** (r=0.647, max over-claim 3);
on the independent pool r is *better* (0.774) but one problem is over-claimed by 8 — the "never ≥5"
phrasing only holds for the SE pool. As a saturation detector at ≥8/16, gpt-oss SVD is
high-precision (FP ≤1/100) with recall 0.63–0.68. V1/ranking cannot do this task (a tournament always
produces winners) — structurally confirmed: V1 runs emit no accept-set, and win-counts don't estimate density
(V1++ accept-sets have recall 0.02–0.13).

## 6.4 Answers to the phase questions

- **Is the verifier useful for candidate selection?** Pairwise (V1) with a strong judge: yes, ≈oracle
  (0.80/0.81 vs 0.83/0.86). With the 4B itself: only on the SE pool and only via pairwise (0.74);
  absolute self-verification (SVD) is below random.
- **Is it strong enough for saturation judgment?** Only gpt-oss SVD (absolute), r≈0.65–0.77,
  essentially-zero false-saturated rate at the ≥8/16 threshold.
- **Does the 4B verify itself reliably? NO** — verified (AUC ≤0.45 absolute, ≈0.62–0.63 pairwise).
- **How close is the strong judge to oracle?** 88% / 67% of the random→oracle gap (top1).
- Caveat: all of this is a 100-problem pilot on one dataset; judge = different model family
  (gpt-oss-120b, 30× params) — "self"-verification claims should be scoped to the 4B rows.
