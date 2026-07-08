# Phase 3 — Compute-matched direct-sampling baselines (AUDIT)

_This is the key audit for the claim "SE is not just more sampling"._
Scripts: `scripts/verify_compute_matched.py`; tables: `tables/compute_matched_baselines.csv`,
`tables/compute_matched_detail.json`.

## 1. Verified budgets (from configs, CODE-level facts)

| run | config | gens/loop/problem | cumulative at loop L |
|---|---|---|---|
| se16 (headline frontier) | `se16/sh*/config.yaml`: `population:16, groups:16, loops:2(+ext)` | 16 | L0=16, L1=32, L2=48, L3=64 |
| pop-8 sharded | `sharded_qwen3_4b/sh*/{fb,loop0b}.yaml`: `population:8` | 8 | L0=8, L1=16 |
| pop-8 loop0b | same, `loops:1, seed:5678` → **loop0-only = pure independent draw** | 8 | 8 |

Sampling params identical across all arms (temp 1.0, top_p 0.95, top_k 20, max_tokens 40960,
same base `Qwen/Qwen3-4B`, same prompts) → unions of draws are legitimate independent-N baselines.

## 2. Existing compute-matched comparisons (recomputed from raw files, 0 cache misses)

### (a) pop-8: SE vs BoN at matched **16** gen/problem, full 1,617  — VERIFIED, but MISLABELED upstream
`reachability_se_vs_bon.json` reproduced exactly: SE(l0∪nofb-l1)=**1,384**, BoN(l0∪l0b)=**1,373**,
only_SE=28, only_BoN=17, both=1,356, neither=216.
**Labeling errors found:** `frontier_report.json` calls this `reachability_matched32_full1617` and
PROJECT_SUMMARY §1 calls it "compute-matched Best-of-N (32-sample)". The underlying runs are pop-8:
it is a **16-generation-matched** comparison (8+8 vs 8+8), and its SE arm is the pop-8 run,
**not** the headline pop-16 run. The comparison itself is valid; the "32" label is wrong.

### (b) se16 frame: SE vs independent at matched **32**/problem, 1,093 non-sat — NEW, cleaner (this audit)
Independent-32 = union of two independent 16-draws (reference pop-8 l0∪l0b restricted to non-sat ∩
se16 loop0). Same problems, same model/sampler.

| quantity (matched 32) | independent-32 | SE (cumulative 32) |
|---|---|---|
| aggregate coverage (any-of) | 850 /1,093 | loop1-pop 872; l0∪l1 union **887** |
| hard tail: ref-244 solved | **1** | **38** |
| hard tail: run-243 solved | **0** | **37** |

The second independent 16-draw adds **zero** aggregate coverage (850→850) and 0–1 hard-tail solves;
SE's second 16 (the loop1 recombination) adds +22 population coverage / +37 union coverage and
37–38 hard-tail solves. **At matched compute, evolution ≠ more sampling — verified.**

### (c) budget sweep summary

| SE setting | SE budget | SE coverage | matched independent | verdict |
|---|---|---|---|---|
| pop-8 SE l0∪l1 (1,617) | 16 | 1,384 | BoN-16: 1,373 | +11 net (28/17 split) — modest |
| se16 loop1 pop (1,093) | 32 | 872 | indep-32: 850 | +22 |
| se16 l0∪l1 union (1,093) | 32 | 887 | indep-32: 850 | **+37** |
| se16 l0∪l1∪l2 union (1,093) | 48 | 907 | indep-48: **MISSING** | not compute-matched yet |
| se16 loop3 (partial) | 64 | n/a (258-prob subset) | indep-64: MISSING | not compute-matched |

Cross-run consistency: pop-8 SE (its own 16-budget) solves 28 of ref-244; se16 loop1 solves 38;
overlap 20 — two separate SE runs crack overlapping-but-distinct hard-tail subsets, both ≫ independent.

## 3. Missing baselines → exact recipes (DO NOT run without Harman's go-ahead; ~GPU-days each)

**independent-48 (to compute-match SE loop2), 1,093 non-sat:**
```bash
# new config = copy of sharded_qwen3_4b/sh0/loop0b.yaml with:
#   run_name: cf_indep48_extra16   routing.population: 16   routing.loops: 1   routing.seed: 9999
#   (loops:1 => loop0-only = pure independent sampling; 16 fresh samples)
# seed file: outputs/openthoughts114k_codeforces_full_datagen/inputs/se16_nonsat_seed.jsonl
python scripts/run_squeeze_evolve.py --config configs/cf_indep48_extra16.yaml \
  --input inputs/se16_nonsat_seed.jsonl --output outputs/.../indep48/extra16_out.jsonl
# then union with the existing two 16-draws; grade via scripts/grade_se16_shards.py-style grade_arm
```
Cost estimate: se16 loop0 (16/problem over 1,093) ≈ one loop of the se16 run; from shard logs the
full se16 3-loop run took ~35 h on multiple nodes → one extra 16-draw ≈ 1 node-day class. `RESULT-DEPENDENT`.

**independent-64 (loop3 match):** same recipe with `population: 32` or run the 16-draw twice (seeds 9999/10001).

**Finish loop3 grading (no GPU, CPU-only execution of 2,868 cached-miss candidates):**
```bash
python scripts/grade_se16_loops.py --max-loop 3 --workers 32   # extends the cache; ~hours of CPU
```

## 4. Sample-count verification trail

- Every candidate count verified from records: se16 = 16/problem/loop (`ncand` column, all 16);
  pop-8 arms = 8/record (asserted over all 1,620 records/arm; sh3 has 402).
- Budgets from `config.yaml` files quoted above (population/groups/loops), not from filenames.
- Grading: `outputs/grading_cache/{se16,reachability_bon}.jsonl`; spot-check re-execution 30/30.

## 5. Claims status

| claim (PROJECT_SUMMARY §1) | status |
|---|---|
| "SE coverage 1,384 vs BoN 1,373 (only_SE 28 / only_BoN 17) → SE +11 net" | **VERIFIED** (but it is matched-16, pop-8 — not "32-sample") |
| "vs compute-matched BoN (32-sample…)" | **CONTRADICTED label** — no 32-sample BoN run exists |
| "SE reaches problems sampling cannot (38→51 vs ~1)" | **VERIFIED & STRENGTHENED** (independent-32 = 1/244 exact; union 58) |
| "frontier largely capability-limited" | SUPPORTED: 186/244 hard-zeros never solved by anything on disk |
