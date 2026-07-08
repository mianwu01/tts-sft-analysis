# Sewon focused follow-up — strict native-1 vs discovered-0→1, and where canonical-unique gains come from

**Data:** existing `per_problem_loop_counts.csv` only (n=1093, loop0/1/2 complete; oracle full-test correctness;
canonical-unique dedup from the prior audit). No new generation, no re-grading, no repo files modified.
**Main diversity metric = canonical-unique correct count** (raw kept as a secondary table). "Solved" = raw>0 is
problem-level and kept separate from candidate-level density. Denominators stated throughout.

---

## Denominators (explicit — these are different groups)

| group | definition | n |
|---|---|---|
| first-solved@loop1 | loop0=0, loop1 raw>0 (**any** crossing) | **37** |
| strict 0→1 (canonical) | loop0 canon=0, loop1 canon=1 | **18** |
| strict 0→1 (raw) | loop0 raw=0, loop1 raw=1 | 18 |
| native-1 (canonical) | loop0 canon=1 | **56** |
| native-1 (raw) | loop0 raw=1 | 52 |

The strict native-vs-discovered comparison uses **native-1 (n=56)** vs **strict 0→1 (n=18)** — *not* the n=37
first-solved group. "First-solved at loop1" (≥1) is a superset and is used only for the discovery-followup counts.

## Part A — strict native-1/16 vs discovered-0→1 (canonical-unique, MAIN)

| metric | A: native-1 (n=56) | B: discovered 0→1 (n=18) |
|---|---|---|
| prev-loop canonical-unique | 1 | 1 |
| **next-loop mean canonical-unique** | **2.98** (95% CI 2.41–3.59) | **2.44** (95% CI 1.61–3.39) |
| next-loop median canonical-unique | 3.0 | 2.5 |
| mean Δ canonical-unique | +1.98 | +1.44 |
| median Δ canonical-unique | +2.0 | +1.5 |
| % stay solved | 0.839 | 0.778 |
| % drop to zero | 0.161 | 0.222 |
| **% add canonical-unique** | **0.679** (CI 0.55–0.79) | **0.611** (CI 0.39–0.83) |
| % stay at exactly 1 | 0.161 | 0.167 |
| % move to 2-4 / 5-8 / 9-15 / 16 | 0.46 / 0.20 / 0.02 / 0 | 0.50 / 0.11 / 0 / 0 |
| next-bucket dist (0/1/2-4/5-8/9-15/16) | .16/.16/.46/.20/.02/0 | .22/.17/.50/.11/0/0 |

*(raw secondary, `partA_native1_vs_discovered01_raw.csv`: A n=52 next-mean-canon 3.08; B n=18 next-mean-canon 2.44 —
same pattern.)*

**Conclusion: directionally supported.** Discovered-0→1 densifies in the same regime as native-1 (both go 1 →
~2.4–3.0 unique, both add unique ~61–68%, both peak at bucket 2-4), but every point estimate is a little weaker
(mean −0.5 unique, retention −0.06) and **the 95% CIs overlap heavily** — at n=18 we cannot distinguish the two, and
cannot claim equivalence. Verdict: **directionally supported, not strongly supported.**

## Part B — where do canonical-unique gains come from? (dynamic previous-loop buckets, pooled loop0→1 + loop1→2)

| prev-loop bucket | n transitions | mean Δ canon | **net total Δ canon** | gross-positive share | %add | %stay-same-bucket | %move-down |
|---|---|---|---|---|---|---|---|
| 0 (hard) | 464 | +0.31 | **+143** | 0.06 | 0.13 | 0.87 | 0.00 |
| 1 (boundary) | 95 | +1.52 | **+144** | 0.07 | 0.58 | 0.23 | 0.19 |
| 2-4 | 267 | +1.60 | **+427** | 0.22 | 0.46 | 0.40 | 0.14 |
| 5-8 | 340 | +1.40 | **+477** | 0.30 | 0.42 | 0.39 | 0.19 |
| 9-15 (near-sat) | 969 | **−0.20** | **−191** | 0.36 | 0.08 | 0.80 | 0.12 |
| 16 (saturated) | 51 | **−1.61** | **−82** | 0.00 | 0.00 | 0.26 | 0.74 |

**The honest metric is net total Δ, not "gross-positive share."** Net canonical-unique gain concentrates in the
**mid buckets 2-4 (+427) and 5-8 (+477)**, with boundary-1 (+144) and hard-0 (+143) smaller. **9-15 is net NEGATIVE
(−191)** and 16 is −82. ⚠️ **Watch the trap:** 9-15 has the *largest* gross-positive share (0.36) purely because it
holds the most problems (n=969) and churns — but it *loses* more unique than it gains (net −191, 80% stay in-bucket).
So by contribution-to-actual-density-growth, 9-15 is a net *drain*, not a source.

## Part C — static loop0-bucket view vs dynamic previous-loop view (canonical-unique)

| bucket | STATIC: loop0→loop2 mean Δ canon (n) | DYNAMIC: mean Δ per transition | DYNAMIC: share of positive gain |
|---|---|---|---|
| 0 | +0.76 (n=243) | +0.31 | 0.06 |
| 1 | +3.43 (n=56) | +1.52 | 0.07 |
| 2-4 | +3.72 (n=146) | +1.60 | 0.22 |
| 5-8 | +2.27 (n=177) | +1.40 | 0.30 |
| 9-15 | **−0.86** (n=471) | **−0.20** | 0.36 (size-inflated; net negative) |

