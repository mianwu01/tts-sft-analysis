#!/usr/bin/env python3
"""Phases 1+2: frontier-movement table + beyond-initial-frontier problem list, computed ONLY from
analysis_outputs/.../tables/recomputed_se16_per_problem.csv (our own recomputation, already verified
identical to the repo pipeline) + pop-8 independent grades (pass16 reference, verified provenance).

Definitions (task §3):
- initial direct-sampling pass@K: K=16 se16 loop0 (this-run) — OR the reference independent-16
  (pop-8 loop0∪loop0b) which defined the 'impossible' class. Both reported, clearly labeled.
- current/evolving-population pass@K: within each loop's 16-candidate population.
- compute-matched: SE loop1 cumulative budget = 32 gen/problem; the union of the two INDEPENDENT
  16-draws (reference-16 ∪ se16-loop0) is an independent-32 baseline on the same problems.
"""
import csv
import json
import math
import os
from collections import defaultdict

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
PC = f"{REPO}/outputs/openthoughts114k_codeforces_full_datagen/problem_classes"
os.chdir(REPO)


def passk(c, n, k):
    if c <= 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


rows = list(csv.DictReader(open(f"{OUT}/tables/recomputed_se16_per_problem.csv")))
p16 = json.load(open(f"{PC}/pass16_by_id.json"))
recompute_pop8 = {r["problem_id"]: int(r["pop8_l0_plus_l0b_correct_of_16"])
                  for r in csv.DictReader(open(f"{OUT}/tables/pop8_pass16_recompute.csv"))}


def cc(r, L):
    v = r.get(f"loop{L}_correct", "")
    return int(v) if v not in ("", None) else None


def miss(r, L):
    v = r.get(f"loop{L}_miss", "")
    return int(v) if v not in ("", None) else None


# ---------------- Phase 1: frontier movement ----------------
N = len(rows)
loops = [0, 1, 2]
overall = {}
for L in loops:
    vals = [cc(r, L) for r in rows]
    overall[L] = {
        "n": N,
        "solvable": sum(1 for v in vals if v > 0),
        "raw_correct": sum(vals),
        "pass@1": round(sum(v / 16 for v in vals) / N, 4),
        **{f"pass@{k}": round(sum(passk(v, 16, k) for v in vals) / N, 4) for k in (2, 4, 8, 16)},
        "cum_budget_per_problem": 16 * (L + 1),
    }

# loop3 partial: only problems with ALL 16 loop3 candidates graded (miss==0)
l3_rows = [r for r in rows if cc(r, 3) is not None and miss(r, 3) == 0]
l3 = {
    "n_fully_graded": len(l3_rows),
    "n_with_ck": sum(1 for r in rows if cc(r, 3) is not None),
    "solvable_l3": sum(1 for r in l3_rows if cc(r, 3) > 0),
    "solvable_l2_same_subset": sum(1 for r in l3_rows if cc(r, 2) > 0),
    "newly_solved_l3_vs_l2": sum(1 for r in l3_rows if cc(r, 2) == 0 and cc(r, 3) > 0),
    "lost_l2_to_l3": sum(1 for r in l3_rows if cc(r, 2) > 0 and cc(r, 3) == 0),
}

# initially-unsolved sets
ref244 = [r for r in rows if r["problem_class_ref"] == "impossible"]           # reference-16 == 0
run243 = [r for r in rows if cc(r, 0) == 0]                                     # this-run loop0 == 0
assert all(p16.get(r["problem_id"], -1) == 0 or r["problem_id"] in
           set(x.strip() for x in open(f"{PC}/impossible_ids.txt")) for r in ref244)


def solved_counts(subset):
    d = {
        "n": len(subset),
        "se16_loop0_solves": sum(1 for r in subset if cc(r, 0) > 0),
        "se_loop1_solves": sum(1 for r in subset if cc(r, 1) > 0),
        "se_loop2_solves": sum(1 for r in subset if cc(r, 2) > 0),
        "se_loop1_union_loop0": sum(1 for r in subset if cc(r, 0) > 0 or cc(r, 1) > 0),
        "se_loop2_union_prior": sum(1 for r in subset if any(cc(r, L) > 0 for L in (0, 1, 2))),
        "reference16_solves": sum(1 for r in subset if p16.get(r["problem_id"], 0) > 0),
        "independent32_union_solves": sum(
            1 for r in subset if cc(r, 0) > 0 or p16.get(r["problem_id"], 0) > 0),
    }
    sub3 = [r for r in subset if cc(r, 3) is not None and miss(r, 3) == 0]
    d["loop3_graded_subset_n"] = len(sub3)
    d["se_loop3_solves_graded_subset"] = sum(1 for r in sub3 if cc(r, 3) > 0)
    return d


imp_ref = solved_counts(ref244)
imp_run = solved_counts(run243)

