# FINAL REPORT — TTS / SqueezeEvolve Data Verification

_2026-07-02. Auditor: Claude (read-only over the repo; all writes under
`/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/`). Repo:
`/mnt/cpfs/yangboxue/opsd/TTS/tts-sft`. Method: every headline number recomputed from raw
checkpoints / result records / grading caches by scripts in `scripts/` here; the caches themselves
spot-checked by re-executing candidates on the full hidden tests._

## 1. Executive summary

The project's core empirical story **survives verification and gets sharper**. From raw data:
(a) verifier-free SE evolution solves 38→51→58(cumulative) of the 244 problems where independent
sampling solves nothing, while a compute-matched independent-32 baseline solves exactly **1** and
adds **zero** aggregate coverage — the strongest verified form of the "not just more sampling" claim;
(b) gains concentrate in boundary buckets, the near-saturated bucket actively degrades (unique
density falls at loop2), and an offline stopping rule ("freeze ≥9/16") halves evolution compute at
zero cost — but a *pure* boundary curriculum would forfeit 57/58 frontier solves;
(c) SFT fold-back works only via oracle-best-per-problem selection (+0.023/+0.024 pass@1, lifts all
pass@k), with SE-source vs independent-source a verified wash *at this pilot scale*;
(d) test-free selection reaches ≈oracle only with a strong judge (gpt-oss V1 0.80/0.81 vs oracle
0.83/0.86); the 4B cannot verify itself; only absolute (SVD) judging can estimate saturation
(r=0.647, over-claim ≤3 on the SE pool).
Two upstream **labeling errors** were found and corrected (the "32-sample BoN" mislabel; the
"~1 independent" number citing the wrong artifact), plus one grading flake adjudicated.

## 2. Verified numbers

All recomputed independently from raw files (scripts + tables in this directory; se16 recomputation
matched the repo pipeline row-for-row: 1,093 problems × loops 0-2, **0 cache misses, 0 diffs**;
30/30 random candidates re-executed reproduce their cached verdicts; pop-8 reachability json
reproduced exactly; every SFT arm matches its `compare_summary.json`; every selection run matches
its `eval.json` except one adjudicated flake).

| # | number | value | source table |
|---|---|---|---|
| 1 | se16 solvable /1,093 (l0/l1/l2) | 850 / 872 / 877 | `tables/frontier_movement.csv` |
| 2 | se16 pass@1 (l0/l1/l2) | 0.4676 / 0.6042 / 0.6348 | same |
| 3 | se16 pop pass@16 (l0/l1/l2) | 0.7777 / 0.7978 / 0.8024 | same |
| 4 | unique full-pass (l0/l1/l2) | 7,584 / 9,015 / 9,085 | `recompute_se16_summary.json` |
| 5 | ref-244 hard-zeros solved by SE l1 / l2 / union | **38 / 51 / 58** | `tables/beyond_frontier_summary.json` |
| 6 | …by independent-32 (two 16-draws) | **1** (0/243 on run-definition) | same |
| 7 | two independent draws agree on hard-zeros | 243/244 | same |
| 8 | aggregate coverage: indep-16→indep-32 | 850 → **850** (+0) | `tables/compute_matched_detail.json` |
| 9 | SE at 32 budget: loop1-pop / union | 872 / **887** | same |
| 10 | pop-8 matched-16 (1,617): SE vs BoN | 1,384 vs 1,373 (only_SE 28 / only_BoN 17) | same (recomputed exactly) |
| 11 | loop3 partial (258 fully-graded) | 214→213 solvable, net **−1** | `frontier_movement_detail.json` |
| 12 | `pass16_by_id.json` provenance | = pop-8 l0∪l0b grades, 1,617/1,617 match | `tables/pop8_pass16_recompute.csv` |
| 13 | SFT: base pass@1/@4/@16 | 0.4132 / 0.4822 / 0.5267 (base identical across all 8 arm evals) | `tables/sft_passk_analysis.csv` |
| 14 | SFT best arms (loop0-best / loop1-best) | 0.4361 / 0.4370 pass@1; 0.5954 / 0.5878 pass@16 | same |
| 15 | SFT all-unique (loop0/loop1) | 0.4103 / 0.3965 | same |
| 16 | real-CoT collapse + mechanism | 0.1999–0.2032; **77–78% cap-hit** (base 44%, code-only 19–26%) | same |
| 17 | selection RANDOM/ORACLE (ind / SE pools) | 0.573 & 0.830 / 0.710 & 0.860 | `tables/selection_detail.json` |
| 18 | Qwen3-4B SVD / V1 top1 | 0.27 & 0.29 / 0.58 & 0.74 | same |
| 19 | gpt-oss-120b SVD / V1 top1 | 0.65 & 0.64 / **0.80 & 0.81** | same |
| 20 | gpt-oss SVD precision/recall (SE pool) | 0.956 / 0.636 | same |
| 21 | gpt-oss SVD density corr (SE pool) | r = 0.647, max over-claim 3 | same |
| 22 | AUC (per-problem avg; method identified) | Qwen SVD 0.366/0.453, V1 0.634/0.620; gpt-oss SVD 0.826/0.713, V1 0.909/0.801 | `tables/selection_auc_addendum.json` |
| 23 | stopping sim: freeze-9-15 rule | 48.2% saved, 58/58 frontier kept, coverage 907 | `tables/curriculum_stopping_simulation.csv` |
| 24 | stopping sim: pure-boundary rule | 70.4% saved, **1/58 frontier kept** | same |
| 25 | cc loop0 saturation (aggregation) | 3,020 / 2,258 / 1,229 (non-sat 3,487) — matches report | `tables/cc_saturation_recompute.json` |
| 26 | train/eval contamination | 0 flagged /1,617 (8-shingle ≥0.5); LCBv6 = 82 atcoder + 49 leetcode | leakage_audit.md |

