#!/usr/bin/env python3
"""Focused audit of the 'discovered 0->1 behaves like native 1/16 boundary' claim.
Uses ONLY the existing dynamic_bucket_transition output (tables/per_problem_loop_counts.csv).
No new generation, no re-grading, no repo modification."""
import csv, json
from collections import defaultdict, Counter
import numpy as np

BASE = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/dynamic_bucket_transition"
BUCKETS = ["0", "1", "2-4", "5-8", "9-15", "16"]
rng = np.random.default_rng(0)

# load per-problem per-loop
M = defaultdict(dict)
for r in csv.DictReader(open(f"{BASE}/tables/per_problem_loop_counts.csv")):
    M[r["problem_id"]][int(r["loop"])] = {
        "raw": int(r["raw_correct_count"]),
        "canon": int(r["canonical_unique_correct_count"]),
        "b_raw": r["bucket_raw"], "b_canon": r["bucket_canonical_unique"]}
PIDS = [p for p in M if all(L in M[p] for L in (0, 1, 2))]
print(f"problems: {len(PIDS)}")

def bdist(pids, loop, key):
    c = Counter(M[p][loop][key] for p in pids)
    n = len(pids)
    return np.array([c[b] / n for b in BUCKETS]) if n else np.zeros(len(BUCKETS)), c

# ---------- Task 1: denominators ----------
hard0 = [p for p in PIDS if M[p][0]["raw"] == 0]
first_l1 = [p for p in hard0 if M[p][1]["raw"] >= 1]                 # n=37: first-solved at loop1 (ANY positive)
disc_raw = [p for p in hard0 if M[p][1]["raw"] == 1]                 # n=18: loop1 raw EXACTLY 1
first_l1_ge2 = [p for p in first_l1 if M[p][1]["raw"] >= 2]
nat_raw = [p for p in PIDS if M[p][0]["raw"] == 1]                   # native raw 1/16 (loop0)
nat_can = [p for p in PIDS if M[p][0]["canon"] == 1]
disc_can = [p for p in hard0 if M[p][1]["canon"] == 1]
denoms = {
    "hard_zero (loop0 raw==0)": len(hard0),
    "first_solved_loop1 (loop0==0 & loop1 raw>=1)  [n=37]": len(first_l1),
    "  of which loop1 raw==1  [= discovered_raw n=18]": len(disc_raw),
    "  of which loop1 raw>=2": len(first_l1_ge2),
    "native_raw_1 (loop0 raw==1)": len(nat_raw),
    "native_canon_1 (loop0 canon==1)": len(nat_can),
    "discovered_canon_0to1 (loop0 canon==0 & loop1 canon==1)": len(disc_can),
    "overlap disc_raw & disc_canon": len(set(disc_raw) & set(disc_can)),
}

# ---------- Task 2: aligned metrics ----------
def metrics(pids, base, nxt):
    n = len(pids)
    nr = np.array([M[p][nxt]["raw"] for p in pids])
    nc = np.array([M[p][nxt]["canon"] for p in pids])
    cr = np.array([M[p][base]["raw"] for p in pids])
    cc = np.array([M[p][base]["canon"] for p in pids])
    braw, _ = bdist(pids, nxt, "b_raw"); bcan, _ = bdist(pids, nxt, "b_canon")
    return {"n": n, "retention": round(float((nr > 0).mean()), 3),
            "p_drop_to_0": round(float((nr == 0).mean()), 3),
            "p_add_raw": round(float((nr > cr).mean()), 3),
            "p_add_canon": round(float((nc > cc).mean()), 3),
            "mean_next_raw": round(float(nr.mean()), 3),
            "mean_next_canon": round(float(nc.mean()), 3),
            "median_next_canon": float(np.median(nc)),
            "next_raw_bucket_dist": {b: round(float(x), 3) for b, x in zip(BUCKETS, braw)},
            "next_canon_bucket_dist": {b: round(float(x), 3) for b, x in zip(BUCKETS, bcan)}}

G = {
    "A_raw_native1 (loop0 raw==1 -> loop1)": metrics(nat_raw, 0, 1),
    "B_raw_discovered0to1 (loop0==0,loop1 raw==1 -> loop2)": metrics(disc_raw, 1, 2),
    "A_canon_native1 (loop0 canon==1 -> loop1)": metrics(nat_can, 0, 1),
    "B_canon_discovered0to1 (loop0 canon==0,loop1 canon==1 -> loop2)": metrics(disc_can, 1, 2),
}

# ---------- Task 3: similarity (TV distance + bootstrap CI + permutation) ----------
def tv(p, q): return float(0.5 * np.abs(p - q).sum())

def similarity(Apids, Bpids, Abase, Anext, Bbase, Bnext, key):
    pA, _ = bdist(Apids, Anext, key); pB, _ = bdist(Bpids, Bnext, key)
    obs_tv = tv(pA, pB)
    # bootstrap TV: resample within each group
    A_b = [M[p][Anext][key] for p in Apids]; B_b = [M[p][Bnext][key] for p in Bpids]
    def dist_from(sample):
        c = Counter(sample); n = len(sample)
        return np.array([c[b] / n for b in BUCKETS])
    tvs = []
    for _ in range(3000):
        sa = rng.choice(A_b, len(A_b), replace=True); sb = rng.choice(B_b, len(B_b), replace=True)
        tvs.append(tv(dist_from(sa), dist_from(sb)))
    tvs = np.array(tvs)
    # permutation test on mean canonical density difference (label shuffle)
    valkey = "canon"
    a_vals = np.array([M[p][Anext][valkey] for p in Apids])
    b_vals = np.array([M[p][Bnext][valkey] for p in Bpids])
    obs_diff = float(a_vals.mean() - b_vals.mean())
    pooled = np.concatenate([a_vals, b_vals]); na = len(a_vals)
    perm = []
    for _ in range(5000):
        rng.shuffle(pooled)
        perm.append(pooled[:na].mean() - pooled[na:].mean())
    perm = np.array(perm)
    pval = float((np.abs(perm) >= abs(obs_diff)).mean())
    # bootstrap CI on mean-canon difference
    diffs = []
    for _ in range(3000):
        sa = rng.choice(a_vals, len(a_vals), replace=True); sb = rng.choice(b_vals, len(b_vals), replace=True)
        diffs.append(sa.mean() - sb.mean())
    diffs = np.array(diffs)
    return {"obs_TV": round(obs_tv, 3),
            "TV_boot_mean": round(float(tvs.mean()), 3),
            "TV_95CI": [round(float(np.percentile(tvs, 2.5)), 3), round(float(np.percentile(tvs, 97.5)), 3)],
            "mean_canon_diff_A_minus_B": round(obs_diff, 3),
            "mean_canon_diff_95CI": [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)],
            "perm_pvalue_mean_canon_diff": round(pval, 3)}

sim = {
    "raw_buckets (A_raw vs B_raw)": similarity(nat_raw, disc_raw, 0, 1, 1, 2, "b_raw"),
    "canon_buckets (A_canon vs B_canon)": similarity(nat_can, disc_can, 0, 1, 1, 2, "b_canon"),
}

out = {"denominators": denoms, "groups": G, "similarity": sim}
json.dump(out, open(f"{BASE}/boundary_like_audit_rollup.json", "w"), indent=2)
print(json.dumps(out, indent=2))
