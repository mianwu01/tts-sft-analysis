# Phase 0 — Data map (TTS / SqueezeEvolve data verification)

_Date: 2026-07-02. All paths relative to repo root `/mnt/cpfs/yangboxue/opsd/TTS/tts-sft/` unless absolute.
This map records **where every experiment's raw data lives**, its schema, and what is missing/ambiguous.
No result claims are made here._

## 0. Input-path check (task §1)

| path | status |
|---|---|
| `docs/PROJECT_SUMMARY_2026-07-01.md` | present (claims source, NOT ground truth) |
| `/mnt/cpfs/yangboxue/opsd/TTS/meeting` | present (dir: `7-02` Harman notes + Dwarkesh-podcast transcript) |
| `docs/PartA.md` | present (writing pack, NOT ground truth) |
| `/mnt/cpfs/yangboxue/opsd/TTS/task` | present (`7-02.md` = this task) |
| `/mnt/cpfs/yangboxue/opsd/TTS/slides/make_slides_week_0626.py` | present (reference deck style) |
| repo root `tts-sft/` | present |

## 1. Experiment inventory (current story: base model `Qwen/Qwen3-4B`, non-thinking-era runs are legacy)

### A. se16 — canonical-nofb SqueezeEvolve, pop-16, codeforces non-saturated 1,093  ← headline frontier experiment
- **Seed pool (with oracle tests):** `data/openthoughts114k_codeforces_stdin_clean.jsonl` — 1,617 rows
  `{seed_id, question, test_cases:{inputs,outputs,time_limit}, …}`.
- **Non-saturated seed:** `outputs/openthoughts114k_codeforces_full_datagen/inputs/se16_nonsat_seed.jsonl` — 1,093 rows.
- **Shards (authoritative 13):** `outputs/openthoughts114k_codeforces_full_datagen/se16/{sh0..sh4,sh7,sh8,redo_sh0..redo_sh5}`
  (sh5/sh6 aborted after loop0; their problems re-run as redo_sh0..5).
  Per shard: `out.jsonl` (final population), `ck/<run>_loop{L}.json` (per-loop 16-candidate population,
  `problems[i].candidates`, positionally matched to `out.jsonl` ids), `config.yaml`.
  Shard sizes: sh0-3=122, sh4/7/8=121, redo 40-41 → union = 1,093, verified disjoint (see verify script).
- **Loop coverage:** loop0/1/2 all 13 shards; **loop3 checkpoints exist** on sh2, sh3, redo_sh0..5 (486 problems; graded subset TBD in Phase 1).
- **Config (`sh*/config.yaml`):** `population:16, groups:16, k:4, loops:2(+config_loop2.yaml extension), fitness:diversity,
  selection:uniform, update:replace, recombination:livecodebench-aggregate, strip_think:true, temp 1.0, top_p 0.95, top_k 20,
  max_tokens 40960, seed 1234`. **Budget: 16 fresh generations per loop → cumulative 16/32/48/64 at loop0/1/2/3.**
- **Pinned loop0:** `se16/pinned_loop0/*.json` (loop0 reused across loop extensions — no re-sampling).
- **Grading cache (oracle verdicts):** `outputs/grading_cache/se16.jsonl` — 49,863 entries
  `{k: md5(harness_path,code,tests_json,tle), v:{passed,n_passed,n_total,error,first_fail}}`.
  Cache key logic: `scripts/lcb_grading.py:cache_key`; grader: `scripts/score_diversify_ab.py:grade_arm`
  (extract last code block → run ALL hidden tests, 6 s/test → full-pass bool; hashes = ws-normalized code of passers).