frontier_csv = f"{OUT}/tables/frontier_movement.csv"
with open(frontier_csv, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["setting", "n_problems", "samples_per_problem_this_stage", "cumulative_budget",
                "solvable(any-of-pop)", "pass@1", "pass@16(pop)",
                "ref244_solved", "run243_solved", "compute_matched_vs",
                "source"])
    w.writerow(["reference independent-16 (pop-8 l0∪l0b)", 1617, 16, 16,
                1617 - sum(1 for v in p16.values() if v == 0), "", "",
                0, imp_run["reference16_solves"], "se16 loop0 (16)",
                "sharded_qwen3_4b/sh*/loop0*_out.jsonl + reachability_bon cache"])
    for L in loops:
        o = overall[L]
        w.writerow([f"SE loop{L}" + (" (= independent-16 draw)" if L == 0 else " (evolved pop)"),
                    o["n"], 16, o["cum_budget_per_problem"], o["solvable"], o["pass@1"], o["pass@16"],
                    [imp_ref["se16_loop0_solves"], imp_ref["se_loop1_solves"], imp_ref["se_loop2_solves"]][L],
                    [0, imp_run["se_loop1_solves"], imp_run["se_loop2_solves"]][L],
                    ["-", "independent-32 (union of the two 16-draws)", "MISSING independent-48"][L],
                    "se16/ck/*loop%d.json + se16 grading cache (recomputed)" % L])
    w.writerow(["independent-32 (reference-16 ∪ se16-loop0)", 1093, 32, 32,
                sum(1 for r in rows if cc(r, 0) > 0 or p16.get(r["problem_id"], 0) > 0), "", "",
                imp_ref["independent32_union_solves"], imp_run["independent32_union_solves"],
                "SE loop1 (32 cumulative)", "union of the two independent draws"])
    w.writerow(["SE loop3 (partial grading)", l3["n_fully_graded"], 16, 64,
                l3["solvable_l3"], "", "", imp_ref["se_loop3_solves_graded_subset"],
                imp_run["se_loop3_solves_graded_subset"], "MISSING independent-64",
                "se16 sh2,sh3,redo_* loop3 ck (2868/7776 candidates ungraded)"])

json.dump({"overall": overall, "loop3_partial": l3, "ref244": imp_ref, "run243": imp_run},
          open(f"{OUT}/tables/frontier_movement_detail.json", "w"), indent=2)

# ---------------- Phase 2: beyond-initial-frontier problem list ----------------
listing = f"{OUT}/tables/beyond_initial_frontier_problems.csv"
shard_of = {}
import glob
import re
for shdir in glob.glob("outputs/openthoughts114k_codeforces_full_datagen/se16/*sh*/"):
    if not os.path.exists(f"{shdir}/out.jsonl"):
        continue
    for line in open(f"{shdir}/out.jsonl"):
        shard_of[json.loads(line)["id"]] = shdir.rstrip("/")

with open(listing, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["problem_id", "frontier_definition", "reference16_correct", "se16_loop0_correct",
                "loop1_correct", "loop2_correct", "loop3_correct_or_blank", "first_solved_loop",
                "initial_bucket_ref16", "in_ref244", "in_run243", "source_ck_dir"])
    both = {r["problem_id"]: r for r in rows}
    ref_ids = set(r["problem_id"] for r in ref244)
    run_ids = set(r["problem_id"] for r in run243)
    for pid in sorted(ref_ids | run_ids):
        r = both[pid]
        solved_l = next((L for L in (0, 1, 2, 3) if (cc(r, L) or 0) > 0), "")
        if all((cc(r, L) or 0) == 0 for L in (1, 2, 3) if cc(r, L) is not None) and cc(r, 0) == 0 \
           and p16.get(pid, 0) == 0:
            solved_l = ""  # never solved by anything
        w.writerow([pid,
                    ("ref244+run243" if pid in ref_ids and pid in run_ids else
                     "ref244_only" if pid in ref_ids else "run243_only"),
                    p16.get(pid, ""), cc(r, 0), cc(r, 1), cc(r, 2),
                    cc(r, 3) if cc(r, 3) is not None and miss(r, 3) == 0 else "",
                    solved_l, "0/16", pid in ref_ids, pid in run_ids, shard_of.get(pid, "")])

# newly solved by loop2 but not loop1 (ref definition)
l2only = [r["problem_id"] for r in ref244 if cc(r, 1) == 0 and cc(r, 2) > 0]
l1solved = [r["problem_id"] for r in ref244 if cc(r, 1) > 0]
l2solved = [r["problem_id"] for r in ref244 if cc(r, 2) > 0]
union12 = [r["problem_id"] for r in ref244 if cc(r, 1) > 0 or cc(r, 2) > 0]
union012 = [r["problem_id"] for r in ref244 if cc(r, 0) > 0 or cc(r, 1) > 0 or cc(r, 2) > 0]

summ = {
    "ref244": {"n": 244, "loop1_pos": len(l1solved), "loop2_pos": len(l2solved),
               "loop2_pos_but_loop1_zero": len(l2only), "union_loop1_2": len(union12),
               "union_loop0_1_2": len(union012),
               "se16_loop0_pos": imp_ref["se16_loop0_solves"],
               "independent32_union": imp_ref["independent32_union_solves"]},
    "run243": {"n": len(run243), "loop1_pos": imp_run["se_loop1_solves"],
               "loop2_pos": imp_run["se_loop2_solves"],
               "reference16_pos(second independent draw)": imp_run["reference16_solves"],
               "independent32_union": imp_run["independent32_union_solves"]},
}
json.dump(summ, open(f"{OUT}/tables/beyond_frontier_summary.json", "w"), indent=2)
print(json.dumps(summ, indent=2))
print("\nOverall:", json.dumps(overall, indent=2))
print("\nloop3 partial:", json.dumps(l3, indent=2))