## 3. Unverified or missing numbers

- **independent-48 / independent-64 baselines** — do not exist; loop2/loop3 are not compute-matched.
  Exact recipes + cost estimates in `compute_matched_baselines.md` §3.
- **loop3 full grading** — 2,868/7,776 candidates ungraded (only 258/486 problems complete);
  finish with `python scripts/grade_se16_loops.py --max-loop 3` (CPU-only).
- **cf_cc loop1 frontier** — generation mid-run; all §4-of-summary SE-on-cc claims are pending.
- cc "~7% test-broken impossibles" and "gradeable ≈13,400 / 19,904" — not re-verified here
  (aggregation level only); `cc_reference_pass: "not_validated"` in the manifest.
- gpt-oss judge cost claims (~0.9 s/call, 4× GPUs) — infra claims, not re-measured.
- Legacy Thinking-2507-era results (math SE, cstrip SFT) — out of scope; treated as historical.
- The difficulty-split selection numbers quoted in the summary ("hard 2–8: 0.50 vs 0.30 / 0.79") use
  a bucketing we approximated but did not exactly reproduce (our buckets in
  `tables/selection_bucket_data.json` confirm the direction).

## 4. Frontier movement — see `frontier_movement.md`

SE moves the initial direct-sampling frontier: +22 problems at loop1, +27 by loop2 (population),
+57 union (coverage 850→907) on 1,093; on the hard-zero 244 it is 38/51/58 vs 1 for matched
independent. Diminishing: loop1→2 net +5 solvable; partial loop3 net −1. Erosion is real
(update=replace loses 7 loop1 solves at loop2; 15-19 problems/loop lose all correct candidates) but
harmless for datagen since all loops are checkpointed.

## 5. Beyond initial direct-sampling frontier — see `beyond_initial_frontier_summary.md`

Full per-problem listing `tables/beyond_initial_frontier_problems.csv` (244 rows, both frontier
definitions, first-solved loop, source checkpoints). 20 problems crack only at loop2 (deep-search
value); 186/244 never solved by anything on disk (capability limit). 4 worked examples included.

## 6. Compute-matched direct-sampling baselines — see `compute_matched_baselines.md`

The **key audit**: budgets verified from configs (se16: 16 gen/loop → cum 16/32/48; pop-8: 8/loop).
The repo's only labeled "compute-matched" artifact is the pop-8 matched-16 run (verified exact) —
but it was **mislabeled** "matched-32" in `frontier_report.json` and "32-sample" in the Jul-1
summary. This audit adds the cleaner matched-32 comparison (independent-32 = union of the two
16-draws vs SE cum-32): SE +22/+37 aggregate, +37/244 hard tail. Verdict: **at matched compute,
SE ≠ more sampling — verified**, with the aggregate edge modest and the hard-tail edge dramatic.

## 7. Bucket / curriculum analysis — see `bucket_analysis.md` + `curriculum_stopping_simulation.md`

Gains concentrate in buckets 1/2-4; 5-8 done after one loop; 9-15 churns and loses unique density at
loop2; 0-bucket thin but sole frontier source. Offline rules: freeze-9-15 = 48% compute for free;
pure-boundary = frontier catastrophe; stop-when-dry kills the 20 late cracks. All descriptive — no
curriculum experiment run.

## 8. SFT pass@1 / pass@K — see `sft_passk_analysis.md`

Durable-vs-selection cleanly separated. Durable: best-per-problem code-only SFT beats base at every k
(0.436-0.437 @1; 0.588-0.595 @16); SE-vs-independent source **null at matched selection** (Δ0.001) in
this tiny cross-platform pilot; all-unique dumping hurts pass@1 but still lifts pass@k≥2; real-CoT
collapse is mechanistically a truncation effect (77-78% cap-hits). No eval-time selection anywhere in
these numbers.

## 9. Self-verification / judge analysis — see `self_verification_analysis.md`

