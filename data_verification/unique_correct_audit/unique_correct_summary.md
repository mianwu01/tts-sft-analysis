# Unique-correct audit — is the se16 bucket heatmap measuring diversity or copy-amplified density?

**Date:** 2026-07-02 · **Scope:** se16 pop-16 run, loops 0/1/2, n=1,093 non-saturated
codeforces problems · **Grading:** oracle full-test, cache-only (0 executions, 0 cache misses).

## TL;DR

The current slide heatmap ("se16: mean correct count (of 16) per initial-difficulty bucket per
loop") counts **raw oracle-correct candidates and is NOT deduplicated**. This audit deduplicates
the correct candidates (exact + canonical) and separates true diversity from copy amplification.

Findings:

1. **Duplication is real and grows with loops, but is modest.** Pooled duplication factor
   (raw ÷ canonical-unique, solved problem-loops) rises **1.10 → 1.25 → 1.33** across loops 0→1→2;
   the fraction of correct candidates that are canonical duplicates rises **9.1% → 20.1% → 24.8%**.
   So ~¾ of correct candidates at loop2 are still *distinct* programs.

2. **On EASY problems the slide's loop-over-loop "gain" is mostly duplication.** For the 9-15/16
   bucket, raw mean rises 12.9 → 14.4 → 14.5, but **canonical-unique mean FALLS 11.6 → 11.5 → 10.6**.
   The loops re-emit the same correct programs more often without adding distinct ones.

3. **On HARD problems the loops add genuine diversity, not copies.** For the 0/16, 1/16, 2-4/16
   buckets, raw AND canonical-unique both rise strongly (e.g. bucket 1/16 canonical-unique
   1.0 → 3.1 → 4.6; hard-zero 0 → 0.35 → 0.76).

4. **The frontier (problem-level solved) claim is ROBUST to duplication.** In the 0/16 hard-zero
   bucket, per-loop solved counts are **0 → 37 → 50**; 57 are ever solved. Of the 50 hard-zero
   problems solved at loop2, **49 carry a canonical solution that did not exist (as a correct
   program) at loop1** — only 1 (`cf-00826`) is pure re-emission. A "solve" is *any-of-N correct*,
   so duplicate amplification **cannot** create a solve from zero; every solved problem has ≥1
   canonical-unique by construction. **The frontier claim does not depend on duplicate amplification.**

**Bottom line for the slide:** the heatmap is honest as a *density* view but the label overstates
loop gains on easy problems. Relabel it "correct-candidate density (not deduplicated)" and add the
canonical-unique heatmap beside it. The frontier / hard-zero story is unaffected.

---

## A. Reproduced raw heatmap (matches the current slide)

Mean **raw** correct-candidate count (of 16), bucketed by loop0 raw-correct count.
Figure: `figures/raw_correct_heatmap.png`. Source table: `tables/raw_vs_unique_by_bucket_loop.csv`.

| loop0 bucket | n | loop0 | loop1 | loop2 |
|---|---|---|---|---|
| 0/16   | 243 | 0.00 | 0.39 | 0.92 |
| 1/16   | 52  | 1.00 | 3.71 | 6.23 |
| 2-4/16 | 124 | 2.92 | 7.43 | 9.16 |
| 5-8/16 | 147 | 6.49 | 11.89 | 12.15 |
| 9-15/16| 527 | 12.92 | 14.44 | 14.48 |

This reproduces the existing `bucket_analysis.py` heatmap (same axis, same oracle). No new problem
had loop0==16 (the set is non-saturated by construction), so there is no 16/16 bucket.

## B. Raw vs exact-unique vs canonical-unique

Full numbers in `tables/raw_vs_unique_by_bucket_loop.csv`. Canonical-unique means (of 16):

| loop0 bucket | loop0 | loop1 | loop2 | raw→canon Δ (loop2) | dup-factor loop2 |
|---|---|---|---|---|---|
| 0/16   | 0.00 | 0.35 | 0.76 | 0.92→0.76 | 1.21 |
| 1/16   | 1.00 | 3.08 | 4.60 | 6.23→4.60 | 1.36 |
| 2-4/16 | 2.85 | 5.95 | 7.35 | 9.16→7.35 | 1.25 |
| 5-8/16 | 6.22 | 9.63 | 9.67 | 12.15→9.67 | 1.26 |
| 9-15/16| 11.60 | 11.47 | **10.61** | 14.48→10.61 | 1.36 |

**Read the last row:** raw rises 12.9→14.5 while canonical-unique *falls* 11.6→10.6. That gap is the
copy amplification the slide currently hides. Aggregate over all 1,093 problems:

| loop | solved | raw | exact-unique | canonical-unique | new canonical | dup-factor | frac-dup |
|---|---|---|---|---|---|---|---|
| 0 | 850 | 8177 | 7660 | 7432 | 7432 | 1.100 | 9.1% |
| 1 | 872 | 10567 | 9173 | 8446 | 6484 | 1.251 | 20.1% |
| 2 | 877 | 11101 | 9262 | 8350 | 6094 | 1.330 | 24.8% |

Note canonical-unique per-loop **plateaus** (8446 at loop1 → 8350 at loop2) while raw keeps climbing.
Exact-unique sits between raw and canonical: canonical merges only ~10% more than exact
(comment-/whitespace-only variants), so both dedup levels tell the same story.

## C. New-unique (genuinely new distinct correct solutions per loop)

Table: `tables/new_unique_by_bucket_loop.csv`. `new_unique[L]` = canonical-correct programs at loop L
not seen correct at any earlier loop. Totals introduced per loop: **loop0 7,432 · loop1 6,484 ·
loop2 6,094** distinct new correct programs — the loops keep finding new solutions, they are not
merely copying. Fraction of *solved* problems whose loop-correctness is only repeated from earlier
loops (no new canonical) is small: **≤4.7% (loop1), ≤12% (loop2)**, and is highest exactly in the
easy 9-15 bucket (63 of 526 solved = 12.0% at loop2) — consistent with easy problems exhausting
their distinct-solution space and starting to repeat.

## D. Cross-loop erosion / amplification (loop1 → loop2)

Per bucket, over problems solved at each loop (see `rollup.json → erosion`):

| bucket | solved L1 | solved L2 | L1-solved lost-all at L2 | L2 retained a prev canonical | L2 introduced new canonical | L2 only-amplified (no new) |
|---|---|---|---|---|---|---|
| 0/16   | 37  | 50  | 7 | 17  | 49  | 1  |
| 1/16   | 43  | 41  | 4 | 23  | 38  | 3  |
| 2-4/16 | 119 | 116 | 5 | 97  | 111 | 5  |
| 5-8/16 | 147 | 144 | 3 | 126 | 135 | 9  |
| 9-15/16| 526 | 526 | 0 | 473 | 463 | 63 |

Loops both **erode** a few problems (lose all correct — most for the hard buckets) and **add** many
new distinct solutions. Pure amplification (solved at loop2 with *no* new canonical vs earlier) is
rare in the hard buckets (1/3/5) and concentrated in the easy 9-15 bucket (63).

## E. Frontier robustness — 0/16 hard-zero bucket (the main claim)

Per-problem detail: `tables/frontier_unique_correct_detail.csv` (243 rows).

- **Problem-level solved by loop (raw oracle):** loop0 **0** → loop1 **37** → loop2 **50**;
  ever-solved across loops = **57**.
- **Multiplicity:** of the 57 ever-solved, **19** have exactly 1 canonical-unique correct solution
  (at their last solved loop) and **38** have multiple. So most hard-zero solves are backed by more
  than one distinct program, not a single copied one.
- **loop2 genuinely-new vs loop1:** of the 50 hard-zero problems solved at loop2, **49** carry a
  canonical solution not correct at loop1; only `cf-00826` is pure re-emission. **20** are solved at
  loop2 but were not solved at loop1 at all.

**Conclusion:** the frontier claim is problem-level *solved* (any-of-N), which duplicate
amplification cannot inflate — a copy of a wrong answer is still wrong, and every solve implies ≥1
distinct correct program. The 0→37→50 movement is genuine reachability, independent of duplication.

## F. Outputs (with exact inputs)

| Output | What |
|---|---|
| `unique_correct_summary.md` | this file |
| `tables/raw_vs_unique_by_bucket_loop.csv` | raw / exact-unique / canonical-unique / dup-factor / near-dup per bucket per loop |
| `tables/new_unique_by_bucket_loop.csv` | new-unique + only-copied per bucket per loop |
| `tables/duplication_by_bucket_loop.csv` | pooled sums + duplication metrics per bucket per loop |
| `tables/frontier_unique_correct_detail.csv` | per-problem hard-zero (0/16) detail |
| `figures/raw_correct_heatmap.png` | reproduced slide heatmap (raw) |
| `figures/canonical_unique_correct_heatmap.png` | canonical-unique heatmap |
| `figures/duplication_factor_heatmap.png` | raw ÷ canonical-unique heatmap |
| `figures/new_unique_correct_heatmap.png` | new canonical-unique heatmap |
| `per_problem_hashes.json` | intermediate: per (problem,loop) correct-candidate hash sets |
| `rollup.json` | machine-readable roll-up (totals, erosion, hard-zero) |

**Input files (read-only, not modified):**
- SE checkpoints: `tts-sft/outputs/openthoughts114k_codeforces_full_datagen/se16/<shard>/ck/*_loop{0,1,2}.json`
  (shards: sh0–sh4, sh7, sh8, redo_sh0–redo_sh5)
- Problem→shard id maps: `.../se16/<shard>/out.jsonl`
- Oracle grade cache: `tts-sft/outputs/grading_cache/se16.jsonl` (cache-only lookups)
- Tests / time limits: `tts-sft/data/openthoughts114k_codeforces_stdin_clean.jsonl`
- Problem classes: `.../problem_classes/pass16_by_id.json`, `impossible_ids.txt` (label only; not used for correctness)
- Repo helpers imported read-only: `scripts/score_diversify_ab.py::extract_code`, `scripts/lcb_grading.py::cache_key`

**Scripts (this audit, under `scripts/`):**
- `harvest_correct_hashes.py` — cache-only grading → per (problem,loop) sets of exact & canonical
  hashes of correct candidates → `per_problem_hashes.json`
- `analyze_unique_correct.py` — all tables, figures, `rollup.json`

**Reproduced/consistent with prior work:** raw correct totals (8177/10567/11101) and 0 cache misses
match `recompute_se16_summary.json`; the raw heatmap matches `bucket_analysis.py`.

## G. How to revise the current slide

- **Relabel the current heatmap:** yes — retitle it *"correct-candidate density (raw, NOT
  deduplicated)"* rather than implying diversity. The count is a legitimate density measure but not a
  distinct-solution count.
