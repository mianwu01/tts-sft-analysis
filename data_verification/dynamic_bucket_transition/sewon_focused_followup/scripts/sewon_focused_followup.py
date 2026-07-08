#!/usr/bin/env python3
"""Sewon focused follow-up: (A) strict native-1 vs discovered-0->1 (canonical-unique MAIN, raw secondary),
(B) dynamic previous-loop->next-loop accounting of where canonical-unique gains come from, (C) static-vs-dynamic,
(D) figures. Uses ONLY existing per_problem_loop_counts.csv (oracle labels + canonical dedup). No generation,
no repo modification. Canonical-unique is the main diversity metric; raw kept separate; solved = raw>0 (problem-level)."""
import csv, json
from collections import defaultdict, Counter
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DBT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/dynamic_bucket_transition"
BASE = f"{DBT}/sewon_focused_followup"
TAB, FIG = f"{BASE}/tables", f"{BASE}/figures"
BUCKETS = ["0", "1", "2-4", "5-8", "9-15", "16"]
BIDX = {b: i for i, b in enumerate(BUCKETS)}
rng = np.random.default_rng(0)

def bucket(c):
    return "0" if c == 0 else "1" if c == 1 else "2-4" if c <= 4 else "5-8" if c <= 8 else "9-15" if c <= 15 else "16"

M = defaultdict(dict)
for r in csv.DictReader(open(f"{DBT}/tables/per_problem_loop_counts.csv")):
    M[r["problem_id"]][int(r["loop"])] = {"raw": int(r["raw_correct_count"]),
                                          "canon": int(r["canonical_unique_correct_count"])}
PIDS = [p for p in M if all(L in M[p] for L in (0, 1, 2))]
N = len(PIDS)
print(f"problems={N}")

def bdist(vals):
    c = Counter(bucket(v) for v in vals); n = len(vals)
    return {b: round(c[b] / n, 4) for b in BUCKETS} if n else {b: 0 for b in BUCKETS}

def boot_ci(vals, stat, iters=3000):
    vals = np.asarray(vals)
    if len(vals) == 0: return [None, None]
    s = [stat(rng.choice(vals, len(vals), replace=True)) for _ in range(iters)]
    return [round(float(np.percentile(s, 2.5)), 3), round(float(np.percentile(s, 97.5)), 3)]

# ============ PART A: strict native-1 vs discovered-0->1 ============
def groupA(field):  # field='canon'|'raw'
    A = [p for p in PIDS if M[p][0][field] == 1]                                   # native-1 (loop0)
    B = [p for p in PIDS if M[p][0][field] == 0 and M[p][1][field] == 1]           # strict discovered 0->1
    return A, B

def metricsA(pids, base, nxt):
    n = len(pids)
    pc = np.array([M[p][base]["canon"] for p in pids])
    nc = np.array([M[p][nxt]["canon"] for p in pids])
    nr = np.array([M[p][nxt]["raw"] for p in pids])
    dc = nc - pc
    dist = bdist([M[p][nxt]["canon"] for p in pids])
    add = (nc > pc).astype(float)
    return {
        "n": n,
        "prev_mean_canon": round(float(pc.mean()), 3),
        "next_mean_canon": round(float(nc.mean()), 3),
        "next_median_canon": float(np.median(nc)),
        "mean_delta_canon": round(float(dc.mean()), 3),
        "median_delta_canon": float(np.median(dc)),
        "pct_stay_solved": round(float((nr > 0).mean()), 3),
        "pct_drop_to_zero": round(float((nr == 0).mean()), 3),
        "pct_add_canon_unique": round(float(add.mean()), 3),
        "pct_stay_exactly_1": round(float((nc == 1).mean()), 3),
        "pct_move_2-4": round(dist["2-4"], 3), "pct_move_5-8": round(dist["5-8"], 3),
        "pct_move_9-15": round(dist["9-15"], 3), "pct_move_16": round(dist["16"], 3),
        "next_bucket_dist_canon": dist,
        "ci_next_mean_canon": boot_ci(nc, np.mean),
        "ci_pct_add_canon": boot_ci(add, np.mean),
    }