Verifier capability, not method, is the limiter (summary's claim **verified**): strong-judge pairwise
≈ oracle (88%/67% of the random→oracle gap); 4B self-verification below random absolute, weak
pairwise; only absolute SVD can estimate density/saturation (gpt-oss r 0.65-0.77, FP≤1/100 at ≥8/16);
ranking structurally cannot. One grading flake found and adjudicated (eval.json right, grades.json
stale) — noise ≈ ±1 problem.

## 10. Oracle-use and leakage audit — see `leakage_audit.md`

Headline arms: **no tests inside generation** (verified configs: `livecodebench-aggregate`,
`evaluation: livecodebench-none`, verifier-free). Oracle is used for (disclosed) train-side
selection and pool classification only. fb arm leaks tests into prompts by design — not in any
headline number; disclose if its outputs feed SFT. Train/eval: 0 overlap flagged, disjoint platforms.
Judges never see tests. Main open risk: cc test validity for future cc claims.

## 11. Sewon meeting recommendation

Use `deck/sewon_meeting_slides.pptx` (5 slides) + `deck/sewon_meeting_deck_notes.md`.
Lead with the three-way pass@K terminology, then the hard-tail figure (1 vs 38/51/58), then the
bucket/stopping story (incl. the R4 warning — it directly seeds the curriculum discussion), then the
SFT table with the selection-vs-durable separation, then the six questions (notes file). Everything
on the slides is verified; the only forward-looking content (cc loop1, RL plans) is labeled pending.

## 12. Claims safe to make

1. "On 244 problems unsolved by 16 independent samples, verifier-free evolution produces correct
   solutions for 58 (23.8%) within two loops, while doubling the independent sample budget to 32
   yields 1 — same model, same sampler, oracle-graded." (And the two-draw 243/244 agreement.)
2. "At matched 32-generation budget, evolution's coverage is 887 vs 850 for independent sampling;
   at matched 16 (pop-8 replication), 1,384 vs 1,373 — the aggregate edge is modest; the hard-tail
   edge is not."
3. "Frontier gains concentrate at the difficulty boundary; the near-saturated bucket degrades
   (unique density falls) under further evolution; freezing it halves evolution compute at zero cost."
4. "A boundary-only curriculum without hard-zero exploration would forfeit 57/58 frontier solves."
5. "Folding back via SFT: oracle-best-per-problem selection lifts pass@1 and every pass@k; the
   training-data *source* (SE vs independent) is indistinguishable at this pilot's scale."
6. "Real chain-of-thought is a bad SFT target here (0.20; 78% token-cap truncation); empty-think +
   code-only is the working recipe."
7. "Test-free selection reaches ≈oracle with a strong judge (0.80/0.81 vs 0.83/0.86); the 4B cannot
   verify itself; only absolute verification can estimate saturation (r≈0.65, over-claim ≤3)."

## 13. Claims to avoid

- Any "beats/exceeds pass@K" phrasing without the three-way qualification; never vs the
  current-population oracle.
- **"Compute-matched Best-of-N (32-sample)"** for the pop-8 comparison — it is matched-16 and a
  different run from the headline pop-16 frontier (upstream mislabel; corrected here).
- "Independent same-budget solves ~1 **of the 244**" citing `only_BoN=17` — right conclusion, wrong
  artifact; cite the independent-32 recomputation instead.
- "SE data is (or is not) a better SFT target" as settled — the pilot is a null at small scale with
  known confounds; the cc run decides.
- Any cc frontier/SE claim (loop1 mid-run) or cc "impossible" counts without the test-broken caveat.
- "SE +11 net coverage" as the headline compute-matched result (it is the weakest of the three
  verified comparisons; the 887-vs-850 and 38-vs-1 numbers are the defensible ones).
- Loop3 conclusions beyond "partial data, net −1" (258/486 problems graded).
- Anything implying self-verification works in-loop today (never used in-loop), or that the 4B can
  self-verify.

## 14. Next experiments (ranked)

1. **cf_cc loop1 grade→frontier** (running) — the scale/diversity replication of §4-6 here.
2. **independent-48 arm** (1 node-day class) — compute-match SE loop2; recipe in
   `compute_matched_baselines.md`.
3. **Boundary-set RL (GRPO) with a hard-zero exploration slice** vs uniform-set RL, compute-matched —
   the curriculum hypothesis test AND the unambiguous weight-level fold-back.
4. **Judge-filtered SFT at scale** (gpt-oss SVD, precision 0.956) on the no-test pool — the test-free
   scaling story; manifest template ready (`manifests/verifier_filtered.csv`).
5. **EFT ablations from the manifests** (final-only vs state-chain vs pos/neg pairs) — blocked on
   deciding whether state-chains are an acceptable proxy for true lineage (SE client doesn't log
   parents; see `manifests/manifest_summary.md`).
6. Finish loop3 grading (CPU-only) to close the loop-depth question.
7. Re-run this audit's scripts after any new generation (they are idempotent and cache-only).
