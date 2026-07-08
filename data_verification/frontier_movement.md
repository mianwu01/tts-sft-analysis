# Phase 1 — Frontier movement (VERIFIED from raw data)

**Experiment:** se16 — canonical SqueezeEvolve (`livecodebench-aggregate` recombination, verifier-free,
no test feedback in generation), pop-16, base `Qwen/Qwen3-4B`, on the 1,093 non-saturated codeforces
problems. Oracle = full hidden codeforces tests (6 s/test).

**Verification method (all numbers below recomputed independently of the repo pipeline):**
- Inputs: 13 shard checkpoint sets `outputs/.../se16/{sh0-4,sh7,sh8,redo_sh0-5}/ck/*_loop{0,1,2,3}.json`
  + `outputs/grading_cache/se16.jsonl` (49,863 verdicts) + `out.jsonl` id order + seed pool tests.
- Script: `analysis_outputs/data_verification/scripts/recompute_se16_counts.py` then `frontier_aggregates.py`.
- Shard union = exactly 1,093 unique problems, 0 duplicates. **0 cache misses** for loops 0–2
  (all 3×17,488 candidates graded). Repo CSV `per_problem_correct_counts.csv` reproduced with
  **0 differing rows**.
- Cache honesty: 30 random candidates (20 cached-pass / 10 cached-fail) **re-executed** on the full
  hidden tests → 30/30 verdicts (and per-test pass counts) reproduced
  (`scripts/spot_check_cache.py`, `tables/spot_check_cache.json`).

## Headline table (tables/frontier_movement.csv)

| setting | samples this stage | cumulative budget | solvable (any-of-pop) | pass@1 | pass@16(pop) | solves of ref-244 | solves of run-243 |
|---|---|---|---|---|---|---|---|
| reference independent-16 (pop-8 l0∪l0b, 1,617 probs) | 16 | 16 | 1,373 /1,617 (849 /1,093 non-sat) | — | — | 0 (defines set) | **0** |
| SE loop0 = fresh independent-16 draw | 16 | 16 | 850 /1,093 | 0.4676 | 0.7777 | 1 | 0 (defines set) |
| **independent-32 (union of the two 16-draws)** | 32 | 32 | **850 /1,093** | — | — | **1** | **0** |
| SE loop1 (evolved pop) | 16 | 32 | 872 /1,093 | 0.6042 | 0.7978 | **38** | **37** |
| SE≤loop1 union (l0∪l1) | — | 32 | 887 /1,093 | — | — | 38 | 37 |
| SE loop2 (evolved pop) | 16 | 48 | 877 /1,093 | 0.6348 | 0.8024 | **51** | **50** |
| SE≤loop2 union | — | 48 | 907 /1,093 | — | — | **58** | **57** |
| SE loop3 (partial: 258 fully-graded probs) | 16 | 64 | 213 (vs 214 at loop2, same subset) | — | — | see caveat | — |

- Actual K in loop0: **16** (verified `ncand`=16 for every problem, every loop).
- Initially-unsolved problems: **two definitions, both reported** —
  - **ref-244**: 0/16 under the reference independent-16 (this is the `problem_classes/impossible` set;
    provenance **verified**: recomputed pop-8 loop0∪loop0b correct-counts == `pass16_by_id.json` for 1,617/1,617).
  - **run-243**: 0/16 under se16's own loop0. Overlap: 243 of 244 (the two independent draws agree
    almost exactly on which problems are hard-zero).

## Answers to the Phase-1 questions

1. **Does SE solve problems that initial direct sampling did not solve? — YES (verified).**
   Of the 244 reference hard-zeros: 38 solved in the loop1 population, 51 in the loop2 population,
   58 cumulative (37/50/57 on the run-243 definition). Loop2-only adds 20 new; 7 loop1-solves are lost
   at loop2 (population `update: replace` — union numbers keep them; all outputs remain on disk).
2. **Does SE outperform compute-matched direct sampling on the hard tail? — YES (verified), with a
   sharper number than the summary claims:** at matched **32** total samples/problem, independent-32
   solves **1/244** (ref definition; 0/243 on run definition) vs SE-32's **38**. The second independent
   16-draw adds ~zero anywhere: aggregate coverage 850→850 (non-sat), i.e. independent sampling has
   effectively saturated by 16 samples on this pool, while SE keeps finding new problems.
3. **Which comparisons are verified / missing?**
   - VERIFIED: loop0/1/2 populations (all candidates graded, cache spot-checked); independent-16 ×2;
     independent-32 (union); pop-8 SE-vs-BoN at matched-16 (recomputed exactly, see Phase 3).
   - PARTIAL: loop3 — checkpoints exist for 486 problems, but only 258 problems have all 16 candidates
     in the grading cache (2,868/7,776 candidates never graded). On the 258 fully-graded: solvable
     214 (loop2) → 213 (loop3), 2 newly solved, 3 lost → **net −1** (the summary's "244-problem sample,
     net −1" is directionally right; the subset is actually 258).
   - MISSING: independent-48 / independent-64 baselines (needed to compute-match loop2/loop3);
     see compute_matched_baselines.md for exact commands.

## Provenance notes / labeling corrections

- `PROJECT_SUMMARY_2026-07-01.md` §1 table (850/872/877, 0.468/0.604/0.635, 0.778/0.798/0.802) —
  **all reproduced exactly**. Unique-density: 7,584 → 9,015 → 9,085 unique full-pass (43.4%→51.5%→51.9%
  of 17,488) — reproduced; loop1→loop2 unique gain is +0.4pp while raw density gains +3.1pp
  (duplicates) — **confirmed**.
- "Independent same-budget solves ~1": the underlying artifact (`impossible244_rollup.json`) cites the
  pop-8 `only_BoN` count, which is NOT the right quantity (different problems, circular set definition).
  The **correct verified statement** is: a second independent 16-draw (making independent-32) solves
  1/244 (or 0/243) of the hard-zeros; SE at the same 32-budget solves 38 (37). The claim survives —
  on cleaner evidence than the artifact it cited.
- All numbers here are oracle/gold-test full-pass; no verifier or judge labels are involved anywhere
  in this phase.
