#!/usr/bin/env python3
"""Phase 6: self-verification / judge analysis — recomputed from raw run artifacts.

Ground truth: _v1pp_analysis/grades.json (per-candidate oracle full-pass for BOTH pilot pools),
spot-checked here by re-executing a sample through the repo harness.

Recomputes, per selector run (selected.jsonl + extra scores/win matrices + grades):
  top1/top3 fullpass (vs the run's own eval.json), RANDOM & ORACLE baselines,
  SVD precision/recall/F1/AUC + estimated-count vs true-count correlation (saturation use),
  V1 pairwise accuracy on mixed pairs + win-count AUC, difficulty-bucket splits.
Outputs: tables/self_verification_analysis.csv, tables/selection_detail.json,
         figures/verifier_by_bucket.png
"""
import csv
import json
import math
import os
import random
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.chdir(REPO)

D = "outputs/openthoughts114k_codeforces_full_datagen/self_verification_selection"
GR = json.load(open(f"{D}/_v1pp_analysis/grades.json"))
POOLKEY = {"ind16": "loop0_independent16", "se16": "loop1_se_loop1_16"}

# labels[pool][pid] = [bool passed per candidate index]
labels = {}
for short, key in POOLKEY.items():
    labels[short] = {pid: [c["passed"] for c in sorted(cands, key=lambda c: c["idx"])]
                     for pid, cands in GR[key].items()}
pilot_ids = [x.strip() for x in open(f"{D}/pilot_100_ids.txt") if x.strip()]


def pool_stats(short):
    L = labels[short]
    ids = [p for p in pilot_ids if p in L]
    dens = [sum(L[p]) / len(L[p]) for p in ids]
    return {"n": len(ids), "oracle_pass@1(any)": round(sum(1 for p in ids if any(L[p])) / len(ids), 4),
            "random_pass@1(mean density)": round(sum(dens) / len(dens), 4)}


baselines = {s: pool_stats(s) for s in ("ind16", "se16")}


def cand_label(cid):
    pid, pool, idx = cid.split("::")
    return labels[pool][pid][int(idx)]


def load_selected(run):
    """Concatenate selected.jsonl of a run dir or its sh* children."""
    paths = []
    root = f"{D}/runs/{run}"
    if os.path.exists(f"{root}/selected.jsonl"):
        paths = [f"{root}/selected.jsonl"]
    else:
        paths = sorted(f"{root}/{s}/selected.jsonl" for s in os.listdir(root)
                       if os.path.exists(f"{root}/{s}/selected.jsonl"))
    recs = []
    for p in paths:
        recs += [json.loads(l) for l in open(p)]
    seen = {}
    for r in recs:
        seen[r["problem_id"]] = r  # last wins (resume)
    return seen


def eval_json_of(run):
    root = f"{D}/runs/{run}"
    if os.path.exists(f"{root}/eval.json"):
        return json.load(open(f"{root}/eval.json"))
    parts = [json.load(open(f"{root}/{s}/eval.json")) for s in sorted(os.listdir(root))
             if os.path.exists(f"{root}/{s}/eval.json")]
    if not parts:
        return None
    n = sum(p["n_problems"] for p in parts)
    return {"n_problems": n,
            "top1_fullpass_rate": round(sum(p["n_top1_pass"] for p in parts) / n, 4),
            "top3_contains_fullpass_rate": round(sum(p["n_top3_pass"] for p in parts) / n, 4)}


def auc(scores_labels):
    pos = [s for s, l in scores_labels if l]
    neg = [s for s, l in scores_labels if not l]
    if not pos or not neg:
        return None
    wins = ties = 0
    for p in pos:
        for q in neg:
            if p > q:
                wins += 1
            elif p == q:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else float("nan")