- **Derived artifacts (to be re-verified, not trusted):** `se16/frontier/`
  - `per_problem_correct_counts.csv` (1,093 rows; loop0/1/2 correct of 16 + class)
  - `per_problem_unique_counts.csv`, `frontier_overall.csv`, `frontier_report.json`, `FRONTIER_REPORT.md`,
    `newly_solvable_*.csv`, `impossible244_becoming_solvable.csv`, `density_bucket_*.csv`, `loops_grade_summary.json`
  - producers: `scripts/grade_se16_loops.py` (Phase B), `scripts/frontier_tables.py` (Phase C), `scripts/grade_se16_shards.py`.
- **Problem classes (reference buckets):** `outputs/openthoughts114k_codeforces_full_datagen/problem_classes/`
  `pass16_by_id.json` (1,617 ids → 0..16), `impossible_ids.txt` (244), `informative_ids.txt` (849), `saturated_ids.txt` (524).
  **No builder script found — provenance unverified** (hypothesis: pop-8 run loop0∪loop0b = 16 independent samples; Phase 1 will test this).

### B. sharded_qwen3_4b — pop-8 SE arms + independent BoN on FULL codeforces 1,617  ← the SE-vs-BoN comparison
- Root: `outputs/openthoughts114k_codeforces_full_datagen/sharded_qwen3_4b/sh{0..3}` (405/405/405/402 problems).
- Per shard, all with **8 candidates/problem** (verified from records):
  `_loop0.jsonl`+`loop0_out.jsonl` (independent draw), `loop0b_out.jsonl` (2nd independent draw, seed 5678),
  `nofb_out.jsonl` (SE loop1, no feedback), `fb_out.jsonl` (SE loop1 + full-test feedback; **tests leaked into generation — datagen-only arm**).
- **`reachability_se_vs_bon.json`:** N=1617, SE(loop0∪nofb-loop1)=1384 vs BoN(loop0∪loop0b)=1373; only_SE=28, only_BoN=17.
  Producer `scripts/reachability_se_vs_bon.py` — **matched at 8+8 = 16 generations/problem** (docstring), i.e.
  **NOT "32-sample" as PROJECT_SUMMARY §1 and frontier_report.json ("reachability_matched32_full1617") label it. Discrepancy #1 to audit.**
- Grading caches: `outputs/grading_cache/reachability_bon.jsonl` (35,464), `canonical_nofb_full.jsonl`, `canonical_fb_full.jsonl`.

### C. SFT experiments (E-matrix) + LCBv6 evals  ← Phase 5
- **Matrix definition:** `docs/multinode_tasks/EXPERIMENT_QUEUE_V2.md` (E1/E1b/E2/E3/E3b/E4); configs `configs/exp_*.yaml`,
  `configs/qwen3_4b_cleaned_se_loop1_16_sft_{all,best}.yaml`.
- **Training data:** `data/sft/`
  - loop0 (independent): `emptythink_loop0_fullpass_{unique,best}.jsonl`, `realthink_loop0_fullpass_{unique,best}.jsonl`
  - loop1 (SE pop16): `cleaned_se_loop1_16_nonsat_fullpass_{unique,best}.jsonl` (+ `.summary.json` each)
  - legacy pop8: `empty_think_fullpass_*.jsonl`, `cstrip_*`
- **Checkpoints:** `outputs/sft/<arm>_lora/` (+ `.train.log`).
- **Evals (raw):** `outputs/sweep_lcbv6/<arm>_ck<step>/{compare_summary.json, base_per_problem.jsonl, sft_per_problem.jsonl, sft_raw.jsonl}`.
  `*_per_problem.jsonl`: `{problem_id, correct_count, n_samples:16, cap_hit_count, platform, …}` → pass@k computable.
  Base (untrained) numbers embedded in every `compare_summary.json` (shared grading cache `nonthinking_lcbv6_shared.jsonl`).
  Collector: `scripts/collect_lcbv6_sweep.py`. Eval seed: `data/seeds/lcbv6_seed.jsonl` (131 problems, LCBv6).
  Base raw generations: `outputs/qwen3_4b_lcbv6/qwen3_4b_lcbv6_raw.jsonl`.
