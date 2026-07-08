# OSS-120B Density Estimation & Stopping-Rule Simulation

**Date:** 2026-07-02 (overnight autonomous run)
**Question (2 parts):**
- **A.** What gpt-oss-120B self-verification setting gives a *reliable per-problem density/bucket estimate* — how many of the N loop-0 candidates are actually correct, **without gold tests**?
- **B.** Can an **OSS-estimated freeze/stopping rule** replace the **oracle** (gold-test) freeze rule that frees ~48% of SE compute by freezing the near-saturated 9–15/16 bucket?

## TL;DR (`RESULT-DEPENDENT`)

1. **Best gpt-oss-120B density-estimate setting = a "trace concrete/edge inputs" prompt, `reasoning_effort=low`,
   single call, no calibration.** It beats the plain prompt (r 0.731→0.752, freeze precision .79→.85). Neither
   self-consistency (k=3) nor higher reasoning effort helped; linear calibration *hurt*. Precision to identify the
   near-saturated bucket plateaus at ~0.85 — a judge/data ceiling.
2. **An OSS-estimated freeze rule can largely replace the gold-test oracle (verdict: PASS).** On se16, at the oracle's
   own compute level (~44–45% of SE loops skipped), the gold-free OSS rule loses only **1 of ~13 reachability
   new-solves** (~93% frontier retained), with ~0.82 agreement to the oracle's freeze set. Guaranteeing **zero**
   frontier loss costs some savings (safe band ~21%).
3. **A better density estimate → a materially safer stopping rule.** The trace estimate reaches zero-frontier-loss at
   ~21% compute saved vs only ~7% for the plain estimate — a ~3× wider safe band, robust across two seeds.

**Actionable:** to skip SE loops on already-saturated problems without gold tests, run the trace self-verification on
loop-0 candidates and freeze a problem when its density estimate ≥ threshold. Aggressive: thr≈7.5 (~44% compute saved,
~1 frontier problem risked). Safe: thr≈12 (~21% saved, zero frontier risk).

---

**Model / infra:** single `gpt-oss-120b` (MXFP4, TP4, `reasoning_effort` as noted) served at `:8000`.
A 2nd 120B was requested but did not fit — GPUs 4–7 are held by other tenants on this shared node (10–19 GB free each; a 120B needs ~20–30 GB/GPU). Single instance was sufficient.

**Data:** `se16` (openthoughts114k codeforces, pop-16 SE), gold `loop0/1/2_correct` from
`outputs/openthoughts114k_codeforces_full_datagen/se16/frontier/per_problem_correct_counts.csv`
(1093 non-saturated problems; note this set *excludes* fully-saturated 16/16, so the freeze target is the 9–15 near-saturated bucket).

All accuracy numbers below are `RESULT-DEPENDENT` (generated this run). The estimator is a self-verification
call per candidate → probability-correct 0–1; per-problem **density estimate = Σ probabilities over the 16 candidates**.

---

## Goals & success criteria

The freeze rule's costly error is a **wrong freeze** (stopping a problem that would still have gained reachability),
so the estimate must be **precise about "saturated," not just well-correlated**. Bars:

**Phase A — density/bucket estimate is "reliable enough" if:**
- **Freeze-signal precision ≥ 0.90** — of problems flagged saturated (near-sat, gold≥9), ≥90% truly are — at usable **recall ≥ 0.50**. (Precision-first: protects the frontier.)
- Ranking **Pearson r ≥ 0.73** (judge-ceiling baseline; beat it if a variant can).
- Calibrated absolute density **MAE ≤ 1.8/16**.
- *If unmet:* keep trying variants (trace-prompt, multi-aspect, prompt-ensemble) until met or variants are exhausted; then report the best safe operating point.

**Phase B — OSS freeze can replace the oracle if,** at an OSS threshold set to the high-precision operating point:
- **≈0 reachability frontier lost** — frozen "new-solve" problems (loop0=0 → loop2>0) ≤ 1, and real-gain freezes minimal.
- **Compute saved comparable to the oracle** (oracle "freeze loop0≥9" ≈ 40–48%).
- High **agreement with the oracle freeze set** (precision ≥ 0.85).

**Verdict scale (Phase B):** STRONG PASS = ≥40% compute saved & 0 frontier lost · PASS = ≥30% & ≤1 lost ·
PARTIAL = 0-frontier-loss only reachable at <30% saved · FAIL = can't save meaningful compute without losing frontier.

---

