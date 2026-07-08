# Dynamic bucket-transition analysis (Sewon follow-up)

**What this is.** The earlier Sewon-deck heatmap was *static*: it grouped problems by their **loop-0** bucket and
showed density per loop. This asks the *dynamic* question she raised — **does a problem's previous-loop state
predict its next-loop behavior, and does a hard-zero problem that just earned its first correct solution then
densify like a problem that was born at 1/16?**

**Data & method (existing data only — no new generation, no re-grading, no repo modification).**
Source = `unique_correct_audit/per_problem_hashes.json`. Oracle correctness = the full-test grading cache
(`outputs/grading_cache/se16.jsonl`), which matches the frontier CSV; canonical dedup = the repo's tokenizer
canonicalization (same as the prior audit). **n = 1093 problems, all with loop0/1/2, 0 cache misses** (clean
denominators). Everything below is **oracle-only** — no self-verifier / OSS-judge labels enter this analysis.
Throughout: **problem-level "solved" (raw_correct>0) is kept separate from candidate-level density**, and
**raw correct-count is kept separate from canonical-unique correct-count**.

Buckets: `0 · 1 · 2-4 · 5-8 · 9-15 · 16` on both raw and canonical-unique counts (of 16 candidates).

---

## Headline totals (n=1093, of 16 candidates each)

| loop | Σ raw correct | Σ canonical-unique correct | problems solved (raw>0) |
|---|---|---|---|
| 0 | 8,177 | 7,432 | 850 |
| 1 | 10,567 | 8,446 | 872 |
| 2 | 11,101 | 8,350 | 877 |

The gap between the columns *is* the Sewon point: **raw density keeps climbing (+2,390 → +534) but canonical-unique
density grows loop0→1 (+1,014) then STALLS loop1→2 (−96), and problem-level solved barely moves (+22, +5).**
Later-loop "gains" are increasingly duplicate solutions, concentrated in the already-dense buckets (see §D).

---

## A. Does the previous-loop bucket predict next-loop density better than the static loop0 bucket?

**Yes, clearly.** Variance of a problem's **loop-2 canonical-unique density** explained (R²) by:
- **static loop-0 bucket: R² = 0.582**
- **previous-loop (loop-1) bucket: R² = 0.813**

Conditioning on the *immediately previous* loop is far more predictive than conditioning on the loop-0 origin.
(The loop-1 bucket is also one step closer in time, which contributes — but that is exactly the claim: the process
is closer to Markov-in-the-previous-loop than anchored to where a problem started.) **Implication: curriculum/freeze
decisions should read the latest loop's state, not the loop-0 bucket.**

Concrete transition behavior (row-normalized, `tables/transition_summary_by_prev_bucket.csv`):
- **Hard-zero (bucket 0)** crosses to solved at only **~11–15% per loop** (loop0→1: 0.152; loop1→2: 0.109) — a
  low, roughly constant discovery rate. ~85–89% stay at 0.
- **Boundary (bucket 1)** mostly densifies: native loop0=1 → loop1 improves bucket 75% of the time (mean next raw
  3.71), but ~17–33% fall back toward 0.
- **Near-saturated (bucket 9-15)** adds essentially **no new unique** solutions: mean Δ canonical-unique = **−0.12**
  (loop0→1) and **+0.09** (loop1→2), while raw still rises — pure copy amplification.

---

## B. Do native-1/16 and discovered-0→1 problems have similar next-loop dynamics?

Same qualitative regime; the discovered set is **modestly weaker**. (`tables/native1_vs_discovered01_{raw,canonical}.csv`)

| group | definition | next loop | n | mean next raw | mean next **canon-unique** | solved-retention | drop-to-0 |
|---|---|---|---|---|---|---|---|
| **A native-1** | loop0 raw=1 | loop1 | **52** | 3.71 | **3.08** | 0.83 | 0.17 |
| **B discovered 0→1** | loop0=0, loop1 raw=1 | loop2 | **18** | 2.78 | **2.44** | 0.78 | 0.22 |
| A-canonical | loop0 canon-u=1 | loop1 | 56 | 4.39 | 2.98 | 0.84 | 0.16 |
| B-canonical | loop0 canon-u=0, loop1 canon-u=1 | loop2 | 18 | 2.78 | 2.44 | 0.78 | 0.22 |

Both groups start at one correct solution and, one loop later, sit at **~2.4–3.1 mean unique-correct**, **retain
solved ~78–84%**, and **rarely reach 9-15** (native 5.8%, discovered 0%). The discovered set densifies a little less
and drops to zero a little more, but it is the **same boundary-densification regime**, ~80% of native strength.
**Caveat: the discovered group is small (n=18)** — this is directional evidence, not a tight estimate.

---

## C. Is Sewon's hypothesis supported?

**Hypothesis:** *"0→1 is the hard discovery step; once a hard-zero problem gets one correct solution, it enters a
boundary-like densification regime."*

**Supported (directionally; small n on the discovered arm).** Two legs:

1. **0→1 really is the hard step.** Of 243 hard-zeros (loop0=0), only **37 (15%) cross at loop1** and **20 (8%) at
   loop2**; **186 (77%) never cross through loop2**. The barrier is getting the *first* correct solution.
   (`tables/hard_zero_discovery_timing.csv`)
