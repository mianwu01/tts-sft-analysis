# Sewon meeting — verified data tables (every number recomputed from raw files; see FINAL_REPORT.md)

Setting: base `Qwen/Qwen3-4B` (single model, verifier-free SqueezeEvolve, no tests in generation),
1,093 non-saturated OpenThoughts-codeforces problems, oracle = full hidden tests, 16 candidates/loop.

## T1 — Three-way pass@K frame (terminology; Slide 1)
| quantity | definition | value here |
|---|---|---|
| current/evolving-population pass@16 | oracle any-correct within the CURRENT 16-candidate population | 0.778 → 0.798 → 0.802 (loop0/1/2) |
| initial direct-sampling pass@16 | any-correct within the INITIAL 16 direct samples | 0.778 (= loop0 row) |
| compute-matched direct-sampling frontier | direct sampling at the SAME total budget (32 = two 16-draws) | coverage 850/1,093 (unchanged from 16 samples: 850) |

## T2 — Frontier movement (Slide 2)
| setting | budget/problem | solvable /1,093 | pass@1 | pass@16(pop) | ref-244 hard-zeros solved |
|---|---|---|---|---|---|
| initial direct 16 (loop0) | 16 | 850 | 0.468 | 0.778 | 1* |
| independent-32 (two 16-draws) | 32 | **850** | — | — | **1** |
| SE loop1 population | 32 cum | 872 | 0.604 | 0.798 | **38** |
| SE loop2 population | 48 cum | 877 | 0.635 | 0.802 | **51** |
| SE union ≤loop2 (all on disk) | 48 cum | 907 | — | — | **58 (23.8%)** |
| independent-48 | 48 | **MISSING baseline** | — | — | TODO |

\*the one ref-244 problem loop0 solves. Two independent 16-draws agree on 243/244 hard-zeros; the
second draw adds ZERO aggregate coverage (850→850) — independent sampling is saturated by ~16 samples
on this pool, evolution is not. Cross-check (pop-8 run, matched-16 on full 1,617): SE 1,384 vs BoN
1,373 = +28/−17. Loop3 (partial, 258 probs graded): net −1 → saturated by loop3.

## T3 — Boundary buckets (Slide 3; mean correct of 16 per loop0-bucket)
| bucket | n | l0 | l1 | l2 | unique l1→l2 | note |
|---|---|---|---|---|---|---|
| 0 | 243 | 0.0 | 0.4 | 0.9 | 0.36→0.83 | 57 problems cracked; 79% never solved |
| 1 | 52 | 1.0 | 3.7 | 6.2 | 3.3→5.1 | biggest relative gain; fragile (17%/loop lose their only solve) |
| 2-4 | 124 | 2.9 | 7.4 | 9.2 | 6.6→8.1 | still improving at loop2 |
| 5-8 | 147 | 6.5 | 11.9 | 12.2 | 10.5→10.5 | done after 1 loop |
| 9-15 | 527 | 12.9 | 14.4 | 14.5 | 12.1→**11.5 ↓** | plateau; loop2 = duplicates + erosion |

Offline stopping simulation: **drop only 9-15 after loop0 → 48% evolution compute saved, 0 frontier
loss, coverage identical (907)**. Dropping the 0-bucket too (pure boundary curriculum) loses **57/58**
frontier solves for 70% savings. "Stop-when-dry" loses the 20 loop2-only cracks.

## T4 — Fold-back into weights: SFT (Slide 4; LCBv6-131 held out, 0 overlap, raw generation)
| arm | data | pass@1 | pass@4 | pass@16 | cap-hit |
|---|---|---|---|---|---|
| base (untrained) | — | 0.413 | 0.482 | 0.527 | 44% |
| loop0-best (804) | independent, oracle-best/problem | 0.436 | 0.534 | 0.595 | 24% |
| loop1-best (872) | SE, oracle-best/problem | **0.437** | 0.528 | 0.588 | 26% |
| loop0-all (3,889) | independent, all-unique | 0.410 | 0.504 | 0.565 | 26% |
| loop1-all (9,025) | SE, all-unique | 0.397 | 0.494 | 0.557 | 19% |
| real-CoT (best) | own reasoning kept | 0.203 | 0.260 | 0.290 | **77%** |
| final-only | no think tags | 0.131 | 0.216 | 0.282 | 0% |

Reads: selection >> source (SE≈indep at matched selection, Δ=0.001); every code-only arm lifts
pass@k≥2; real-CoT collapse is a cap-hit/over-thinking effect (78% truncation); SE's +68 extra
covered problems don't transfer to this cross-platform benchmark at this scale.

## T5 — Test-time selection (Phase 6; 100-problem pilot, judges never see tests)
| judge | SVD (absolute) | V1 (pairwise) | vs RANDOM / ORACLE |
|---|---|---|---|
| Qwen3-4B (self) | 0.27 / 0.29 (below random) | 0.58 / 0.74 | random 0.573 / 0.710 |
| gpt-oss-120b | 0.65 / 0.64 | **0.80 / 0.81** | oracle 0.830 / 0.860 |

(ind-pool / SE-pool.) gpt-oss V1 recovers 88%/67% of the random→oracle gap. Filtering: gpt-oss SVD
precision 0.956 / recall 0.636. Saturation estimation: only absolute SVD works — gpt-oss r=0.647,
over-claim ≤3 (SE pool); pairwise structurally cannot (tournaments always have winners).

## T6 — Scale-up status (context)
code_contests loop0 (pop-8, 6,507 problems): 46.4% saturated 8/8 · 34.7% informative · 18.9%
impossible (bimodal) → 3,487 non-saturated; **loop1 running** — the loop0-vs-loop1 frontier on cc is
the pending §1-analogue. (cc "impossible" includes an unmeasured test-broken fraction — flagged.)