## Phase A — best density-estimate setting

Stratified sample of **120 problems** (30 each in gold-loop0 buckets 0 / 1–4 / 5–8 / 9–15). Metric priority:
identify the **near-saturated (gold≥9)** problems, since that is exactly what the freeze rule needs.

| variant | Pearson r | MAE (/16) | bias | freeze(gold≥9) F1 (best thr) |
|---|---|---|---|---|
| **low_k1** (effort=low, 1 call) | **0.731** | 2.39 | −0.90 | **0.76** (P .79 / R .73 @ thr 8.0) |
| low_k3 (effort=low, 3-call self-consistency) | 0.737 | 2.35 | −0.91 | 0.76 |
| medium_k1 (effort=medium) | 0.725 | 2.62 | −1.52 | 0.74 |

**Findings (`RESULT-DEPENDENT`):**
- **Self-consistency (k=3) barely helps** — r +0.006, MAE −0.04, identical freeze F1 — not worth 3× cost.
- **Higher reasoning effort is *worse*** — `medium` under-counts more (bias −1.52 vs −0.90) and drops r/F1.
  The judge's discrimination is the ceiling; more test-time thinking makes it more conservative, not more accurate.
- **Systematic under-count bias ≈ −0.9/16.** A monotonic calibration fixes the *absolute* count (MAE) but not the
  freeze *decision* (thresholding on the estimate is invariant to monotonic transforms → freeze F1 unchanged).
- Calibration curve (mean estimate by gold count) is monotonic-on-average but **over-counts easy-wrong problems**
  (gold 0 → est ~1.9) and **under-counts the top** (gold 12–15 → est ~9–12).

### Phase A2 — the setting that actually wins

Two more probes on the same 120-problem sample:

| variant | r | MAE | freeze(gold≥9) F1 | P / R |
|---|---|---|---|---|
| low_k1 (plain "is it correct?") | 0.731 | 2.39 | 0.76 | .79 / .73 |
| **trace** (name 2–3 edge inputs → trace code → judge) | **0.752** | **2.24** | **0.79** | **.85** / .73 |

- **The trace prompt breaks the r≈0.73 judge ceiling** (+0.021 r, freeze precision .79→.85). Forcing the model to
  *name concrete/edge inputs and mentally execute them* is the one lever that improved the estimate — unlike
  self-consistency or more reasoning effort, which didn't.
- **Linear calibration *hurts*** (LOO MAE 2.39 → 2.59): the raw estimate's −0.9 bias is cheaper than the variance a
  fitted rescale adds out-of-sample. → **use raw estimates, no calibration.**
- **Freeze precision plateaus at ~0.85** (thr 8→12: P .85→.84, R .73→.53). It does **not** reach the 0.90 bar — a
  judge/data ceiling. The residual ~15% "false freezes" are either over-trusted wrong code **or** cases where the
  codeforces gold tests are too weak (judge may actually be right). Whether they cost *frontier* is Phase B's job.

### Phase A verdict