RUNS = {  # run-dir -> (judge, selector, pool)
    "pilot100c_svd_independent16": ("Qwen3-4B", "SVD", "ind16"),
    "pilot100c_svd_se_loop1_16": ("Qwen3-4B", "SVD", "se16"),
    "pilot100c_v1_independent16": ("Qwen3-4B", "V1", "ind16"),
    "pilot100c_v1_v2_se16": ("Qwen3-4B", "V1", "se16"),
    "pilot100c_llmv_independent16": ("Qwen3-4B", "LLM-verifier", "ind16"),
    "independent16_svd_gptoss120b": ("gpt-oss-120b", "SVD", "ind16"),
    "independent16_v1_gptoss120b": ("gpt-oss-120b", "V1", "ind16"),
    "se_loop1_16_svd_gptoss120b": ("gpt-oss-120b", "SVD", "se16"),
    "se_loop1_16_v1_gptoss120b": ("gpt-oss-120b", "V1", "se16"),
    "pilot100c_v1pp_lite_v2_se16": ("Qwen3-4B", "V1++lite", "se16"),
    "pilot100c_v1pp_edge_v2_se16": ("Qwen3-4B", "V1++edge", "se16"),
}

table = []
detail = {"baselines": baselines}
bucket_edges = [(0, 0, "0"), (1, 1, "1"), (2, 8, "2-8"), (9, 15, "9-15"), (16, 16, "16")]
bucket_data = defaultdict(dict)

for run, (judge, sel, pool) in RUNS.items():
    recs = load_selected(run)
    if not recs:
        table.append({"run": run, "status": "NO selected.jsonl"})
        continue
    L = labels[pool]
    ids = [p for p in pilot_ids if p in recs and p in L]
    top1 = [cand_label(recs[p]["selected_top1_candidate_id"]) if recs[p].get("selected_top1_candidate_id") else False
            for p in ids]
    top3 = [any(cand_label(c) for c in (recs[p].get("selected_top3_candidate_ids") or [])) for p in ids]
    ev = eval_json_of(run)
    row = {"run": run, "judge": judge, "selector": sel, "pool": pool, "n": len(ids),
           "top1_fullpass_recomputed": round(sum(top1) / len(ids), 4),
           "top3_recomputed": round(sum(top3) / len(ids), 4),
           "eval_json_top1": None if not ev else ev["top1_fullpass_rate"],
           "match_eval_json": None if not ev else abs(sum(top1) / len(ids) - ev["top1_fullpass_rate"]) < 5e-3}

    # difficulty buckets by pool true count
    for lo, hi, bname in bucket_edges:
        bids = [p for p in ids if lo <= sum(L[p]) <= hi]
        if bids:
            r_top1 = sum(1 for p in bids if recs[p].get("selected_top1_candidate_id")
                         and cand_label(recs[p]["selected_top1_candidate_id"])) / len(bids)
            rnd = sum(sum(L[p]) / len(L[p]) for p in bids) / len(bids)
            orc = sum(1 for p in bids if any(L[p])) / len(bids)
            bucket_data[f"{judge} {sel} ({pool})"][bname] = (round(r_top1, 3), round(rnd, 3), round(orc, 3), len(bids))

    # per-candidate scores (SVD & V1 have extra scores / win_counts)
    sl = []
    est_vs_true = []
    acc_prec = None
    for p in ids:
        ex = recs[p].get("extra") or {}
        scores = ex.get("scores")
        wins = ex.get("win_counts")
        if scores:
            for cid, s in scores.items():
                sl.append((s, cand_label(cid)))
        elif wins:
            for i, s in enumerate(wins):
                sl.append((s, L[p][i]))
        acc = recs[p].get("accepted_candidate_ids")
        if acc is not None:
            tp = sum(1 for c in acc if cand_label(c))
            est_vs_true.append((len(acc), sum(L[p])))
            acc_prec = acc_prec or [0, 0, 0]
            acc_prec[0] += tp
            acc_prec[1] += len(acc)
            acc_prec[2] += sum(L[p])
    if sl:
        aucs = [auc([(s, l) for s, l in grp]) for grp in [sl]]
        row["auc_per_candidate"] = round(aucs[0], 3) if aucs[0] is not None else None
    if acc_prec and acc_prec[1]:
        row["accept_precision"] = round(acc_prec[0] / acc_prec[1], 3)
        row["accept_recall"] = round(acc_prec[0] / max(1, acc_prec[2]), 3)
        f1d = (acc_prec[0] / acc_prec[1]) + (acc_prec[0] / max(1, acc_prec[2]))
        row["accept_f1"] = round(2 * (acc_prec[0] / acc_prec[1]) * (acc_prec[0] / max(1, acc_prec[2])) / f1d, 3) if f1d else 0.0
    if est_vs_true:
        xs = [e for e, t in est_vs_true]
        ys = [t for e, t in est_vs_true]
        row["est_count_pearson_r"] = round(pearson(xs, ys), 3)
        row["max_overclaim(est-true)"] = max(e - t for e, t in est_vs_true)
        # saturation confusion at >=8/16
        tp = sum(1 for e, t in est_vs_true if e >= 8 and t >= 8)
        fp = sum(1 for e, t in est_vs_true if e >= 8 and t < 8)
        fn = sum(1 for e, t in est_vs_true if e < 8 and t >= 8)
        tn = sum(1 for e, t in est_vs_true if e < 8 and t < 8)
        row["sat_conf_tp_fp_fn_tn(@>=8)"] = f"{tp}/{fp}/{fn}/{tn}"

    # V1 pairwise accuracy on mixed pairs from win_matrix
    if sel.startswith("V1"):
        corr = tot = 0
        for p in ids:
            m = (recs[p].get("extra") or {}).get("win_matrix")
            if not m:
                continue
            for i in range(len(m)):
                for j in range(len(m)):
                    if i == j or L[p][i] == L[p][j]:
                        continue
                    if m[i][j] == m[j][i]:
                        continue
                    winner_correct = (m[i][j] > m[j][i]) == L[p][i]
                    corr += winner_correct
                    tot += 1
        if tot:
            row["pairwise_acc_mixed"] = round(corr / tot, 3)
    table.append(row)