2. **After crossing, they densify like boundary problems.** Of the 37 first-solved-at-loop1: **81% stay solved** at
   loop2, only 19% fall back to 0, and **~62–65% add *more* unique/raw correct solutions**; their loop1→loop2 bucket
   moves are dominated by `1→2-4`, `1→5-8`, `2-4→…` (up or stable). Their next-loop density (~2.4 unique) matches
   native-1 problems (~3.1) to within the small-sample noise. (`tables/hard_zero_loop1_first_solved_followup.csv`)

So the discovery step is the bottleneck, and post-discovery behavior looks boundary-like — as Sewon predicted.

---

## D. What this implies for curriculum

- **Keep hard-zero (0-bucket) problems in the population for frontier discovery.** They convert at only ~11–15%/loop,
  but they are the *only* source of new solved problems — the entire reachability frontier comes from 0→≥1 crossings.
- **Once a hard-zero is discovered (0→1), treat it as a boundary problem** — route it into boundary-style
  densification / self-distillation, because it then behaves like a native 1/16 problem (§B, §C).
- **Freeze near-solved 9-15 (and 16) when unique density stops improving.** These buckets add ~0 or **negative**
  canonical-unique per loop (9-15 Δcanon ≈ −0.12 / +0.09; raw-16 Δcanon = **−1.30** loop1→2) — extra loops there buy
  duplicates. This is the same saturation signal the OSS stopping-rule work exploits.
- **Do NOT use a pure boundary-only curriculum that drops the 0-bucket.** Dropping hard-zeros removes the discovery
  source and kills frontier growth (consistent with the earlier "pure-boundary loses 57/58 frontier" finding).

Net: a **state-dependent** curriculum — discover on 0-bucket, densify on boundary (native *and* freshly-discovered),
freeze on saturated — dominates any static loop-0-bucket split.

---

## E. What remains unanswerable without new generation

- **The 20 problems first solved at loop2 have no observable post-discovery dynamics** — we only see them *arrive* at
  loop2 and cannot tell whether they too enter boundary-like densification. **A targeted loop-3 pass on those 20 (and
  on the 186 still-unsolved, to measure continued conversion) is required.** This first pass needs no new generation;
  loop-3 is the only genuinely new data needed, and only for the loop2-discovered set.
- The discovered-0→1 arm is n=18; loop-3 would also enlarge the discovered pool and tighten the §B/§C comparison.

---

## 4–5 line summary for Sewon

- The old heatmap was static (by loop-0 bucket); this uses previous-loop → next-loop transitions, and the previous-loop bucket predicts next-loop density far better (R² 0.81 vs 0.58).
- 0→1 is genuinely the hard step: only ~15% of hard-zeros cross per loop, 77% never cross through loop2.
- Once a hard-zero earns its first correct solution, it densifies like a native 1/16 problem (81% stay solved, ~63% add more unique solutions; next-loop density ~2.4 vs native ~3.1) — supporting the "discover, then boundary-densify" picture (discovered arm is n=18, so directional).
- Near-saturated 9-15/16 add ~0 or negative *unique* density per loop — safe to freeze; hard-zeros must stay in for discovery.
- Only new data needed: a targeted loop-3 on the 20 problems first solved at loop2 (their post-discovery dynamics are unobservable without it).

---

### Created files
- `tables/per_problem_loop_counts.csv` — per problem × loop: raw / exact-unique / canonical-unique correct, solved_any, raw & canonical buckets (1093×3 rows).
- `tables/raw_bucket_transition_counts.csv`, `tables/raw_bucket_transition_probs.csv` — raw-bucket transition matrices (loop0→1 & loop1→2, counts + row-normalized).
- `tables/canonical_bucket_transition_counts.csv`, `tables/canonical_bucket_transition_probs.csv` — same for canonical-unique buckets.
- `tables/transition_summary_by_prev_bucket.csv` — per prev-bucket: n, mean next raw/canon, mean Δ raw/canon, P(improve/same/drop/drop-to-zero), both loop-pairs, both bucket types.
- `tables/native1_vs_discovered01_raw.csv`, `tables/native1_vs_discovered01_canonical.csv` — Group A (native-1) vs Group B (discovered 0→1) next-loop outcomes + bucket distributions.
- `tables/hard_zero_discovery_timing.csv` — hard-zero first-solved@loop1 / @loop2 / never (denominator 243).
- `tables/hard_zero_loop1_first_solved_followup.csv` — loop2 fate of the 37 loop1-first-solved (retain/drop/densify + bucket transitions).
- `figures/raw_transition_matrix_loop0_to_loop1.png`, `figures/raw_transition_matrix_loop1_to_loop2.png`
- `figures/canonical_transition_matrix_loop0_to_loop1.png`, `figures/canonical_transition_matrix_loop1_to_loop2.png`
- `figures/native1_vs_discovered01_next_loop_density.png` — slide-ready answer to the core question.
- `rollup.json` — all key statistics in one JSON.
- `scripts/dynamic_bucket_transition.py` — the analysis (re-runnable; reads only the audit hashes file).
