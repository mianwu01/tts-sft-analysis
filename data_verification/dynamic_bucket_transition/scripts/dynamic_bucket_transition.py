#!/usr/bin/env python3
"""Sewon follow-up: DYNAMIC bucket-transition analysis (loop0->loop1->loop2).

Uses EXISTING data only (no generation, no re-grading, no repo modification):
  input = unique_correct_audit/per_problem_hashes.json
          (oracle correctness = full-test grading cache outputs/grading_cache/se16.jsonl,
           matches the frontier CSV; canonical dedup = repo tokenizer canonicalization).

Keeps strictly separate, everywhere:
  - problem-level solved (raw_correct>0)  vs  candidate-level density (counts).
  - raw_correct_count  vs  exact_unique  vs  canonical_unique_correct_count.
  - oracle labels only (NO self-verifier / OSS-judge labels enter this analysis).
Denominators are stated in every table (row totals / group n).
"""
import os, json, csv
from collections import defaultdict, Counter
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
AUDIT = f"{ROOT}/unique_correct_audit/per_problem_hashes.json"
BASE = f"{ROOT}/dynamic_bucket_transition"
TAB, FIG = f"{BASE}/tables", f"{BASE}/figures"
os.makedirs(TAB, exist_ok=True); os.makedirs(FIG, exist_ok=True)

BUCKETS = ["0", "1", "2-4", "5-8", "9-15", "16"]
BIDX = {b: i for i, b in enumerate(BUCKETS)}
def bucket(c):
    if c == 0: return "0"
    if c == 1: return "1"
    if c <= 4: return "2-4"
    if c <= 8: return "5-8"
    if c <= 15: return "9-15"
    return "16"

d = json.load(open(AUDIT))
P = d["problems"]; classes = d.get("classes", {})
LOOPS = (0, 1, 2)

# ---- per-problem per-loop metrics ----
M = {}
for pid, rec in P.items():
    if not all(str(L) in rec for L in LOOPS):
        continue
    M[pid] = {}
    for L in LOOPS:
        r = rec[str(L)]
        raw = int(r["raw_correct"])
        ex = len(set(r["exact_hashes"]))
        cu = len(set(r["canon_hashes"]))
        M[pid][L] = {"raw": raw, "exact_u": ex, "canon_u": cu, "solved": raw > 0,
                     "ncand": int(r["ncand"]), "miss": int(r["miss"]),
                     "b_raw": bucket(raw), "b_canon": bucket(cu)}
PIDS = sorted(M)
N = len(PIDS)
print(f"[load] problems with full loop0/1/2 = {N}", flush=True)

# ===================== TASK 1: per-problem per-loop table =====================
with open(f"{TAB}/per_problem_loop_counts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["problem_id", "problem_class", "loop", "ncand", "cache_miss",
                "raw_correct_count", "exact_unique_correct_count", "canonical_unique_correct_count",
                "solved_any", "bucket_raw", "bucket_canonical_unique"])
    for pid in PIDS:
        for L in LOOPS:
            m = M[pid][L]
            w.writerow([pid, classes.get(pid, "unknown"), L, m["ncand"], m["miss"],
                        m["raw"], m["exact_u"], m["canon_u"], int(m["solved"]),
                        m["b_raw"], m["b_canon"]])
print("[task1] per_problem_loop_counts.csv", flush=True)

# ===================== TASK 2: transition matrices =====================
PAIRS = [(0, 1), (1, 2)]