**Static and dynamic agree on the qualitative answer.** Both show gains concentrated in buckets **1–8** and a **net
loss on 9-15**. The dynamic view adds precision: (i) the biggest *net* density is added by **2-4 and 5-8**, not the
hard-zero bucket; (ii) hard-0 mainly contributes *discovery* (0→1 crossings, +0.31/transition) rather than density;
(iii) 9-15 is high-churn with net erosion.

**Answers to the three Part-C questions:**
- **Does "unique density improves mainly on hard/boundary problems" still hold?** *Partly — restate it.* Gains
  concentrate on **boundary-through-partially-solved (buckets 1–8)**. The pure hard-zero (0) bucket contributes the
  *reachability frontier* (crossings) but little density; near-saturated 9-15/16 **lose** unique density. So the
  accurate wording is "unique-density gains come from the boundary and partially-solved buckets (1–8), **not** the
  near-saturated ones."
- **Which exact dynamic buckets contribute most?** By net total Δ: **5-8 (+477) and 2-4 (+427)**; by per-problem rate:
  **1 (+1.52) and 2-4 (+1.60)**.
- **Does 9-15 contribute positive unique gain?** **No — net negative (−191, mean −0.20/transition), 80% stay in
  bucket.** It is duplication/churn, not unique growth. (Its high gross-positive *share* is a size artifact.)

## Part D — figures (`figures/`)
- `native1_vs_discovered01_canonical_comparison.png` — native-1 vs discovered-0→1: next-loop mean unique (with 95% CI), %add-unique, %drop-to-zero.
- `dynamic_bucket_gain_by_previous_bucket.png` — mean Δ canonical-unique by previous-loop bucket (loop0→1 vs loop1→2); shows positive on 0–8, negative on 9-15/16.
- `dynamic_bucket_gain_contribution.png` — share of total positive canonical gain by previous-loop bucket.
- `previous_to_next_bucket_transition_canonical.png` — pooled previous→next canonical-unique transition matrix (row-normalized).

---

## Part E

**1. Sewon's exact question — "when a 0/16 problem becomes 1/16, does it then behave like a native 1/16 boundary
problem?"** Directionally yes, but the strict test is underpowered. The 18 problems that cross exactly 0→1 by loop1
go on to a next-loop density of ~2.44 canonical-unique (median 2.5), add a new unique solution 61% of the time, and
stay solved 78% — the *same qualitative densification regime* as the 56 native-1/16 problems (~2.98 unique, 68% add,
84% stay). Every native number is modestly higher, and the 95% CIs overlap (discovered mean CI 1.61–3.39 contains the
native mean 2.98), so we cannot establish equivalence — only that discovered-0→1 shows boundary-*like* densification.

**2. "Under dynamic previous-loop buckets, where does unique-correct density gain actually come from?"** From the
**boundary and partially-solved states (buckets 1–8)**: net canonical-unique gain is dominated by 5-8 (+477) and 2-4
(+427), with boundary-1 (+144) and hard-0 (+143) contributing less; the hard-0 bucket's real role is *discovery*
(0→1 crossings) rather than density. The **near-saturated 9-15 bucket is a net drain (−191)** and 16 is −82 — extra
loops there churn duplicates and lose unique solutions. Conditioning on the previous loop makes this sharper than the
static loop0 view, though both agree qualitatively.

**3. Slack bullets for Sewon (safe):**
- Strict test uses native-1 (n=56) vs *exactly* 0→1 (n=18) — not the n=37 "first-solved" group.
- Discovered 0→1 shows **boundary-like densification** (~2.4 next-loop unique, 61% add a unique solution, 78% stay solved) vs native-1 (~3.0, 68%, 84%) — directionally alike, CIs overlap, so not "identical" (n=18).
- Under dynamic buckets, net unique-density gain comes from **boundary/partially-solved (buckets 1–8)**; hard-0's role is *discovery*, not density.
- **9-15 is a net drain** on unique density (−191 total, −0.20/loop): later loops there add duplicates, not new solutions → safe to freeze.
- Static loop0 and dynamic previous-loop views agree; dynamic just localizes gains to 2-4 and 5-8.

**4. Wording recommendation.** Safest = **"After first discovery, hard-zero problems often continue to gain unique
solutions, but strict equivalence to native 1/16 is underpowered."** Also safe: **"0→1 problems show boundary-like
densification."** **Avoid** "0→1 problems behave like native 1/16" (asserts an equivalence the n=18 sample cannot
support).

---

### Created files (all new; no existing files modified)
- `sewon_focused_followup_summary.md` (this report), `rollup.json`
- `tables/partA_native1_vs_discovered01_canonical.csv`, `tables/partA_native1_vs_discovered01_raw.csv`
- `tables/partB_canonical_gain_by_prev_bucket.csv`, `tables/partB_raw_gain_by_prev_bucket.csv`
- `tables/partC_static_vs_dynamic_canonical.csv`
- `figures/native1_vs_discovered01_canonical_comparison.png`, `figures/dynamic_bucket_gain_by_previous_bucket.png`, `figures/dynamic_bucket_gain_contribution.png`, `figures/previous_to_next_bucket_transition_canonical.png`
- `scripts/sewon_focused_followup.py`
