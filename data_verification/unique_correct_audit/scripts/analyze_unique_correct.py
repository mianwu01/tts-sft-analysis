#!/usr/bin/env python3
"""Unique-correct audit part 2: consume per_problem_hashes.json (from harvest_correct_hashes.py)
and emit all tables, figures, and the summary markdown.

Buckets are by THIS-RUN loop0 raw correct count (the same axis the current slide uses):
  0/16, 1/16, 2-4/16, 5-8/16, 9-15/16.  (No non-saturated problem has loop0==16.)
Loops: 0, 1, 2 (loop3 excluded: partial + cache misses).

Definitions (see harvest script docstring for normalization details):
  raw_correct               = # oracle-correct candidates (of 16)               [current slide]
  exact_unique_correct      = # distinct correct after exact_norm  (minimal ws)
  canonical_unique_correct  = # distinct correct after canonical_norm (tokenizer, comment/ws-stripped)
  duplication_factor        = raw / max(canonical_unique, 1)        [solved problem-loops only]
  frac_dup                  = 1 - canonical_unique / raw            [raw>0]
  new_unique_correct[L]     = # canonical-correct hashes at loop L not correct at any loop < L
  near_dup_unique           = # token-Jaccard>=0.90 clusters among correct candidates (approx.)
All correctness is ORACLE (full-test cache), kept separate from candidate-level diversity.
"""
import csv
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/unique_correct_audit"
LOOPS = (0, 1, 2)
BUCKETS = [("0", lambda c: c == 0), ("1", lambda c: c == 1),
           ("2-4", lambda c: 2 <= c <= 4), ("5-8", lambda c: 5 <= c <= 8),
           ("9-15", lambda c: 9 <= c <= 15)]
NEAR_DUP_JACCARD = 0.90

data = json.load(open(f"{OUT}/per_problem_hashes.json"))
PROB = data["problems"]
CLASSES = data["classes"]
META = data["meta"]


# ---------- per-problem derived metrics ----------
def token_set(code):
    # coarse token 1-gram set for approximate near-dup Jaccard (diagnostic only)
    import re
    return set(re.findall(r"[A-Za-z_]\w*|\d+|[^\s\w]", code or ""))


def near_dup_clusters(codes):
    """Union-find over correct candidates: link a<->b if Jaccard(token_set) >= threshold.
    Returns number of clusters (approximate 'semantic-ish' unique count). Diagnostic only."""
    n = len(codes)
    if n <= 1:
        return n
    sets = [token_set(c) for c in codes]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            a, b = sets[i], sets[j]
            if not a and not b:
                sim = 1.0
            else:
                u = len(a | b)
                sim = (len(a & b) / u) if u else 1.0
            if sim >= NEAR_DUP_JACCARD:
                parent[find(i)] = find(j)
    return len({find(i) for i in range(n)})


P = {}  # pid -> dict of per-loop metrics
for pid, loops in PROB.items():
    m = {"class": CLASSES.get(pid, "unknown")}
    seen_canon = set()
    for L in LOOPS:
        d = loops.get(str(L)) or loops.get(L)
        if d is None:
            m[L] = None
            continue
        raw = d["raw_correct"]
        exact_set = set(d["exact_hashes"])
        canon_list = d["canon_hashes"]
        canon_set = set(canon_list)
        new_set = canon_set - seen_canon
        near = near_dup_clusters(d["correct_codes"])
        m[L] = {
            "raw": raw,
            "exact_unique": len(exact_set),
            "canon_unique": len(canon_set),
            "canon_set": canon_set,
            "new_unique": len(new_set),
            "near_dup_unique": near,
            "solved": raw > 0,
        }
        seen_canon |= canon_set
    P[pid] = m

# bucket assignment by loop0 raw
def bucket_of(pid):
    d0 = P[pid].get(0)
    if d0 is None:
        return None
    c = d0["raw"]
    for name, pred in BUCKETS:
        if pred(c):
            return name
    return None  # (would be a loop0==16; none exist)


BK = defaultdict(list)
for pid in P:
    b = bucket_of(pid)
    if b is not None:
        BK[b].append(pid)

