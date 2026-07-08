# Phase 8 — EFT / self-evolution fine-tuning data manifests (NO training started)

Built by `scripts/build_eft_manifests.py` from verified per-candidate oracle grades
(`tables/per_candidate_grades.jsonl.gz`; se16 run, loops 0–2, 1,093 problems) and, for the
verifier-filtered ablation, the gpt-oss-120b SVD accept sets (test-free labels).
Manifests reference candidates by `(shard, loop, index)` into the on-disk checkpoints —
no solution text is duplicated. Held-out LCBv6 problems appear in **no** manifest.

| manifest | rows | design |
|---|---|---|
| `final_correct_only.csv` | 9,141 | unique correct candidates of each problem's LAST solved loop (the "SFT on final solutions" arm; per-problem best-selection to be applied downstream) |
| `evolution_chain.csv` | 136 | for the 58 beyond-frontier problems: unique correct candidates at every loop ≤ first-solve loop (Harman's "fine-tune on the evolution process" idea, positives-only) |
| `boundary_only.csv` | 6,004 | all unique corrects of loop0-bucket 1–8 problems (boundary curriculum arm) |
| `all_problem.csv` | 22,894 | maximal positive set: every unique correct across loops (equals the verified cumulative-unique count — consistency check ✓) |
| `positive_negative_pairs.csv` | 3,984 (1,992 pairs) | per problem×loop: 1 full-pass positive + 1 failed negative from the same population (DPO/preference or negative-learning arm) |
| `verifier_filtered.csv` | 756 | **test-free** positives: gpt-oss SVD accepts on the SE pool (pilot-100); `oracle_truth` column included — measured precision 0.956, so ~4.4% are false positives by construction |

## Label sources
All labels oracle full-pass on hidden codeforces tests except `verifier_filtered.csv`
(strong-judge labels; oracle truth carried alongside for audit). `leakage_risk` per row;
see `leakage_audit.md` — oracle use is train-side selection only.

## Known gaps (flagged, not silently missing)
- **True process/lineage chains are not reconstructable from checkpoints**: the SE client does not
  record which parent candidates fed each recombination. `evolution_chain.csv` therefore contains
  correct-per-loop *state* chains, not parent→child traces. To get real lineage, generation must be
  re-run with the client's routing/audit output retained (`<out>.raw.json` `routing_details`) — TODO
  before any process-supervision EFT.
- Negative rows in `positive_negative_pairs.csv` are capped at 1/problem/loop to keep the manifest
  balanced; the full negative pool (~6.6k failed candidates/loop) is recoverable from
  `per_candidate_grades.jsonl.gz` (passed=false rows).
- `verifier_filtered` covers only the 100-problem pilot pools — scaling it to the 1,093 (or the
  cf_cc 3,487) requires running the gpt-oss judge at scale (cost: ~64 judge calls/problem).