def transition(prev, nxt, bkey, ckey):
    """bkey = 'b_raw'|'b_canon' (defines rows/cols); ckey = 'raw'|'canon_u' (delta/improve count field).
    Returns (counts[pb][nb], summary_rows)."""
    counts = {pb: Counter() for pb in BUCKETS}
    stat = {pb: {"n": 0, "next_raw": [], "next_canon": [], "d_raw": [], "d_canon": [],
                 "improve": 0, "same": 0, "drop": 0, "dropzero": 0} for pb in BUCKETS}
    for pid in PIDS:
        pb = M[pid][prev][bkey]; nb = M[pid][nxt][bkey]
        counts[pb][nb] += 1
        s = stat[pb]; s["n"] += 1
        s["next_raw"].append(M[pid][nxt]["raw"]); s["next_canon"].append(M[pid][nxt]["canon_u"])
        s["d_raw"].append(M[pid][nxt]["raw"] - M[pid][prev]["raw"])
        s["d_canon"].append(M[pid][nxt]["canon_u"] - M[pid][prev]["canon_u"])
        if BIDX[nb] > BIDX[pb]: s["improve"] += 1
        elif BIDX[nb] == BIDX[pb]: s["same"] += 1
        else: s["drop"] += 1
        if nb == "0": s["dropzero"] += 1
    rows = []
    for pb in BUCKETS:
        s = stat[pb]; n = s["n"]
        if n == 0:
            rows.append([pb, 0, "", "", "", "", "", "", "", ""]); continue
        rows.append([pb, n,
                     round(np.mean(s["next_raw"]), 3), round(np.mean(s["next_canon"]), 3),
                     round(np.mean(s["d_raw"]), 3), round(np.mean(s["d_canon"]), 3),
                     round(s["improve"] / n, 3), round(s["same"] / n, 3),
                     round(s["drop"] / n, 3), round(s["dropzero"] / n, 3)])
    return counts, rows

# write counts + probs CSVs (both loop-pairs in one file per bucket-type)
def write_matrix_csvs(bkey, tag):
    fc = open(f"{TAB}/{tag}_bucket_transition_counts.csv", "w", newline="")
    fp = open(f"{TAB}/{tag}_bucket_transition_probs.csv", "w", newline="")
    wc, wp = csv.writer(fc), csv.writer(fp)
    hdr = ["loop_pair", "prev_bucket"] + [f"next_{b}" for b in BUCKETS] + ["row_total"]
    wc.writerow(hdr); wp.writerow(hdr)
    mats = {}
    for prev, nxt in PAIRS:
        counts, _ = transition(prev, nxt, bkey, "raw" if bkey == "b_raw" else "canon_u")
        mats[(prev, nxt)] = counts
        lp = f"loop{prev}->loop{nxt}"
        for pb in BUCKETS:
            row = [counts[pb][b] for b in BUCKETS]; tot = sum(row)
            wc.writerow([lp, pb] + row + [tot])
            wp.writerow([lp, pb] + [round(x / tot, 4) if tot else "" for x in row] + [tot])
    fc.close(); fp.close()
    return mats

raw_mats = write_matrix_csvs("b_raw", "raw")
canon_mats = write_matrix_csvs("b_canon", "canonical")
print("[task2] raw/canonical transition counts+probs CSVs", flush=True)

# combined per-prev-bucket summary (both loop pairs, both bucket types)
with open(f"{TAB}/transition_summary_by_prev_bucket.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["loop_pair", "bucket_type", "prev_bucket", "n_problems(denominator)",
                "mean_next_raw", "mean_next_canonical_unique", "mean_delta_raw", "mean_delta_canonical_unique",
                "p_improve_bucket", "p_same_bucket", "p_drop_bucket", "p_drop_to_zero"])
    for bkey, btype in [("b_raw", "raw"), ("b_canon", "canonical_unique")]:
        for prev, nxt in PAIRS:
            _, rows = transition(prev, nxt, bkey, "raw" if bkey == "b_raw" else "canon_u")
            for r in rows:
                w.writerow([f"loop{prev}->loop{nxt}", btype] + r)
print("[task2] transition_summary_by_prev_bucket.csv", flush=True)

