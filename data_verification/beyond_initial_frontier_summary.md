# Phase 2 — Problems beyond the initial direct-sampling frontier (VERIFIED)

**Definition used:** initial correct count = 0 (out of the initial 16 direct samples) AND ≥1 correct
candidate in a later SE loop population, under oracle/gold-test full-pass grading.
Both frontier definitions are listed per problem in
`tables/beyond_initial_frontier_problems.csv` (`ref244` = reference independent-16 hard-zeros;
`run243` = this-run loop0 hard-zeros; overlap 243/244).

Sources: recomputed per-problem counts (`tables/recomputed_se16_per_problem.csv`, verified vs raw
checkpoints + grading cache with 0 misses, cache spot-checked 30/30 by re-execution).
Script: `scripts/frontier_aggregates.py`.

## Counts (ref-244 definition)

| quantity | count |
|---|---|
| initially unsolved (0/16 reference draw) | 244 |
| solved by SE loop1 population | **38** |
| solved by SE loop2 population | **51** |
| solved by loop2 but NOT loop1 (newly cracked at loop2) | **20** |
| solved at loop1 but lost at loop2 (`update: replace` erosion) | 7 |
| cumulative union (any SE loop ≤2) | **58 (23.8%)** |
| solved by the fresh independent-16 draw (se16 loop0) | 1 |
| solved by independent-32 (both draws) | **1** |
| never solved by anything on disk | 186 |

run-243 definition: loop1 37, loop2 50, union 57, second-independent-draw 0, independent-32 0.

- First-solved-loop distribution (ref-244): loop0 1, loop1 37, loop2 20, never 186.
- Per-problem rows include: both frontier definitions, all loop correct-counts, first solved loop,
  loop3 count where fully graded, and the source shard checkpoint dir (candidate text is in
  `<shard>/ck/<run>_loop<L>.json` → `problems[i].candidates`).

## Representative examples (all verified from checkpoints + oracle grading)

| problem | ref16 | loop0 | loop1 | loop2 | reading |
|---|---|---|---|---|---|
| `cf-00002` (mex function game) | 0 | 0 | 1 | 4 | cracked at loop1, densifies at loop2 |
| `cf-00028` (rectangular pond) | 0 | 0 | 4 | 9 | strongest densification after crack |
| `cf-00010` (directed graph, multi-edges) | 0 | 0 | 0 | 1 | needs TWO evolution loops to crack |
| `cf-00058` (logical OR matrix) | 0 | 0 | 1 | 0 | cracked then LOST (replace-erosion case) |

(Problem text: `data/openthoughts114k_codeforces_stdin_clean.jsonl` by `seed_id`; first correct
candidate: the loop-1/2 checkpoint of the shard listed in the CSV.)

## Facts only — no broad claims

- These counts show the loop1/loop2 populations contain correct solutions for 58 problems where
  16 (and 32) direct samples contain none.
- They do NOT by themselves say anything about SFT value, generalization, or non-code domains.
- loop3: on its 258 fully-graded problems, 2 newly solved vs 3 lost (net −1) → no evidence of further
  frontier movement at loop3 (partial data).