- **Add a second heatmap:** yes — place `canonical_unique_correct_heatmap.png` next to it (and
  optionally `duplication_factor_heatmap.png`). The contrast is the whole point: on easy problems raw
  rises while canonical-unique is flat/falling; on hard problems both rise.
- **One-sentence caveat under the figure:**
  > *Counts raw oracle-correct candidates, not distinct programs; loop-over-loop growth is partly
  > copy amplification (duplication factor 1.10→1.33 across loops), so canonical-unique correct is
  > flat-to-declining on easy problems while the hard-problem and frontier gains are genuine.*
- **One-sentence oral explanation:**
  > *"This heatmap is raw correct-candidate density, not deduplicated — when we dedup to distinct
  > programs the easy-bucket 'improvement' is mostly the loop re-emitting the same solution, but the
  > hard-problem gains and the 0→50 hard-zero frontier are real distinct new solves, not copies."*

## H. Limitations & rules honored

- **Exact/canonical dedup is NOT semantic equivalence.** Canonical-norm removes comments and
  normalizes whitespace but keeps variable names, statement order, and block structure verbatim
  (INDENT/DEDENT/NEWLINE preserved). It is deliberately *conservative*: it can only **over-count**
  uniqueness (miss true equivalences), never invent duplicates. Alpha-renamed or reordered-but-
  equivalent programs still count as distinct — so true diversity is ≤ the canonical-unique numbers
  reported.
- **Near-duplicate clusters** (`mean_near_dup_unique` column, token-Jaccard ≥ 0.90) are an
  approximate diagnostic only, not ground truth; they track canonical-unique closely and are not
  used for any headline claim.
- **Oracle correctness is kept strictly separate** from any self-verifier label (self-verifier labels
  are not used here) and from candidate-level diversity: dedup is applied only *after* oracle
  correctness is decided, on the correct candidates.
- **Problem-level solved counts are kept separate** from candidate-level diversity throughout.
- **No numbers were invented**; all cells trace to `per_problem_hashes.json` / `rollup.json`. Every
  correct candidate tokenized cleanly (0 canonicalization fallbacks), so canonical-unique is reliable.
- **loop3 is excluded** (only 486 problems present with 2,868 cache misses → not comparable);
  analysis is restricted to loops 0/1/2, which have complete cache coverage (0 misses).
- No repo files were modified; all outputs live under `analysis_outputs/data_verification/unique_correct_audit/`.