partA = {}
for field, label in [("canon", "canonical_MAIN"), ("raw", "raw_secondary")]:
    A, B = groupA(field)
    partA[label] = {"A_native1": metricsA(A, 0, 1), "B_discovered0to1": metricsA(B, 1, 2)}

# denominator distinctions (explicit)
denoms = {
    "first_solved_loop1 (loop0=0, loop1 raw>0)": len([p for p in PIDS if M[p][0]["raw"] == 0 and M[p][1]["raw"] > 0]),
    "strict_0to1_canon (loop0 canon=0, loop1 canon=1)": len([p for p in PIDS if M[p][0]["canon"] == 0 and M[p][1]["canon"] == 1]),
    "strict_0to1_raw (loop0 raw=0, loop1 raw=1)": len([p for p in PIDS if M[p][0]["raw"] == 0 and M[p][1]["raw"] == 1]),
    "native1_canon (loop0 canon=1)": len([p for p in PIDS if M[p][0]["canon"] == 1]),
    "native1_raw (loop0 raw=1)": len([p for p in PIDS if M[p][0]["raw"] == 1]),
}

# write Part A tables (canonical main + raw secondary)
def write_partA(label, fname):
    A, B = partA[label]["A_native1"], partA[label]["B_discovered0to1"]
    keys = [k for k in A if not isinstance(A[k], dict)]
    with open(f"{TAB}/{fname}", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["metric", "A_native1", "B_discovered_0to1"])
        for k in keys:
            w.writerow([k, A[k], B[k]])
        w.writerow([])
        w.writerow(["next_bucket_dist_canon", "A_native1", "B_discovered_0to1"])
        for b in BUCKETS:
            w.writerow([f"bucket_{b}", A["next_bucket_dist_canon"][b], B["next_bucket_dist_canon"][b]])
write_partA("canonical_MAIN", "partA_native1_vs_discovered01_canonical.csv")
write_partA("raw_secondary", "partA_native1_vs_discovered01_raw.csv")
print("[A] canon: nA=%d nB=%d | raw: nA=%d nB=%d" % (
    partA["canonical_MAIN"]["A_native1"]["n"], partA["canonical_MAIN"]["B_discovered0to1"]["n"],
    partA["raw_secondary"]["A_native1"]["n"], partA["raw_secondary"]["B_discovered0to1"]["n"]))

# ============ PART B: where do canonical-unique gains come from (dynamic prev-bucket) ============
def transitions(pairs, field):
    """pairs: list of (prev_loop, next_loop). Returns list of (prev_bucket, prev_val, next_val, delta)."""
    out = []
    for prev, nxt in pairs:
        for p in PIDS:
            pv, nv = M[p][prev][field], M[p][nxt][field]
            out.append((bucket(pv), pv, nv, nv - pv))
    return out

def gain_accounting(tr):
    by = defaultdict(list)
    for pb, pv, nv, d in tr: by[pb].append((pv, nv, d))
    total_pos = sum(max(0, d) for _, _, _, d in tr)  # gross positive canonical gain across all transitions
    rows = []
    for b in BUCKETS:
        items = by[b]; n = len(items)
        if n == 0:
            rows.append({"bucket": b, "n": 0}); continue
        pv = np.array([x[0] for x in items]); nv = np.array([x[1] for x in items]); d = np.array([x[2] for x in items])
        pos = float(sum(max(0, x) for x in d))
        # bucket-index movement (solved = raw handled separately; here bucket on the same field)
        up = same = down = 0
        for a, c in zip(pv, nv):
            ia, ic = BIDX[bucket(a)], BIDX[bucket(c)]
            up += ic > ia; same += ic == ia; down += ic < ia
        rows.append({
            "bucket": b, "n": n,
            "mean_prev": round(float(pv.mean()), 3), "mean_next": round(float(nv.mean()), 3),
            "mean_delta": round(float(d.mean()), 3), "total_delta_net": int(d.sum()),
            "gross_positive_gain": int(pos),
            "share_of_total_positive_gain": round(pos / total_pos, 4) if total_pos else 0.0,
            "pct_add": round(float((d > 0).mean()), 3),
            "pct_stay_solved": round(float((nv > 0).mean()), 3),
            "pct_drop_to_zero": round(float((nv == 0).mean()), 3),
            "pct_move_up_bucket": round(up / n, 3), "pct_stay_same_bucket": round(same / n, 3),
            "pct_move_down_bucket": round(down / n, 3),
        })
    return rows, total_pos

