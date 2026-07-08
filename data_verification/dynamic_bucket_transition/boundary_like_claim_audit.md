# Audit: "discovered 0→1 behaves like native 1/16 boundary"

**Scope.** Statistical + semantic check of that claim, using only existing
`tables/per_problem_loop_counts.csv` (oracle labels, canonical dedup; n=1093, loop0/1/2 complete).
No new generation, no re-grading, no repo files modified. Stats: `boundary_like_audit_rollup.json`.

## Verdict — **B. Directionally supported (underpowered on the equivalence part).**

The claim bundles three sub-claims of very different strength:
1. **"0→1 is the discovery bottleneck"** — *strongly supported* (well-powered).
2. **"once discovered, problems densify"** — *supported* (n=37, well-powered).
3. **"…behaves *like native 1/16*"** (equivalence) — *directional only*; the strict comparison is **n=18**, and the
   native-vs-discovered difference is **not statistically distinguishable from zero** — but neither is equivalence
   established. Absence of a significant difference at n=18 is *not* evidence of sameness.

So "boundary-like **densification**" is safe; "**behaves like** native 1/16" overstates.

---

## 1. Denominators (these are different groups — the source of the wording risk)

| group | definition | n | which claim uses it |
|---|---|---|---|
| hard-zero | loop0 raw==0 | **243** | discovery-timing denominator |
| first-solved@loop1 | loop0==0 **&** loop1 raw **≥1** | **37** | "81% stay solved / ~63% add canonical-unique" (followup) |
| → of which loop1 raw **==1** | = **discovered-raw** (strict) | **18** | "next-loop density ~2.4", the native-comparison |
| → of which loop1 raw **≥2** | stronger discoveries | 19 | excluded from strict native-1 comparison |
| native-raw-1 | loop0 raw==1 | 52 | Group A (raw) |
| native-canon-1 | loop0 canon-unique==1 | 56 | Group A (canonical) |
| discovered-canon-0→1 | loop0 canon==0 & loop1 canon==1 | 18 | Group B (canonical) — **the same 18** as discovered-raw |

**Key clarity point:** the "**81% / 63%**" figures come from **n=37** (any positive loop1 crossing), while the
"**~2.4 vs ~3.1 density**" comparison comes from **n=18** (crossed to *exactly* one). They are not the same denominator.
"First-solved at loop1" (≥1) ≠ "loop1 count = 1"; the strict boundary comparison must use the n=18 exactly-1 group,
because native-1/16 is itself an exactly-1 group. (discovered-raw and discovered-canonical are the identical 18
problems, so no duplicate-only discoveries exist here.)

## 2. Aligned metrics (native A vs discovered B)

| metric | A_raw native-1 (n=52) | B_raw discovered-0→1 (n=18) | A_canon native-1 (n=56) | B_canon discovered (n=18) |
|---|---|---|---|---|
| next-loop solved retention | 0.827 | 0.778 | 0.839 | 0.778 |
| P(drop to 0) | 0.173 | 0.222 | 0.161 | 0.222 |
| P(add raw correct) | 0.750 | 0.611 | 0.768 | 0.611 |
| P(add canonical-unique) | 0.712 | 0.611 | 0.679 | 0.611 |
| mean next raw | 3.71 | 2.78 | 4.39 | 2.78 |
| mean next canonical-unique | 3.08 | 2.44 | 2.98 | 2.44 |
| **median** next canonical-unique | 3.0 | 2.5 | 3.0 | 2.5 |
| next-bucket dist (raw) 0/1/2-4/5-8/9-15/16 | .17/.08/.40/.29/.06/0 | .22/.17/.39/.22/0/0 | — | — |
| next-bucket dist (canon) | .17/.12/.48/.21/.02/0 | .22/.17/.50/.11/0/0 | .16/.16/.46/.20/.02/0 | .22/.17/.50/.11/0/0 |

Every point estimate is **directionally lower for discovered** (retention −0.05, mean unique −0.6, adds-unique −0.10),
and only **native** ever reaches 9-15 (5.8% raw). Same modal bucket (2-4) and same "mostly densifies" shape.

## 3. Similarity (TV distance, bootstrap CI, permutation)

| comparison | observed TV | TV bootstrap 95% CI | mean-canon diff (A−B) | diff 95% CI | perm p-value |
|---|---|---|---|---|---|
| raw buckets (A_raw vs B_raw) | **0.139** | [0.085, 0.427] | +0.632 | **[−0.51, +1.70]** | **0.321** |
| canon buckets (A_canon vs B_canon) | **0.103** | [0.067, 0.383] | +0.538 | [−0.58, +1.57] | 0.380 |

- **Distributions are close** — TV ≈ 0.10–0.14 (0 = identical, 1 = disjoint) — but the **bootstrap CI is wide**
  (up to ~0.4), so "similar" and "moderately different" are both consistent with n=18.
- The **density gap (native ~0.6 unique higher) is not statistically significant**: permutation p ≈ 0.32–0.38, and the
  bootstrap CI on the difference **straddles 0**.
- **Interpretation:** under-powered. We can neither confirm the groups are the same nor show they differ. The honest
  read is "consistent with a similar densification regime, but n=18 cannot establish equivalence."

## 4. Safe-wording verdicts

| candidate wording | safe? | why |
|---|---|---|
| "Once discovered, hard-zero problems **behave like** native 1/16 boundary problems." | **No** | Asserts equivalence; every point estimate is weaker and n=18 cannot establish sameness (non-significance ≠ equivalence). Overstates. |
| "Once discovered, hard-zero problems show **boundary-like densification**." | **Yes** | Claims a densification *regime*, not equivalence; supported by n=37 (81% retain, 63% add unique) and n=18 (mean 2.4, modal bucket 2-4). |
| "**Directionally**, 0→1 problems resemble native 1/16 problems, **but the discovered arm is small**." | **Yes** | Explicitly directional + states the n caveat. Matches the data. |
| "0→1 is the discovery bottleneck; after crossing, problems **often densify** rather than merely re-emit one solution." | **Yes (strongest)** | Bottleneck is well-powered (243→37→20); "often densify" holds (P(add unique)=0.61, only ~17% stay at bucket-1); no equivalence claim. |

**Recommendation:** replace "behaves like native 1/16 boundary problems" with **"shows boundary-like densification"**
(or the bottleneck+densify wording), and keep the explicit n=18 caveat wherever native-vs-discovered magnitudes are quoted.

## 5. One-line Slack bullet for Sewon

> 0→1 is the discovery bottleneck (~11–15% of hard-zeros cross per loop); once across they show **boundary-like densification** (81% stay solved, ~63% add a new *unique* solution; next-loop ≈2.4 unique vs native-1's ≈3.1) — directionally native-like but **not statistically distinguishable at n=18**, so say "boundary-like densification," not "identical to native."

---

*Files: this report + `boundary_like_audit_rollup.json` + `scripts/boundary_like_audit.py`. No existing files modified.*