bnames = [b for b, _ in BUCKETS]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


# ---------- TABLE 1: raw_vs_unique_by_bucket_loop.csv ----------
t1 = []
heat_raw = defaultdict(dict)
heat_canon = defaultdict(dict)
heat_dup = defaultdict(dict)
for b in bnames:
    pids = BK[b]
    for L in LOOPS:
        recs = [P[p][L] for p in pids if P[p][L] is not None]
        solved = [r for r in recs if r["solved"]]
        raws = [r["raw"] for r in recs]
        exu = [r["exact_unique"] for r in recs]
        cnu = [r["canon_unique"] for r in recs]
        sum_raw = sum(r["raw"] for r in solved)
        sum_cnu = sum(r["canon_unique"] for r in solved)
        row = {
            "bucket_loop0": b, "loop": L, "n_problems": len(recs), "n_solved": len(solved),
            "mean_raw_correct": round(mean(raws), 3),
            "mean_exact_unique": round(mean(exu), 3),
            "mean_canonical_unique": round(mean(cnu), 3),
            "pooled_dup_factor": round(sum_raw / sum_cnu, 3) if sum_cnu else "",
            "mean_dup_factor_solved": round(mean([r["raw"] / max(r["canon_unique"], 1) for r in solved]), 3) if solved else "",
            "pooled_frac_dup": round(1 - sum_cnu / sum_raw, 4) if sum_raw else "",
            "mean_frac_dup_solved": round(mean([1 - r["canon_unique"] / r["raw"] for r in solved]), 4) if solved else "",
            "mean_near_dup_unique": round(mean([r["near_dup_unique"] for r in recs]), 3),
        }
        t1.append(row)
        heat_raw[b][L] = mean(raws)
        heat_canon[b][L] = mean(cnu)
        heat_dup[b][L] = (sum_raw / sum_cnu) if sum_cnu else float("nan")