def write_partB(field, fname):
    specs = [("loop0->loop1", [(0, 1)]), ("loop1->loop2", [(1, 2)]), ("pooled", [(0, 1), (1, 2)])]
    cols = ["transition", "prev_bucket", "n", "mean_prev", "mean_next", "mean_delta", "total_delta_net",
            "gross_positive_gain", "share_of_total_positive_gain", "pct_add", "pct_stay_solved",
            "pct_drop_to_zero", "pct_move_up_bucket", "pct_stay_same_bucket", "pct_move_down_bucket"]
    allrows = {}
    with open(f"{TAB}/{fname}", "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for name, pairs in specs:
            rows, _ = gain_accounting(transitions(pairs, field)); allrows[name] = rows
            for r in rows:
                if r.get("n", 0) == 0:
                    w.writerow([name, r["bucket"], 0] + [""] * (len(cols) - 3)); continue
                w.writerow([name, r["bucket"], r["n"], r["mean_prev"], r["mean_next"], r["mean_delta"],
                            r["total_delta_net"], r["gross_positive_gain"], r["share_of_total_positive_gain"],
                            r["pct_add"], r["pct_stay_solved"], r["pct_drop_to_zero"],
                            r["pct_move_up_bucket"], r["pct_stay_same_bucket"], r["pct_move_down_bucket"]])
    return allrows

partB_canon = write_partB("canon", "partB_canonical_gain_by_prev_bucket.csv")
partB_raw = write_partB("raw", "partB_raw_gain_by_prev_bucket.csv")
print("[B] canonical + raw gain-by-prev-bucket tables written")

# ============ PART C: static loop0-bucket view vs dynamic prev-bucket view ============
static_rows = []
for b in BUCKETS:
    grp = [p for p in PIDS if bucket(M[p][0]["canon"]) == b]
    if not grp: continue
    l2 = np.array([M[p][2]["canon"] for p in grp]); l0 = np.array([M[p][0]["canon"] for p in grp])
    static_rows.append({"loop0_bucket": b, "n": len(grp),
                        "loop2_mean_canon": round(float(l2.mean()), 3),
                        "loop0to2_mean_delta_canon": round(float((l2 - l0).mean()), 3)})
# dynamic pooled (from partB_canon['pooled'])
dyn = {r["bucket"]: r for r in partB_canon["pooled"]}
with open(f"{TAB}/partC_static_vs_dynamic_canonical.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["bucket", "STATIC_n_loop0", "STATIC_loop2_mean_canon", "STATIC_loop0to2_mean_delta_canon",
                "DYNAMIC_n_transitions(pooled)", "DYNAMIC_mean_delta_canon", "DYNAMIC_share_of_positive_gain"])
    sr = {r["loop0_bucket"]: r for r in static_rows}
    for b in BUCKETS:
        s = sr.get(b); dd = dyn.get(b, {})
        w.writerow([b,
                    s["n"] if s else 0, s["loop2_mean_canon"] if s else "", s["loop0to2_mean_delta_canon"] if s else "",
                    dd.get("n", 0), dd.get("mean_delta", ""), dd.get("share_of_total_positive_gain", "")])
print("[C] static-vs-dynamic table written")

