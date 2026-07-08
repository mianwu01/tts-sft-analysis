#!/usr/bin/env python3
"""Phase 4: bucket analysis / curriculum signal, from the recomputed se16 per-problem table.
Buckets by THIS-RUN loop0 correct count (K=16 verified). Also recomputes the cf_cc loop0
saturation aggregation from per-shard grade_loop0.json.
Outputs: tables/bucket_analysis.csv, bucket_analysis.md, figures/bucket_heatmap.png,
         tables/cc_saturation_recompute.json
"""
import csv
import json
import os
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
os.chdir(REPO)

BUCKETS = [("0", lambda c: c == 0), ("1", lambda c: c == 1), ("2-4", lambda c: 2 <= c <= 4),
           ("5-8", lambda c: 5 <= c <= 8), ("9-15", lambda c: 9 <= c <= 15), ("16", lambda c: c == 16)]

rows = list(csv.DictReader(open(f"{OUT}/tables/recomputed_se16_per_problem.csv")))


def ival(r, col):
    v = r.get(col, "")
    return int(v) if v not in ("", None) else None


out_rows = []
heat = defaultdict(dict)
for bname, pred in BUCKETS:
    grp = [r for r in rows if pred(ival(r, "loop0_correct"))]
    if not grp:
        continue
    for L in (0, 1, 2, 3):
        sub = [r for r in grp if ival(r, f"loop{L}_correct") is not None and
               (L < 3 or ival(r, f"loop{L}_miss") == 0)]
        if not sub:
            continue
        cs = [ival(r, f"loop{L}_correct") for r in sub]
        us = [ival(r, f"loop{L}_unique") for r in sub]
        prev = [ival(r, f"loop{L-1}_correct") for r in sub] if L > 0 else None
        d = {
            "bucket_loop0": bname, "loop": L, "n_problems": len(sub),
            "avg_correct": round(sum(cs) / len(sub), 2),
            "avg_density": round(sum(cs) / len(sub) / 16, 4),
            "avg_unique": round(sum(us) / len(sub), 2),
            "avg_unique_density": round(sum(us) / len(sub) / 16, 4),
            "improved_vs_prev": "" if L == 0 else sum(1 for c, p in zip(cs, prev) if c > p),
            "plateaued_vs_prev": "" if L == 0 else sum(1 for c, p in zip(cs, prev) if c == p),
            "worsened_vs_prev": "" if L == 0 else sum(1 for c, p in zip(cs, prev) if c < p),
            "newly_solved_vs_prev": "" if L == 0 else sum(1 for c, p in zip(cs, prev) if p == 0 and c > 0),
            "remaining_unsolved": sum(1 for c in cs if c == 0),
            "pct_improved": "" if L == 0 else round(100 * sum(1 for c, p in zip(cs, prev) if c > p) / len(sub), 1),
            "pct_worsened": "" if L == 0 else round(100 * sum(1 for c, p in zip(cs, prev) if c < p) / len(sub), 1),
        }
        out_rows.append(d)
        heat[bname][L] = sum(cs) / len(sub)

with open(f"{OUT}/tables/bucket_analysis.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
    w.writeheader()
    w.writerows(out_rows)

# ---- heatmap: mean correct count per bucket per loop (loops 0-2 complete) ----
bnames = [b for b, _ in BUCKETS if b in heat]
fig, ax = plt.subplots(figsize=(7.5, 4.2))
data = [[heat[b].get(L, float("nan")) for L in (0, 1, 2)] for b in bnames]
im = ax.imshow(data, aspect="auto", cmap="Greys", vmin=0, vmax=16)
for i, b in enumerate(bnames):
    for j, L in enumerate((0, 1, 2)):
        v = heat[b].get(L)
        if v is not None:
            ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                    color=("white" if v > 9 else "black"), fontsize=11)
ax.set_xticks([0, 1, 2])
ax.set_xticklabels(["loop0\n(16 gen)", "loop1\n(cum 32)", "loop2\n(cum 48)"])
ax.set_yticks(range(len(bnames)))
ax.set_yticklabels([f"{b}/16" for b in bnames])
ax.set_ylabel("initial (loop0) correct-count bucket")
ax.set_title("se16: mean correct count (of 16) per initial-difficulty bucket per loop\n"
             "n=1,093 non-saturated codeforces, oracle full-test grading (verified)")
fig.colorbar(im, label="mean correct of 16")
fig.tight_layout()
fig.savefig(f"{OUT}/figures/bucket_heatmap.png", dpi=200)
plt.close(fig)

# ---- cf_cc loop0 saturation recompute (aggregation level) ----
import glob
counts = {}
for fpath in glob.glob("outputs/openthoughts_cf_cc_datagen/loop0_pop8/sh*/grade_loop0.json"):
    for pid, v in json.load(open(fpath)).items():
        counts[pid] = v["correct"]
dist = Counter(counts.values())
cc_rec = {"n": len(counts), "saturated_8": sum(1 for c in counts.values() if c == 8),
          "impossible": sum(1 for c in counts.values() if c == 0),
          "dist": {str(k): dist.get(k, 0) for k in range(9)}}
cc_rec["informative"] = cc_rec["n"] - cc_rec["saturated_8"] - cc_rec["impossible"]
cc_rec["non_saturated"] = cc_rec["informative"] + cc_rec["impossible"]
repo_rep = json.load(open("outputs/openthoughts_cf_cc_datagen/saturation_report.json"))
cc_rec["matches_repo_report"] = all(repo_rep[k] == cc_rec[k] for k in
                                    ("n", "saturated_8", "informative", "impossible", "non_saturated"))
json.dump(cc_rec, open(f"{OUT}/tables/cc_saturation_recompute.json", "w"), indent=2)

print(json.dumps({"buckets": out_rows, "cc": cc_rec}, indent=2)[:3000])
