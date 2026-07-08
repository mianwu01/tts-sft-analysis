# Phase 7 — Offline curriculum / stopping-rule simulation (existing loop data only)

Simulated on the verified se16 per-problem trajectories (loop0→1→2; 1,093 problems; evolution budget
= 34,976 generations for loops 1+2). Cumulative-unique bookkeeping from per-candidate grades
(`tables/per_candidate_grades.jsonl.gz`). Decisions use only information available at decision time.
Script: `scripts/stopping_sim.py`. Table: `tables/curriculum_stopping_simulation.csv`.
**This is an offline what-if; no pipeline was modified and no curriculum experiment has been run.**

| rule | evolved @l1/@l2 | inference saved | coverage (any-of) | unique retained | frontier-58 kept | boundary kept @l2 |
|---|---|---|---|---|---|---|
| R0 full 2-loop run | 1093/1093 | 0% | 907 | 22,894 | 58 | 100% |
| R1 stop on per-problem density drop | 1093/996 | 4.4% | 907 | 22,285 | 58 | 90% |
| R2 stop when no new unique this loop | 1093/853 | 11.0% | 887 | 22,834 | **38 (loses 20)** | 95% |
| R3 = R2 + allow newly-solved to continue | 1093/853 | 11.0% | 887 | 22,834 | **38 (loses 20)** | 95% |
| R4 boundary-only (drop 0 AND 9-15) | 323/323 | **70.4%** | 850 | 12,258 | **1 (loses 57!)** | 100% |
| **R5 drop 9-15 only (keep 0-bucket exploration)** | 566/566 | **48.2%** | **907** | 12,531 | **58 (loses 0)** | 100% |
| R6 = R5 + R1 per-problem stop | 566/535 | 49.6% | 907 | 12,473 | 58 | 90% |

## Verified take-aways (facts of the simulation)

1. **The winning offline rule is R5**: freeze the near-saturated bucket (9-15/16 at loop0; 527
   problems) after loop0 and keep evolving everything else — **48% of evolution compute saved with
   ZERO loss of coverage or frontier problems**. The dropped unique solutions (22.9k → 12.5k) are
   overwhelmingly extra duplicates-adjacent density on already-easy problems — irrelevant for
   best-per-problem SFT (which keeps 1/problem) and for coverage.
2. **A pure boundary curriculum (R4, dropping the 0-bucket) is a frontier catastrophe**: it saves 70%
   but forfeits 57 of the 58 beyond-frontier solves — the entire "SE reaches new problems" result
   lives in the 0/16 bucket. Any RL/evolution curriculum must keep a hard-tail exploration allocation.
3. **"Stop when dry" rules (R2/R3) are subtly dangerous**: 20 of the 58 frontier problems produce
   their first correct solution only at loop2 after a completely dry loop1 — a no-new-unique stop
   kills exactly the late frontier discoveries, for only 11% savings.
4. R1 (stop on density decrease) is safe but nearly free-of-savings (4.4%) — density rarely drops
   before loop2 at this depth.
5. All rules assume best-so-far outputs are retained on disk (they are — per-loop checkpoints), so
   "worsened" loops never destroy data for SFT; they only waste compute.

## Caveats

- Only 2 evolution loops exist; rules that shine at deeper horizons (e.g. R1/R2) are under-tested.
- Oracle counts are used for the bucket decision. A deployable test-free version would use gpt-oss SVD
  estimated counts (Phase 6: r=0.65–0.77 vs truth, over-claim ≤3 on the SE pool) — expected to
  approximate R5 well because R5 only needs a coarse ≥9/16 test, but **that variant has not been run**.
- These numbers are simulation over an already-collected run; a live curriculum changes the
  recombination inputs and could differ.
