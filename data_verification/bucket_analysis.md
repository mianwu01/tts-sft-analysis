# Phase 4 — Bucket analysis / curriculum signal (VERIFIED, descriptive only)

Buckets = **this-run loop0 correct count** (actual K=16, verified). Data: recomputed per-problem
counts (`tables/recomputed_se16_per_problem.csv`; raw ck + cache, 0 misses, spot-checked).
Script: `scripts/bucket_analysis.py`. Full table: `tables/bucket_analysis.csv`.
Heatmap: `figures/bucket_heatmap.png`. Loop3 columns are the 258-problem fully-graded subset only.
No 16/16 bucket exists: max loop0 correct = 15 (pool was pre-filtered non-saturated by the
reference draw; the fresh draw never fully saturated a problem).

## Central table (mean correct of 16 → density; unique = dedup by normalized code)

| bucket (loop0) | n | loop0 | loop1 | loop2 | unique l1→l2 | %improved l1 / l2 | %worsened l1 / l2 | unsolved @l2 |
|---|---|---|---|---|---|---|---|---|
| 0/16 | 243 | 0.00 | 0.39 | 0.92 | 0.36 → 0.83 | 15.2 / 18.1 | 0.0 / 2.9 | **193 (79%)** |
| 1/16 | 52 | 1.00 | 3.71 | 6.23 | 3.27 → 5.12 | 75.0 / 65.4 | 17.3 / 17.3 | 11 |
| 2-4/16 | 124 | 2.92 | 7.43 | 9.16 | 6.64 → 8.09 | 83.9 / 68.5 | 8.9 / 21.0 | 8 |
| 5-8/16 | 147 | 6.49 | 11.89 | 12.15 | 10.46 → 10.54 | 89.8 / 49.0 | 7.5 / 32.7 | 3 |
| 9-15/16 | 527 | 12.92 | 14.44 | 14.48 | 12.14 → **11.51 (declines)** | 75.9 / 28.5 | 12.5 / 23.7 | 1 |

## Where the gains concentrate (verified facts)

1. **Relative densification is largest in the boundary buckets** (1 and 2-4): ×6.2 and ×3.1 mean-correct
   by loop2, still improving at loop2. The 5-8 bucket is nearly done after ONE loop (11.89→12.15).
2. **The 9-15 bucket plateaus at loop1 and starts to churn**: at loop2 only 28.5% improve, 23.7% worsen,
   and **unique density falls** (12.14→11.51) — extra loops there produce duplicates, not new solutions.
3. **The 0/16 bucket moves but stays mostly stuck**: 37 newly solved at loop1 + 20 at loop2, but 193/243
   (79%) remain unsolved and mean density after solving is tiny (0.92/16). Frontier expansion is real but
   thin here — matches the "capability-limited" reading.
4. **Fragility on thin buckets**: bucket 1/16 has 17% of problems *losing* their only correct solution
   at each loop (`update: replace`); 11 problems that started with 1 correct are at 0 by loop2.
   Pinned/elitist retention (keep best-so-far on disk) is what saves these for data-generation use.
5. loop3 (partial, 258 probs): boundary buckets still creep (e.g. 2-4: 9.57 mean) but 0-bucket newly
   solved = 0 and 9-15 unique density keeps falling — consistent with saturation.

## Offline curriculum interpretation (descriptive — no curriculum experiment has been run)

| bucket | suggested action (hypothesis to test, not a result) |
|---|---|
| 0/16 | keep a **small exploration allocation** (SE does crack 23% of these by loop2; sole source of frontier movement) |
| 1, 2-4 | **continue evolving** — highest marginal gain per loop, still improving at loop2 |
| 5-8 | 1 loop is enough; freeze after loop1 (loop2: 33% worsen vs 49% improve) |
| 9-15 | **stop/freeze at loop1; use best-so-far** (loop2 adds duplicates and erodes unique density) |
| (8/8 cc / 16/16 ref) | exclude from evolution entirely (cf_cc already drops these — 46.4%) |

## cf_cc scale-up saturation (aggregation recomputed — matches repo report exactly)

`tables/cc_saturation_recompute.json` vs `outputs/openthoughts_cf_cc_datagen/saturation_report.json`:
n=6,507 code_contests loop0 (pop-8): saturated 8/8 = 3,020 (46.4%), informative 1–7/8 = 2,258 (34.7%),
impossible 0/8 = 1,229 (18.9%) → non-saturated 3,487 (53.6%). Distribution is **bimodal** (1,229 at 0
and 3,020 at 8; middle bins 216–641). Caveat: verified at aggregation level from per-shard
`grade_loop0.json`; per-candidate re-grading of cc (different executor) not re-run here (TODO, low risk).
Note "impossible 0/8" on cc includes an estimated ~7% test-broken problems (from the Jul-1 summary;
that sub-claim is `RESULT-DEPENDENT`, not re-verified here).

**Do-not-claim:** these tables justify a curriculum *hypothesis*; no experiment has yet shown the
curriculum improves anything.
