#!/usr/bin/env python3
"""Phase 5: recompute SFT pass@1..pass@16 from raw per-problem eval files (16 samples/problem),
verify against each compare_summary.json, verify base consistency across arms, and audit
training-data sizes vs the data files. Outputs tables/sft_passk_analysis.csv + figures/sft_passk_plot.png."""
import csv
import glob
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
os.chdir(REPO)

ARMS = {  # eval-dir -> (label, target format, source, selection, train data file)
    "run1_A_lora_ck141": ("final-only loop1-all (ck141)", "final-only", "loop1(SE,pop8)", "all-unique", "data/sft/cstrip_sft_loop1_dedup.jsonl"),
    "run1_A_lora_ck282": ("final-only loop1-all (ck282)", "final-only", "loop1(SE,pop8)", "all-unique", "data/sft/cstrip_sft_loop1_dedup.jsonl"),
    "empty_think_A_lora_ck565": ("E1 code-only loop1-all", "empty-think code-only", "loop1(SE,pop16)", "all-unique", "data/sft/empty_think_fullpass_unique.jsonl"),
    "emptythink_loop0_A_lora_ck243": ("E3 code-only loop0-all", "empty-think code-only", "loop0(independent)", "all-unique", "data/sft/emptythink_loop0_fullpass_unique.jsonl"),
    "emptythink_loop0_B_best_lora_ck150": ("E3b code-only loop0-best", "empty-think code-only", "loop0(independent)", "best-per-problem", "data/sft/emptythink_loop0_fullpass_best.jsonl"),
    "emptythink_loop1_B_lora_ck164": ("E1b code-only loop1-best", "empty-think code-only", "loop1(SE,pop16)", "best-per-problem", "data/sft/empty_think_fullpass_best.jsonl"),
    "realthink_loop0_A_lora_ck116": ("E2 real-CoT loop0-all", "real CoT", "loop0(independent)", "all-unique", "data/sft/realthink_loop0_fullpass_unique.jsonl"),
    "realthink_loop0_B_lora_ck72": ("E4 real-CoT loop0-best", "real CoT", "loop0(independent)", "best-per-problem", "data/sft/realthink_loop0_fullpass_best.jsonl"),
}
KS = (1, 2, 4, 8, 16)


def passk(c, n, k):
    if c <= 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def eval_from(path):
    rows = [json.loads(l) for l in open(path)]
    n = len(rows)
    out = {"n_problems": n,
           "cap_hit_rate": round(sum(r.get("cap_hit_count", 0) for r in rows) / max(1, sum(r["n_samples"] for r in rows)), 4)}
    for k in KS:
        out[f"pass@{k}"] = round(sum(passk(r["correct_count"], r["n_samples"], k) for r in rows) / n, 4)
    out["solved_any"] = sum(1 for r in rows if r["correct_count"] > 0)
    return out


table = []
base_signatures = set()
base_eval = None
for d, (label, fmt, src, sel, data_file) in ARMS.items():
    root = f"outputs/sweep_lcbv6/{d}"
    if not os.path.isdir(root):
        table.append({"arm": label, "status": "MISSING eval dir"})
        continue
    sft = eval_from(f"{root}/sft_per_problem.jsonl")
    base = eval_from(f"{root}/base_per_problem.jsonl")
    base_signatures.add(json.dumps(base, sort_keys=True))
    base_eval = base
    cs = json.load(open(f"{root}/compare_summary.json"))
    rep = cs["subsets"]["all_131"]
    consistent = (abs(rep["sft"]["pass@1_mean"] - sft["pass@1"]) < 5e-4 and
                  abs(rep["base"]["pass@1_mean"] - base["pass@1"]) < 5e-4 and
                  abs(rep["sft"]["pass@k_any"] - sft["pass@16"]) < 5e-4)
    nd = sum(1 for _ in open(data_file)) if os.path.exists(data_file) else None
    row = {"arm": label, "format": fmt, "source": src, "selection": sel,
           "train_rows": nd, "eval_dir": d, "consistent_with_repo_summary": consistent,
           "cap_hit_rate": sft["cap_hit_rate"], **{f"pass@{k}": sft[f"pass@{k}"] for k in KS}}
    table.append(row)

# base row
brow = {"arm": "BASE Qwen3-4B (untrained)", "format": "-", "source": "-", "selection": "-",
        "train_rows": "-", "eval_dir": "(shared within every compare_summary)",
        "consistent_with_repo_summary": len(base_signatures) == 1,
        "cap_hit_rate": base_eval["cap_hit_rate"], **{f"pass@{k}": base_eval[f"pass@{k}"] for k in KS}}
table.insert(0, brow)

cols = ["arm", "format", "source", "selection", "train_rows", "pass@1", "pass@2", "pass@4",
        "pass@8", "pass@16", "cap_hit_rate", "consistent_with_repo_summary", "eval_dir"]
with open(f"{OUT}/tables/sft_passk_analysis.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(table)

print(f"base identical across arms: {len(base_signatures) == 1}")
for r in table:
    print(json.dumps(r))

# ---- plot ----
fig, ax = plt.subplots(figsize=(8.2, 4.4))
xs = range(len(KS))
styles = {
    "BASE Qwen3-4B (untrained)": dict(ls=":", color="black", lw=2.2),
    "E3b code-only loop0-best": dict(ls="-", marker="^", color="black"),
    "E1b code-only loop1-best": dict(ls="-", marker="^", mfc="white", color="0.45"),
    "E3 code-only loop0-all": dict(ls="--", marker="o", mfc="white", color="black"),
    "E1 code-only loop1-all": dict(ls="--", marker="o", mfc="white", color="0.45"),
    "E2 real-CoT loop0-all": dict(ls="-", color="0.7", lw=1.6),
    "final-only loop1-all (ck141)": dict(ls="-.", color="0.8", lw=1.4),
}
for r in table:
    st = styles.get(r["arm"])
    if not st or "pass@1" not in r:
        continue
    ax.plot(xs, [r[f"pass@{k}"] for k in KS], label=r["arm"], **st)
ax.set_xticks(list(xs))
ax.set_xticklabels([str(k) for k in KS])
ax.set_xlabel("k (of 16 samples)")
ax.set_ylabel("LCBv6 pass@k (all_131)")
ax.set_title("SFT arms vs untrained base — recomputed from raw per-problem evals")
ax.legend(frameon=False, fontsize=8.5, loc="lower right")
fig.tight_layout()
fig.savefig(f"{OUT}/figures/sft_passk_plot.png", dpi=200)
print("saved plot")