- Arms present in `outputs/sweep_lcbv6/`: run1_A_lora_ck{141,282,424} (final-only), empty_think_A_lora_ck565 (E1),
  emptythink_loop1_B_lora_ck164 (E1b), emptythink_loop0_A_lora_ck243 (E3), emptythink_loop0_B_best_lora_ck150 (E3b),
  realthink_loop0_A_lora_ck116 (E2), realthink_loop0_B_lora_ck72 (E4), all_ck40/all_ck80/smoke (legacy).

### D. Self-verification / judge selection (pilot-100)  ← Phase 6
- Root: `outputs/openthoughts114k_codeforces_full_datagen/self_verification_selection/`
  - `pilot_100_ids.txt` (100 problems), pools = independent16 (se16 loop0) & se_loop1_16 (se16 loop1).
  - Runs (each: `eval.json` {top1_fullpass_rate, top3…}, `selected.jsonl`, `judge_cache.jsonl`, `run_config.json`):
    Qwen3-4B judges: `pilot100c_{svd,v1,svdv1tb,llmv…}_{independent16,se_loop1_16}`, `pilot100c_svdL{1..5}_*` (SVD prompt levels);
    gpt-oss-120b judge: `{independent16,se_loop1_16}_{svd,v1}_gptoss120b`; `judge_mode_ablation/`; `_v1pp_analysis/`.
  - `SELECTION_SUMMARY.txt` (older roll-up — **stale vs later corrected runs; Discrepancy #2**: shows V1-SE 0.68 vs summary's 0.74),
    `selfverif_difficulty_per_problem.json` (difficulty split source).
- Older SVD pilot: `outputs/openthoughts114k_codeforces_full_datagen/svd_pilot_100/svd_pilot_100x16.jsonl`.
- Selector script: `scripts/run_self_verification_selection.py`; analysis `scripts/analyze_judge_mode_ablation.py`.
- Oracle & random baselines: derivable from pools + `pass16` grades (recompute in Phase 6).

### E. code_contests scale-up (cf+cc pool)  ← §4 of summary
- Pool: `data/openthoughts_cf_cc_stdin_pool.jsonl` (8,124 = 1,617 cf + 6,507 cc); `outputs/openthoughts_cf_cc_datagen/manifest.json`.
- loop0 pop-8: `outputs/openthoughts_cf_cc_datagen/loop0_pop8/sh{0..43}`; **saturation:** `saturation_report.json`
  (n=6507: saturated-8/8=3020, informative=2258, impossible=1229 → non-sat 3487; full dist 0..8).
- loop1 pop-8 (SE): `outputs/openthoughts_cf_cc_datagen/loop1_pop8/{inputs,manifest.json,pinned_loop0,se}` — **RUNNING, not graded**.
- Builder: `scripts/build_cf_cc_pool.py`; sat report: `scripts/cc_saturation_report.py`.

### F. Legacy (Qwen3-4B-Thinking-2507 era / math) — reference only, not the current story
- Math SE loops≤5 + BoN N=80/N=16@160k: `outputs/node1_se_loop5_*`, `node2_bon_*`, `node2_reachability_loop*`, `node4_loop10_16k_*`.
- pop-8 cstrip SFT (negative results): `outputs/node1_cstrip_loop1_*`, `node3_cstrip_loop2_*`, docs `NODE1_RESULTS.md`/`NODE3_RESULTS.md`.
- Feedback probes (fb in prompt): `node1_lcb_*`, `node2_math_*` + docs. The **fb arm** of B above is the only current-model feedback run.

## 2. Likely source files per verification phase

| Phase | primary raw sources |
|---|---|
| 1/2 frontier | se16 `ck/*loop{0,1,2,3}.json` + `outputs/grading_cache/se16.jsonl` + `out.jsonl` ids (recompute per-problem counts; cross-check `frontier/*`) |
| 3 compute-matched | A: se16 loop budgets from `config.yaml`; independent arms: `problem_classes/pass16_by_id.json` (16), se16 loop0 (16 fresh), pop-8 `loop0/loop0b_out.jsonl` (8+8) + `reachability_bon.jsonl` cache |
| 4 buckets | recomputed per-problem counts (Phase 1) bucketed by loop0 correct |
| 5 SFT | `outputs/sweep_lcbv6/*/compare_summary.json` + `*_per_problem.jsonl` (16 samples → pass@k) |
| 6 verification | `self_verification_selection/runs/*/{eval.json,selected.jsonl,judge_cache.jsonl}` + pool grades for oracle/random |
| 7 stopping rules | Phase 1 per-problem loop trajectories |
| 8 manifests | se16 ck + cache (correct labels), `data/sft/*.jsonl` |
| 9 leakage | configs (`evaluation: livecodebench-none`), `fb.yaml` arms, seed vs LCBv6 id sets, `check_contamination_vs_lcbv6.py` output |

## 3. Missing / ambiguous (flagged before any claims)

1. **`problem_classes/pass16_by_id.json` has no builder script** — provenance must be established empirically (Phase 1) before the
   "impossible-244" framing is used. Hypothesis: pop-8 loop0∪loop0b.
2. **"Compute-matched 32-sample BoN" labeling**: `reachability_se_vs_bon.py` matches at **16** gen/problem on pop-8 arms;
   `frontier_report.json` + PROJECT_SUMMARY call it matched-32. One of them is wrong — Phase 3 must recompute at true budgets.
   Also note the SE arm in that comparison is the **pop-8** SE, not the headline pop-16 run.
3. **SE budget accounting** (does SE loop1 cost 16 or 32 cumulative generations?) — from config, each loop generates 16 new
   candidates; any fair frontier comparison at loop1 needs a 32-sample independent baseline. A **true independent-32 arm does not
   exist as a single run** — must be assembled from (reference-16 ∪ se16-loop0-16) or (se16-loop0 ∪ pop-8 16), each with caveats.
4. **loop3**: checkpoints exist for 486 problems (sh2,sh3,redo_0..5) but summary claims "244-problem sample, net −1" — which
   subset was graded is unverified; cache will reveal.
5. **Selection roll-ups disagree** (SELECTION_SUMMARY.txt V1-SE 0.68 vs PROJECT_SUMMARY 0.74) — per-run `eval.json` are authoritative;
   known silent-truncation bug in `selected.jsonl` (memory: verify `wc -l selected.jsonl == n_ids`).
6. **AUC / precision / recall / r=0.65 claims** for judges: no obvious artifact file yet — must be recomputed from
   `judge_cache.jsonl` + oracle grades, or located in `_v1pp_analysis`/`judge_mode_ablation`.
7. **cf_cc loop1** is mid-run: no loop1 grades exist → all §4 SE-on-cc claims are loop0-only for now.
8. **E4 data-size mismatch** (config 371 vs file 504 rows — from project memory) — verify in Phase 5.
9. Math-era experiments used a different base model (Thinking-2507) — must not be mixed into current-model claims.

## 4. Recommended next commands (executed in subsequent phases)

```bash
# Phase 1: recompute per-problem per-loop correct counts from raw ck + cache (no re-execution)
python analysis_outputs/data_verification/scripts/recompute_se16_counts.py

# Phase 1 spot-check: re-execute ~30 random cached candidates to validate cache honesty
python analysis_outputs/data_verification/scripts/spot_check_cache.py --n 30

# Phase 3: recompute pop-8 reachability + assemble independent-32 comparison on the 244 set
python analysis_outputs/data_verification/scripts/verify_compute_matched.py

# Phase 5: recompute SFT pass@k from *_per_problem.jsonl
python analysis_outputs/data_verification/scripts/verify_sft_passk.py

# Phase 6: recompute selection metrics + oracle/random from runs/ + pool grades
python analysis_outputs/data_verification/scripts/verify_selection.py
```