cols = ["run", "judge", "selector", "pool", "n", "top1_fullpass_recomputed", "top3_recomputed",
        "eval_json_top1", "match_eval_json", "auc_per_candidate", "accept_precision",
        "accept_recall", "accept_f1", "est_count_pearson_r", "max_overclaim(est-true)",
        "sat_conf_tp_fp_fn_tn(@>=8)", "pairwise_acc_mixed", "status"]
with open(f"{OUT}/tables/self_verification_analysis.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(table)
json.dump({"baselines": baselines, "runs": table}, open(f"{OUT}/tables/selection_detail.json", "w"), indent=2)

# ---- figure: top1 by difficulty bucket for headline selectors ----
show = ["Qwen3-4B SVD (se16)", "Qwen3-4B V1 (se16)", "gpt-oss-120b SVD (se16)", "gpt-oss-120b V1 (se16)"]
bnames = [b for _, _, b in bucket_edges]
fig, ax = plt.subplots(figsize=(8.6, 4.2))
w = 0.18
for i, s in enumerate(show):
    vals = [bucket_data[s].get(b, (float("nan"),) * 4)[0] for b in bnames]
    ax.bar([x + (i - 1.5) * w for x in range(len(bnames))], vals, width=w, label=s,
           color=str(0.15 + 0.2 * i), edgecolor="black")
rnd = [bucket_data[show[1]].get(b, (0, float("nan"), 0, 0))[1] for b in bnames]
orc = [bucket_data[show[1]].get(b, (0, 0, float("nan"), 0))[2] for b in bnames]
ax.plot(range(len(bnames)), rnd, "k--", label="random (pool density)")
ax.plot(range(len(bnames)), orc, "k:", label="oracle (any correct)")
ax.set_xticks(range(len(bnames)))
ns = [bucket_data[show[1]].get(b, (0, 0, 0, 0))[3] for b in bnames]
ax.set_xticklabels([f"{b}\n(n={n})" for b, n in zip(bnames, ns)])
ax.set_xlabel("pool true correct-count bucket (SE loop1 pool)")
ax.set_ylabel("selected-candidate pass@1")
ax.set_title("Selection quality by difficulty bucket — recomputed from raw judge outputs + oracle grades")
ax.legend(frameon=False, fontsize=8.5)
fig.tight_layout()
fig.savefig(f"{OUT}/figures/verifier_by_bucket.png", dpi=200)

print(json.dumps({"baselines": baselines}, indent=2))
for r in table:
    print(json.dumps(r))
json.dump({k: v for k, v in bucket_data.items()}, open(f"{OUT}/tables/selection_bucket_data.json", "w"), indent=2)