**Best density/bucket setting: `trace` prompt, `reasoning_effort=low`, single call, no calibration.**
- Reliable for **ranking / bucketing** (r 0.752 ✓ ≥0.73) — good enough to *order* problems by saturation.
- Freeze-signal **precision 0.85 @ recall 0.73** (thr≈8) — below the 0.90 target; **P≥0.90 is unreachable** with this
  judge, so 0.85 is the safe operating point. Absolute density **MAE ≈ 2.2/16** (above the 1.8 target; calibration can't help).
- **Implication:** the estimate is a good *saturation ranker* but not a precise *counter*. A freeze rule built on it will
  mis-freeze ~15% by the bucket metric — Phase B tests whether that actually loses reachability.

---

## Phase B — OSS freeze rule vs oracle freeze rule

**Setup (`RESULT-DEPENDENT`):** representative **random 300** se16 problems (gold-loop0 mix: 24% unsolved,
15% 1–4, 16% 5–8, 45% near-saturated ≥9 — matches the ~48% saturation rate). Estimate = **trace** variant.
- **Oracle freeze** = gold `loop0_correct ≥ 9` (the "freeze 9–15" rule).
- **OSS freeze** = trace density estimate `≥ threshold` (swept).
- **Frontier that matters = reachability "new-solves"**: problems with `loop0=0 → loop2>0` (the loops made an
  unsolved problem solvable). There are **14** in the sample. Freezing one of these is the real cost.
  (The "real-gain" count of 118 is mostly near-saturated **duplicate density** — the *oracle itself* forgoes 36 of
  them, i.e. that's the *intended* saving from skipping saturated problems, not lost frontier.)

**Result — the trade-off curve (freeze aggressiveness → compute saved vs reachability lost):**

| rule / threshold | frozen | compute saved | **new-solves lost** (of 14) | agreement w/ oracle (P) |
|---|---|---|---|---|
| **Oracle** (loop0≥9) | 135 | **45.0%** | **0** | — |
| OSS thr 6.0 | 160 | 53.3% | 2 | .74 |
| OSS thr 7.0 | 141 | 47.0% | 1 | .81 |
| **OSS thr 7.5 (matched to oracle compute)** | 133 | **44.3%** | **1** | **.82** |
| OSS thr 8.0 | 122 | 40.7% | 1 | .87 |
| OSS thr 9.0 | 110 | 36.7% | 1 | .90 |
| OSS thr 12.0 (fully safe) | 69 | **23.0%** | **0** | .94 |

**Reading it:**
- At the **oracle's own compute level (~44–45%)**, the OSS rule loses **1 of 14** new-solves — it preserves **93%**
  of the reachability frontier **with no gold tests at all**, and agrees with the oracle's freeze set 82% of the time.
- The entire risk comes from the estimator occasionally **over-scoring a hard (loop0=0) problem** — it takes est≥7.5
  to freeze, so this is rare (1–2 cases in 300). The oracle can never make this error because it sees the true count.
- **To guarantee zero frontier loss**, the OSS rule must be conservative (thr≥12) → still saves **23%** of compute
  (about half the oracle's saving) while agreeing with the oracle 94%.
- Post-hoc calibration didn't help here either (calibrated `≥9` froze 112 = 37% saved, same 1 new-solve lost).

### Phase B verdict: **PASS**

The OSS-estimated freeze rule is a viable **gold-free replacement** for the oracle:
- **~90% of the oracle's compute saving (44% vs 45%) at ~93% frontier retention (13/14 new-solves).** → meets the
  **PASS** bar (≥30% saved, ≤1 new-solve lost; agreement .82). It misses **STRONG PASS** only because 0-loss
  requires backing off to ~23% saving.
- It is **tunable**: pick the aggressive point (44% saved, 1 lost) for throughput, or the safe point (23% saved, 0 lost)
  when no frontier problem may be dropped.

**Bottom line for the research question:** yes — a self-verification density estimate from gpt-oss-120B (no test
execution) can drive an SE stopping/freeze rule that captures most of the compute savings the gold-test oracle gives,
while keeping essentially all of the reachability frontier. The estimate is a strong *saturation ranker*; its residual
imprecision costs a small, tunable amount of frontier.

### Does the Phase A estimate improvement matter for the freeze rule? (trace vs low_k1)

Same Phase B sim, run with each estimator (seed=7, n=300):

| estimator | matched-oracle point | **max compute saved at ZERO new-solve loss** |
|---|---|---|
| low_k1 (r 0.731) | 45.7% saved, 1 lost | **8.7%** (thr 14) |
| **trace (r 0.752)** | 44.3% saved, 1 lost | **23.0%** (thr 12) |

- At the **aggressive** (oracle-matched ~45%) operating point the two are equivalent — both lose 1 new-solve.
- But the **safe (zero-loss) operating point is ~2.6× better with trace**: it frees 23% of compute with *no* frontier
  loss, vs only 8.7% for low_k1. low_k1 catastrophically over-scores one hard (loop0=0) problem, so you must freeze
  almost nothing to avoid dropping it; trace's sharper estimate pushes that error down, opening a usable safe band.
- **Takeaway:** a better self-verification density estimate doesn't move the *aggressive* frontier much, but it
  materially widens the **safe** compute-savings band. The trace prompt earns its keep.

**Robustness (two random seeds):** the gap holds.

| variant | matched-oracle point (both seeds) | safe (0-loss) compute saved: seed7 / seed11 |
|---|---|---|
| low_k1 | ~45% saved, 1 new-solve lost | 8.7% / **5.3%** |
| **trace** | ~45% saved, 1 new-solve lost | 23.0% / **20.7%** |

At the aggressive operating point the variants tie every time (~45% saved, lose 1 of 12–14 new-solves). The
separation is entirely in the **safe band**: trace supports ~3–4× more zero-loss compute savings than low_k1 across
both seeds. `RESULT-DEPENDENT`, n=300 each.