# figures: row-normalized transition heatmaps
def heatmap(counts, title, path):
    Mx = np.zeros((len(BUCKETS), len(BUCKETS)))
    tot = np.zeros(len(BUCKETS))
    for i, pb in enumerate(BUCKETS):
        row = np.array([counts[pb][b] for b in BUCKETS], float); tot[i] = row.sum()
        Mx[i] = row / row.sum() if row.sum() else 0
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(Mx, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(BUCKETS))); ax.set_xticklabels(BUCKETS)
    ax.set_yticks(range(len(BUCKETS)))
    ax.set_yticklabels([f"{b}  (n={int(tot[i])})" for i, b in enumerate(BUCKETS)])
    ax.set_xlabel("next-loop bucket"); ax.set_ylabel("prev-loop bucket (row denominator)")
    ax.set_title(title, fontsize=11)
    for i in range(len(BUCKETS)):
        for j in range(len(BUCKETS)):
            if tot[i]:
                ax.text(j, i, f"{Mx[i,j]:.2f}", ha="center", va="center",
                        color="white" if Mx[i, j] > 0.5 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="row-normalized P(next | prev)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)

for (prev, nxt), tag in [((0, 1), "loop0_to_loop1"), ((1, 2), "loop1_to_loop2")]:
    heatmap(raw_mats[(prev, nxt)], f"RAW-bucket transition {tag.replace('_',' ')}  (row-normalized)",
            f"{FIG}/raw_transition_matrix_{tag}.png")
    heatmap(canon_mats[(prev, nxt)], f"CANONICAL-unique-bucket transition {tag.replace('_',' ')}  (row-normalized)",
            f"{FIG}/canonical_transition_matrix_{tag}.png")
print("[task2] 4 transition heatmaps", flush=True)

# ===================== TASK 3: native-1/16 vs discovered 0->1 =====================
def group_outcomes(pids, this_loop, next_loop):
    n = len(pids)
    nr = [M[p][next_loop]["raw"] for p in pids]
    nc = [M[p][next_loop]["canon_u"] for p in pids]
    braw = Counter(M[p][next_loop]["b_raw"] for p in pids)
    bcan = Counter(M[p][next_loop]["b_canon"] for p in pids)
    retained = sum(1 for p in pids if M[p][next_loop]["raw"] > 0)
    dropzero = sum(1 for p in pids if M[p][next_loop]["raw"] == 0)
    reach = {b: sum(1 for p in pids if M[p][next_loop]["b_raw"] == b) for b in ["2-4", "5-8", "9-15", "16"]}
    return {"n": n, "mean_next_raw": round(np.mean(nr), 3) if n else 0,
            "mean_next_canon": round(np.mean(nc), 3) if n else 0,
            "p_next_solved_retention": round(retained / n, 3) if n else 0,
            "p_next_drop_to_zero": round(dropzero / n, 3) if n else 0,
            **{f"p_next_reaches_{b}": round(reach[b] / n, 3) if n else 0 for b in reach},
            "braw": braw, "bcan": bcan}

def write_native_vs_disc(field, fname):
    # field: 'raw' or 'canon_u'
    A = [p for p in PIDS if M[p][0][field] == 1]                                     # native boundary at loop0
    B = [p for p in PIDS if M[p][0][field] == 0 and M[p][1][field] == 1]             # discovered 0->1 by loop1
    oA = group_outcomes(A, 0, 1); oB = group_outcomes(B, 1, 2)
    with open(f"{TAB}/{fname}", "w", newline="") as f:
        w = csv.writer(f)
        cols = ["group", "definition", "measured_at_next_loop", "n_problems(denominator)",
                "mean_next_raw", "mean_next_canonical_unique", "p_next_solved_retention", "p_next_drop_to_zero",
                "p_next_reaches_2-4", "p_next_reaches_5-8", "p_next_reaches_9-15", "p_next_reaches_16"] + \
               [f"frac_next_raw_bucket_{b}" for b in BUCKETS] + [f"frac_next_canon_bucket_{b}" for b in BUCKETS]
        w.writerow(cols)
        for gname, gdef, mloop, o in [
            ("A_native_1", f"loop0 {field}==1", "loop1", oA),
            ("B_discovered_0to1", f"loop0 {field}==0 AND loop1 {field}==1", "loop2", oB)]:
            n = o["n"]
            row = [gname, gdef, mloop, n, o["mean_next_raw"], o["mean_next_canon"],
                   o["p_next_solved_retention"], o["p_next_drop_to_zero"],
                   o["p_next_reaches_2-4"], o["p_next_reaches_5-8"], o["p_next_reaches_9-15"], o["p_next_reaches_16"]]
            row += [round(o["braw"][b] / n, 4) if n else 0 for b in BUCKETS]
            row += [round(o["bcan"][b] / n, 4) if n else 0 for b in BUCKETS]
            w.writerow(row)
    return oA, oB

raw_A, raw_B = write_native_vs_disc("raw", "native1_vs_discovered01_raw.csv")
can_A, can_B = write_native_vs_disc("canon_u", "native1_vs_discovered01_canonical.csv")
print(f"[task3] native1 vs discovered01 (raw: nA={raw_A['n']} nB={raw_B['n']}; canon: nA={can_A['n']} nB={can_B['n']})", flush=True)

# slide-ready figure: next-loop raw-bucket distribution, native-1 vs discovered-0->1
def native_vs_disc_fig():
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    x = np.arange(len(BUCKETS)); wd = 0.38
    fa = [raw_A["braw"][b] / raw_A["n"] for b in BUCKETS]
    fb = [raw_B["braw"][b] / raw_B["n"] for b in BUCKETS]
    ax.bar(x - wd / 2, fa, wd, label=f"A: native 1/16 (loop0=1) → loop1   (n={raw_A['n']})", color="#4C78A8")
    ax.bar(x + wd / 2, fb, wd, label=f"B: discovered 0→1 (loop0=0,loop1=1) → loop2   (n={raw_B['n']})", color="#F58518")
    ax.set_xticks(x); ax.set_xticklabels(BUCKETS)
    ax.set_xlabel("next-loop raw correct-count bucket"); ax.set_ylabel("fraction of problems")
    ax.set_ylim(0, max(max(fa), max(fb)) * 1.55)   # headroom so legend clears the tallest bars
    ax.set_title("Once a 0/16 problem gets its first correct solution,\ndoes it densify like a native 1/16 problem?", fontsize=12)
    ax.legend(fontsize=9, loc="upper right")
    txt = (f"mean next-loop density (raw / canonical-unique):\n"
           f"  A native-1:      {raw_A['mean_next_raw']:.2f} / {raw_A['mean_next_canon']:.2f}\n"
           f"  B discovered-0→1: {raw_B['mean_next_raw']:.2f} / {raw_B['mean_next_canon']:.2f}\n"
           f"solved-retention:  A {raw_A['p_next_solved_retention']:.2f}   B {raw_B['p_next_solved_retention']:.2f}")
    ax.text(0.02, 0.97, txt, transform=ax.transAxes, va="top", ha="left", fontsize=8.5,
            family="monospace", bbox=dict(boxstyle="round", fc="#f5f5f5", ec="#ccc"))
    fig.tight_layout(); fig.savefig(f"{FIG}/native1_vs_discovered01_next_loop_density.png", dpi=140); plt.close(fig)
native_vs_disc_fig()
print("[task3] native1_vs_discovered01_next_loop_density.png", flush=True)

# ===================== TASK 4: hard-zero discovery timing =====================
hard0 = [p for p in PIDS if M[p][0]["raw"] == 0]
fs_loop1 = [p for p in hard0 if M[p][1]["raw"] > 0]
fs_loop2 = [p for p in hard0 if M[p][1]["raw"] == 0 and M[p][2]["raw"] > 0]
never = [p for p in hard0 if M[p][1]["raw"] == 0 and M[p][2]["raw"] == 0]
nh = len(hard0)
with open(f"{TAB}/hard_zero_discovery_timing.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["category", "definition", "count", "fraction_of_hard_zero(denominator=%d)" % nh])
    w.writerow(["hard_zero_total", "loop0 raw_correct==0", nh, 1.0])
    w.writerow(["first_solved_loop1", "loop0==0, loop1>0", len(fs_loop1), round(len(fs_loop1) / nh, 4)])
    w.writerow(["first_solved_loop2", "loop0==0, loop1==0, loop2>0", len(fs_loop2), round(len(fs_loop2) / nh, 4)])
    w.writerow(["never_solved_through_loop2", "loop0==0, loop1==0, loop2==0", len(never), round(len(never) / nh, 4)])
print(f"[task4] hard_zero total={nh} first@loop1={len(fs_loop1)} first@loop2={len(fs_loop2)} never={len(never)}", flush=True)

# loop1-first-solved followup: their loop1->loop2 dynamics
nf = len(fs_loop1)
retained = sum(1 for p in fs_loop1 if M[p][2]["raw"] > 0)
dropped0 = sum(1 for p in fs_loop1 if M[p][2]["raw"] == 0)
inc_raw = sum(1 for p in fs_loop1 if M[p][2]["raw"] > M[p][1]["raw"])
inc_canon = sum(1 for p in fs_loop1 if M[p][2]["canon_u"] > M[p][1]["canon_u"])
same_raw = sum(1 for p in fs_loop1 if M[p][2]["raw"] == M[p][1]["raw"])
tr_raw = Counter((M[p][1]["b_raw"], M[p][2]["b_raw"]) for p in fs_loop1)
tr_can = Counter((M[p][1]["b_canon"], M[p][2]["b_canon"]) for p in fs_loop1)
with open(f"{TAB}/hard_zero_loop1_first_solved_followup.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric", "count", "fraction(denominator=%d)" % nf])
    for lab, c in [("loop1_first_solved_total", nf), ("loop2_retained_solved", retained),
                   ("loop2_dropped_to_zero", dropped0), ("loop2_increased_raw_density", inc_raw),
                   ("loop2_increased_canonical_unique_density", inc_canon), ("loop2_same_raw_density", same_raw)]:
        w.writerow([lab, c, round(c / nf, 4) if nf else 0])
    w.writerow([])
    w.writerow(["loop1_bucket->loop2_bucket (RAW)", "count", "fraction"])
    for (a, b), c in sorted(tr_raw.items(), key=lambda kv: (-kv[1])):
        w.writerow([f"{a}->{b}", c, round(c / nf, 4)])
    w.writerow([])
    w.writerow(["loop1_bucket->loop2_bucket (CANONICAL-UNIQUE)", "count", "fraction"])
    for (a, b), c in sorted(tr_can.items(), key=lambda kv: (-kv[1])):
        w.writerow([f"{a}->{b}", c, round(c / nf, 4)])
print(f"[task4] loop1-first-solved followup: n={nf} retained={retained} dropped0={dropped0} inc_raw={inc_raw} inc_canon={inc_canon}", flush=True)

# ===================== rollup for the report =====================
def static_vs_dynamic():
    """Compare predictiveness of prev-loop bucket vs static loop0 bucket for loop1->loop2 next density.
    Metric: within-group variance reduction (R^2-like) of next-loop canonical density using
    the conditioning bucket. Higher => more predictive."""
    y = np.array([M[p][2]["canon_u"] for p in PIDS], float)  # target: loop2 canonical density
    sst = ((y - y.mean()) ** 2).sum()
    def r2(groupfn):
        groups = defaultdict(list)
        for p in PIDS: groups[groupfn(p)].append(M[p][2]["canon_u"])
        sse = sum(sum((np.array(v) - np.mean(v)) ** 2) for v in groups.values())
        return round(1 - sse / sst, 4)
    return {"static_loop0_bucket_R2": r2(lambda p: M[p][0]["b_canon"]),
            "dynamic_loop1_bucket_R2": r2(lambda p: M[p][1]["b_canon"])}

roll = {
    "n_problems": N,
    "raw_correct_total_by_loop": {L: sum(M[p][L]["raw"] for p in PIDS) for L in LOOPS},
    "canon_unique_total_by_loop": {L: sum(M[p][L]["canon_u"] for p in PIDS) for L in LOOPS},
    "solved_any_by_loop": {L: sum(1 for p in PIDS if M[p][L]["solved"]) for L in LOOPS},
    "native_vs_discovered_raw": {"A": {k: raw_A[k] for k in raw_A if k not in ("braw", "bcan")},
                                 "B": {k: raw_B[k] for k in raw_B if k not in ("braw", "bcan")}},
    "native_vs_discovered_canon": {"A": {k: can_A[k] for k in can_A if k not in ("braw", "bcan")},
                                   "B": {k: can_B[k] for k in can_B if k not in ("braw", "bcan")}},
    "hard_zero": {"total": nh, "first_solved_loop1": len(fs_loop1), "first_solved_loop2": len(fs_loop2),
                  "never_through_loop2": len(never),
                  "loop1_first_solved_followup": {"n": nf, "retained": retained, "dropped_to_zero": dropped0,
                                                  "increased_raw": inc_raw, "increased_canon": inc_canon}},
    "predictiveness_R2_next_loop2_canon": static_vs_dynamic(),
}
json.dump(roll, open(f"{BASE}/rollup.json", "w"), indent=2)
print("\n[rollup]\n" + json.dumps(roll, indent=2))
print("\n[DONE] all tables + figures written under", BASE)