# ============ rollup ============
roll = {"n_problems": N, "denominators": denoms, "partA": partA,
        "partB_canonical_pooled": {r["bucket"]: r for r in partB_canon["pooled"]},
        "partB_canonical_loop0to1": {r["bucket"]: r for r in partB_canon["loop0->loop1"]},
        "partB_canonical_loop1to2": {r["bucket"]: r for r in partB_canon["loop1->loop2"]},
        "partC_static": static_rows}
json.dump(roll, open(f"{BASE}/rollup.json", "w"), indent=2)

# ============ PART D: figures ============
CA, CB = partA["canonical_MAIN"]["A_native1"], partA["canonical_MAIN"]["B_discovered0to1"]

# D1: native-1 vs discovered compact comparison (canonical)
fig, ax = plt.subplots(1, 2, figsize=(10, 4.4))
m = ax[0]
means = [CA["next_mean_canon"], CB["next_mean_canon"]]
errs = [[CA["next_mean_canon"] - CA["ci_next_mean_canon"][0], CB["next_mean_canon"] - CB["ci_next_mean_canon"][0]],
        [CA["ci_next_mean_canon"][1] - CA["next_mean_canon"], CB["ci_next_mean_canon"][1] - CB["next_mean_canon"]]]
m.bar([0, 1], means, yerr=errs, capsize=6, color=["#4C78A8", "#F58518"])
m.set_xticks([0, 1]); m.set_xticklabels([f"native-1\n(n={CA['n']})", f"discovered 0→1\n(n={CB['n']})"])
m.set_ylabel("next-loop mean canonical-unique"); m.set_title("Next-loop unique-correct density\n(95% bootstrap CI)")
for i, v in enumerate(means): m.text(i, v + 0.05, f"{v:.2f}", ha="center", fontsize=10)
r = ax[1]; x = np.arange(2); wd = 0.35
r.bar(x - wd / 2, [CA["pct_add_canon_unique"], CA["pct_drop_to_zero"]], wd, color="#4C78A8", label=f"native-1 (n={CA['n']})")
r.bar(x + wd / 2, [CB["pct_add_canon_unique"], CB["pct_drop_to_zero"]], wd, color="#F58518", label=f"discovered 0→1 (n={CB['n']})")
r.set_xticks(x); r.set_xticklabels(["% add unique", "% drop to zero"]); r.set_ylim(0, 1)
r.set_title("Densify vs collapse"); r.legend(fontsize=8)
for i, (a, b) in enumerate(zip([CA["pct_add_canon_unique"], CA["pct_drop_to_zero"]],
                               [CB["pct_add_canon_unique"], CB["pct_drop_to_zero"]])):
    r.text(i - wd / 2, a + 0.02, f"{a:.2f}", ha="center", fontsize=8)
    r.text(i + wd / 2, b + 0.02, f"{b:.2f}", ha="center", fontsize=8)
fig.suptitle("Strict native-1/16 vs discovered-0→1 (canonical-unique)", fontsize=12)
fig.tight_layout(); fig.savefig(f"{FIG}/native1_vs_discovered01_canonical_comparison.png", dpi=140); plt.close(fig)