with open(f"{OUT}/tables/raw_vs_unique_by_bucket_loop.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(t1[0]))
    w.writeheader()
    w.writerows(t1)

# ---------- TABLE 3: duplication_by_bucket_loop.csv (+ cross-loop erosion cols) ----------
# cross-loop (loop1 -> loop2) per bucket, over problems solved at loop1
t3 = []
for b in bnames:
    pids = BK[b]
    for L in LOOPS:
        recs = [P[p][L] for p in pids if P[p][L] is not None]
        solved = [r for r in recs if r["solved"]]
        sum_raw = sum(r["raw"] for r in solved)
        sum_cnu = sum(r["canon_unique"] for r in solved)
        sum_exu = sum(r["exact_unique"] for r in solved)
        t3.append({
            "bucket_loop0": b, "loop": L, "n_solved": len(solved),
            "sum_raw_correct": sum_raw, "sum_exact_unique": sum_exu, "sum_canonical_unique": sum_cnu,
            "pooled_dup_factor": round(sum_raw / sum_cnu, 3) if sum_cnu else "",
            "pooled_frac_dup_candidates": round(1 - sum_cnu / sum_raw, 4) if sum_raw else "",
            "exact_vs_canonical_extra_merge": sum_exu - sum_cnu,  # how many more canonical merges than exact
        })
with open(f"{OUT}/tables/duplication_by_bucket_loop.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(t3[0]))
    w.writeheader()
    w.writerows(t3)

# ---------- TABLE 2: new_unique_by_bucket_loop.csv ----------
t2 = []
heat_new = defaultdict(dict)
for b in bnames:
    pids = BK[b]
    for L in LOOPS:
        recs = [(p, P[p][L]) for p in pids if P[p][L] is not None]
        newu = [r["new_unique"] for _, r in recs]
        solved = [(p, r) for p, r in recs if r["solved"]]
        n_new = sum(1 for x in newu if x >= 1)
        # solved-only-copied: solved this loop but 0 new canonical (all repeats of earlier loops)
        only_copied = sum(1 for _, r in solved if r["new_unique"] == 0)
        row = {
            "bucket_loop0": b, "loop": L, "n_problems": len(recs), "n_solved": len(solved),
            "n_problems_with_new_unique": n_new,
            "mean_new_unique": round(mean(newu), 3),
            "total_new_unique": sum(newu),
            "n_solved_only_copied_from_earlier": ("" if L == 0 else only_copied),
            "frac_solved_only_copied": ("" if L == 0 else (round(only_copied / len(solved), 4) if solved else "")),
        }
        t2.append(row)
        heat_new[b][L] = mean(newu)
with open(f"{OUT}/tables/new_unique_by_bucket_loop.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(t2[0]))
    w.writeheader()
    w.writerows(t2)

# ---------- Cross-loop erosion/amplification (loop1 -> loop2), per bucket ----------
erosion = []
for b in bnames:
    pids = BK[b]
    lost_all = retained = introduced = only_amp = solved1 = solved2 = 0
    for p in pids:
        r1, r2 = P[p].get(1), P[p].get(2)
        if r1 is None or r2 is None:
            continue
        if r1["solved"]:
            solved1 += 1
            if not r2["solved"]:
                lost_all += 1
        if r2["solved"]:
            solved2 += 1
            prev = P[p][0]["canon_set"] | r1["canon_set"]
            has_prev = len(r2["canon_set"] & prev) > 0
            has_new = r2["new_unique"] > 0
            if has_prev:
                retained += 1
            if has_new:
                introduced += 1
            if has_prev and not has_new:
                only_amp += 1
    erosion.append({
        "bucket_loop0": b, "n_solved_loop1": solved1, "n_solved_loop2": solved2,
        "loop1_solved_lost_all_at_loop2": lost_all,
        "loop2_retained_a_prev_canonical": retained,
        "loop2_introduced_new_canonical": introduced,
        "loop2_only_amplified_no_new": only_amp,
    })

# ---------- TABLE 5: frontier_unique_correct_detail.csv (0/16 hard-zero bucket) ----------
hz = BK["0"]
fr_rows = []
for p in sorted(hz):
    r0, r1, r2 = P[p][0], P[p][1], P[p][2]
    first_solved = ""
    for L in LOOPS:
        if P[p][L]["solved"]:
            first_solved = L
            break
    new_vs_l1 = len(r2["canon_set"] - r1["canon_set"]) if r2["solved"] else 0
    fr_rows.append({
        "problem_id": p, "class": P[p]["class"],
        "loop0_raw": r0["raw"], "loop1_raw": r1["raw"], "loop2_raw": r2["raw"],
        "loop1_canonical_unique": r1["canon_unique"], "loop2_canonical_unique": r2["canon_unique"],
        "loop1_new_unique": r1["new_unique"], "loop2_new_unique": r2["new_unique"],
        "first_solved_loop": first_solved,
        "loop2_solved": int(r2["solved"]),
        "loop2_new_canonical_vs_loop1": new_vs_l1,
    })
with open(f"{OUT}/tables/frontier_unique_correct_detail.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(fr_rows[0]))
    w.writeheader()
    w.writerows(fr_rows)

# hard-zero roll-up
hz_solved_by_loop = {L: sum(1 for p in hz if P[p][L]["solved"]) for L in LOOPS}
hz_ever = [p for p in hz if any(P[p][L]["solved"] for L in LOOPS)]
# multiplicity at the LAST loop where solved (best evidence of diversity)
def last_solved_loop(p):
    ls = [L for L in LOOPS if P[p][L]["solved"]]
    return ls[-1] if ls else None
hz_exactly1 = hz_multi = 0
for p in hz_ever:
    L = last_solved_loop(p)
    cu = P[p][L]["canon_unique"]
    if cu == 1:
        hz_exactly1 += 1
    elif cu > 1:
        hz_multi += 1
hz_l2_new_vs_l1 = sum(1 for p in hz if P[p][2]["solved"] and len(P[p][2]["canon_set"] - P[p][1]["canon_set"]) > 0)
hz_l2_solved_not_l1 = sum(1 for p in hz if P[p][2]["solved"] and not P[p][1]["solved"])

# ---------- FIGURES ----------
def heatmap(hd, title, cbar, fname, vmax, fmt="{:.1f}", cmap="Greys", white_above=None):
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    grid = np.array([[hd[b].get(L, np.nan) for L in LOOPS] for b in bnames])
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=vmax)
    wa = white_above if white_above is not None else vmax * 0.55
    for i, b in enumerate(bnames):
        for j, L in enumerate(LOOPS):
            v = hd[b].get(L)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                ax.text(j, i, fmt.format(v), ha="center", va="center",
                        color=("white" if v > wa else "black"), fontsize=11)
    ax.set_xticks(range(len(LOOPS)))
    ax.set_xticklabels([f"loop{L}\n(cum {(L+1)*16} gen)" for L in LOOPS])
    ax.set_yticks(range(len(bnames)))
    ax.set_yticklabels([f"{b}/16" for b in bnames])
    ax.set_ylabel("initial (loop0) raw-correct bucket")
    ax.set_title(title, fontsize=10)
    fig.colorbar(im, label=cbar)
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)


sub = "n=1,093 non-saturated codeforces · oracle full-test (cache-verified, 0 miss)"
heatmap(heat_raw, "se16: mean RAW correct-candidate count (of 16) per bucket per loop\n"
        "[NOT deduplicated — the current slide]\n" + sub,
        "mean raw correct of 16", f"{OUT}/figures/raw_correct_heatmap.png", vmax=16)
heatmap(heat_canon, "se16: mean CANONICAL-UNIQUE correct count per bucket per loop\n"
        "[distinct programs, comments/whitespace stripped]\n" + sub,
        "mean canonical-unique correct", f"{OUT}/figures/canonical_unique_correct_heatmap.png", vmax=16)
heatmap(heat_dup, "se16: DUPLICATION FACTOR (raw ÷ canonical-unique) per bucket per loop\n"
        "[1.0 = no dups; >1 = copy amplification · solved problem-loops]\n" + sub,
        "duplication factor", f"{OUT}/figures/duplication_factor_heatmap.png",
        vmax=3.0, fmt="{:.2f}", cmap="OrRd", white_above=2.1)
heatmap(heat_new, "se16: mean NEW canonical-unique correct solutions per bucket per loop\n"
        "[distinct programs not seen correct in any earlier loop]\n" + sub,
        "mean new canonical-unique", f"{OUT}/figures/new_unique_correct_heatmap.png",
        vmax=8, fmt="{:.2f}", white_above=4.4)

# ---------- roll-up JSON for the summary writer ----------
rollup = {
    "meta": META,
    "bucket_counts": {b: len(BK[b]) for b in bnames},
    "totals_by_loop": {},
    "erosion": erosion,
    "hard_zero": {
        "n": len(hz),
        "solved_by_loop": hz_solved_by_loop,
        "ever_solved": len(hz_ever),
        "ever_solved_exactly1_canonical_at_last_solved_loop": hz_exactly1,
        "ever_solved_multi_canonical_at_last_solved_loop": hz_multi,
        "loop2_solved_with_new_canonical_vs_loop1": hz_l2_new_vs_l1,
        "loop2_solved_not_solved_at_loop1": hz_l2_solved_not_l1,
    },
}
for L in LOOPS:
    recs = [P[p][L] for p in P if P[p][L] is not None]
    solved = [r for r in recs if r["solved"]]
    sum_raw = sum(r["raw"] for r in recs)
    sum_exu = sum(r["exact_unique"] for r in recs)
    sum_cnu = sum(r["canon_unique"] for r in recs)
    sum_new = sum(r["new_unique"] for r in recs)
    rollup["totals_by_loop"][L] = {
        "n_problems": len(recs), "n_solved": len(solved),
        "sum_raw": sum_raw, "sum_exact_unique": sum_exu, "sum_canonical_unique": sum_cnu,
        "sum_new_unique": sum_new,
        "pooled_dup_factor": round(sum_raw / sum_cnu, 4) if sum_cnu else None,
        "pooled_frac_dup": round(1 - sum_cnu / sum_raw, 4) if sum_raw else None,
    }
json.dump(rollup, open(f"{OUT}/rollup.json", "w"), indent=2)
print(json.dumps(rollup, indent=2))