# D2: mean delta canonical by previous bucket (loop0->1 vs loop1->2)
d01 = {r["bucket"]: r for r in partB_canon["loop0->loop1"]}
d12 = {r["bucket"]: r for r in partB_canon["loop1->loop2"]}
fig, ax = plt.subplots(figsize=(8.6, 4.8)); x = np.arange(len(BUCKETS)); wd = 0.38
v01 = [d01[b].get("mean_delta", 0) if d01[b].get("n") else 0 for b in BUCKETS]
v12 = [d12[b].get("mean_delta", 0) if d12[b].get("n") else 0 for b in BUCKETS]
ax.bar(x - wd / 2, v01, wd, label="loop0→loop1", color="#4C78A8")
ax.bar(x + wd / 2, v12, wd, label="loop1→loop2", color="#F58518")
ax.axhline(0, color="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(BUCKETS)
ax.set_xlabel("previous-loop canonical-unique bucket"); ax.set_ylabel("mean Δ canonical-unique")
ax.set_title("Per-problem canonical-unique gain by previous-loop bucket")
ax.legend()
fig.tight_layout(); fig.savefig(f"{FIG}/dynamic_bucket_gain_by_previous_bucket.png", dpi=140); plt.close(fig)

# D3: share of total positive canonical gain by previous bucket
fig, ax = plt.subplots(figsize=(8.6, 4.8))
s01 = [d01[b].get("share_of_total_positive_gain", 0) if d01[b].get("n") else 0 for b in BUCKETS]
s12 = [d12[b].get("share_of_total_positive_gain", 0) if d12[b].get("n") else 0 for b in BUCKETS]
ax.bar(x - wd / 2, s01, wd, label="loop0→loop1", color="#4C78A8")
ax.bar(x + wd / 2, s12, wd, label="loop1→loop2", color="#F58518")
ax.set_xticks(x); ax.set_xticklabels(BUCKETS)
ax.set_xlabel("previous-loop canonical-unique bucket"); ax.set_ylabel("share of total positive canonical gain")
ax.set_title("Where do the positive canonical-unique gains come from?")
ax.legend()
for i, (a, b) in enumerate(zip(s01, s12)):
    if a: ax.text(i - wd / 2, a + 0.005, f"{a:.2f}", ha="center", fontsize=7)
    if b: ax.text(i + wd / 2, b + 0.005, f"{b:.2f}", ha="center", fontsize=7)
fig.tight_layout(); fig.savefig(f"{FIG}/dynamic_bucket_gain_contribution.png", dpi=140); plt.close(fig)

# D4: pooled canonical previous->next transition matrix (row-normalized)
Mx = np.zeros((6, 6)); tot = np.zeros(6)
for pb, pv, nv, d in transitions([(0, 1), (1, 2)], "canon"):
    Mx[BIDX[pb], BIDX[bucket(nv)]] += 1
for i in range(6): tot[i] = Mx[i].sum(); Mx[i] = Mx[i] / tot[i] if tot[i] else 0
fig, ax = plt.subplots(figsize=(6.4, 5.4))
im = ax.imshow(Mx, cmap="Blues", vmin=0, vmax=1)
ax.set_xticks(range(6)); ax.set_xticklabels(BUCKETS); ax.set_yticks(range(6))
ax.set_yticklabels([f"{b} (n={int(tot[i])})" for i, b in enumerate(BUCKETS)])
ax.set_xlabel("next-loop canonical-unique bucket"); ax.set_ylabel("previous-loop bucket (row denom)")
ax.set_title("Pooled previous→next canonical-unique transition\n(loop0→1 + loop1→2, row-normalized)", fontsize=11)
for i in range(6):
    for j in range(6):
        if tot[i]: ax.text(j, i, f"{Mx[i,j]:.2f}", ha="center", va="center",
                           color="white" if Mx[i, j] > 0.5 else "black", fontsize=8)
fig.colorbar(im, ax=ax, label="P(next | prev)")
fig.tight_layout(); fig.savefig(f"{FIG}/previous_to_next_bucket_transition_canonical.png", dpi=130); plt.close(fig)
print("[D] 4 figures written")

print("\n[rollup A canonical]", json.dumps(partA["canonical_MAIN"], indent=1)[:1200])
print("\n[rollup B canonical pooled]")
for r in partB_canon["pooled"]:
    if r.get("n"): print("  ", r["bucket"], "n=%d" % r["n"], "meanΔ=%.2f" % r["mean_delta"],
                          "totalΔ=%d" % r["total_delta_net"], "share+=%.2f" % r["share_of_total_positive_gain"],
                          "up/same/down=%.2f/%.2f/%.2f" % (r["pct_move_up_bucket"], r["pct_stay_same_bucket"], r["pct_move_down_bucket"]))
print("\n[C static]"); [print("  ", r) for r in static_rows]
print("\n[DONE]")
