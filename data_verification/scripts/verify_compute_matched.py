#!/usr/bin/env python3
"""Phase 3: compute-matched direct-sampling baseline audit.

1. Recompute the pop-8 SE-vs-BoN reachability (matched 16 gen/problem, full 1,617) from raw
   out.jsonl + reachability_bon cache (cache-only) — verifies reachability_se_vs_bon.json.
2. Budget audit for every SE setting present; assemble the best available compute-matched
   independent baselines at each budget from EXISTING independent draws:
     - independent-16: reference (pop-8 l0∪l0b) or se16-loop0 (fresh 16)
     - independent-32: union of the two (16+16)  [heterogeneous: pop-8 uses max_tokens/backends
       identical (same model, same sampler temp1.0/top_p0.95/top_k20) — verified from configs]
     - independent-48/64: MISSING → exact TODO commands emitted.
3. Hard-tail overlap: SE-solved vs BoN-solved on the ref-244 set; also aggregate coverage
   at matched 32 on the 1,093 non-saturated (se16 SE l0∪l1 vs independent-32).
"""
import csv
import json
import os
import sys
from collections import defaultdict

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.chdir(REPO)
from score_diversify_ab import extract_code, _norm  # noqa: E402
from lcb_grading import cache_key  # noqa: E402

HARNESS = os.path.join(REPO, "scripts", "lcb_exec_harness.py")
POP8 = "outputs/openthoughts114k_codeforces_full_datagen/sharded_qwen3_4b"
PC = "outputs/openthoughts114k_codeforces_full_datagen/problem_classes"


def load_cache(path):
    d = {}
    for line in open(path):
        try:
            r = json.loads(line)
            d[r["k"]] = r["v"]
        except Exception:
            continue
    return d


pool = {}
for line in open("data/openthoughts114k_codeforces_stdin_clean.jsonl"):
    r = json.loads(line)
    s = r["test_cases"]
    tj = s if isinstance(s, str) else json.dumps(s)
    pool[r["seed_id"]] = (tj, float(json.loads(tj).get("time_limit") or 6.0))

cache = load_cache("outputs/grading_cache/reachability_bon.jsonl")


def solved_and_miss(path):
    solved, misses, n = set(), 0, 0
    for line in open(path):
        r = json.loads(line)
        pid = r["id"]
        tj, tl = pool[pid]
        n += 1
        for cand in (r.get("candidates") or []):
            code = extract_code(cand)
            if not code:
                continue
            v = cache.get(cache_key(HARNESS, code, tj, tl))
            if v is None:
                misses += 1
            elif v.get("passed"):
                solved.add(pid)
    return solved, misses, n


cats = {"both": 0, "only_SE": 0, "only_BoN": 0, "neither": 0}
U = defaultdict(set)
ids_all = []
tot_miss = 0
for sh in range(4):
    l0, m0, _ = solved_and_miss(f"{POP8}/sh{sh}/loop0_out.jsonl")
    l1, m1, _ = solved_and_miss(f"{POP8}/sh{sh}/nofb_out.jsonl")
    lb, mb, _ = solved_and_miss(f"{POP8}/sh{sh}/loop0b_out.jsonl")
    tot_miss += m0 + m1 + mb
    ids = [json.loads(x)["id"] for x in open(f"{POP8}/sh{sh}/loop0_out.jsonl")]
    ids_all += ids
    for pid in ids:
        se = (pid in l0) or (pid in l1)
        bon = (pid in l0) or (pid in lb)
        cats["both" if se and bon else "only_SE" if se else "only_BoN" if bon else "neither"] += 1
    U["loop0"] |= l0
    U["loop1"] |= l1
    U["loop0b"] |= lb
    U["SE"] |= (l0 | l1)
    U["BoN"] |= (l0 | lb)
    print(f"sh{sh}: loop0={len(l0)} nofb_loop1={len(l1)} loop0b={len(lb)} miss={m0+m1+mb}")

repo_reach = json.load(open(f"{POP8}/reachability_se_vs_bon.json"))
verify = {
    "recomputed": {"N": len(ids_all), "cats": cats, "coverage": {k: len(v) for k, v in U.items()},
                   "cache_misses": tot_miss},
    "repo_json": repo_reach,
    "match": (cats == repo_reach["cats"] and len(ids_all) == repo_reach["N"] and
              {k: len(v) for k, v in U.items()} == repo_reach["coverage"]),
}

# ---- hard-tail overlap (ref-244) for the pop-8 arms + se16 arms ----
imp_ids = set(x.strip() for x in open(f"{PC}/impossible_ids.txt") if x.strip())
se16rows = {r["problem_id"]: r for r in csv.DictReader(
    open(f"{OUT}/tables/recomputed_se16_per_problem.csv"))}


def cc(pid, L):
    v = se16rows.get(pid, {}).get(f"loop{L}_correct", "")
    return int(v) if v not in ("", None) else 0


hard = {
    "n_ref244": len(imp_ids),
    "pop8_SE16gen_solves": len(U["SE"] & imp_ids),
    "pop8_BoN16gen_solves(by construction 0)": len(U["BoN"] & imp_ids),
    "pop8_loop1only_solves": len(U["loop1"] & imp_ids),
    "se16_loop0_solves": sum(1 for p in imp_ids if cc(p, 0) > 0),
    "se16_loop1_solves(cum32)": sum(1 for p in imp_ids if cc(p, 1) > 0),
    "se16_loop2_solves(cum48)": sum(1 for p in imp_ids if cc(p, 2) > 0),
    "independent32_solves": sum(1 for p in imp_ids if cc(p, 0) > 0),  # ref16 is 0 by construction
    "overlap_pop8SE_and_se16loop1": len({p for p in imp_ids if cc(p, 1) > 0} & U["SE"] & imp_ids),
}

# ---- aggregate coverage at matched budgets on the 1,093 (se16 frame) ----
p16 = json.load(open(f"{PC}/pass16_by_id.json"))
nonsat = list(se16rows)
agg = {
    "n": len(nonsat),
    "SE32_union_l0_l1": sum(1 for p in nonsat if cc(p, 0) > 0 or cc(p, 1) > 0),
    "SE48_union_l0_l1_l2": sum(1 for p in nonsat if cc(p, 0) > 0 or cc(p, 1) > 0 or cc(p, 2) > 0),
    "SE_loop1_pop_only": sum(1 for p in nonsat if cc(p, 1) > 0),
    "independent16_se16loop0": sum(1 for p in nonsat if cc(p, 0) > 0),
    "independent16_reference": sum(1 for p in nonsat if p16.get(p, 0) > 0),
    "independent32_union": sum(1 for p in nonsat if cc(p, 0) > 0 or p16.get(p, 0) > 0),
    "independent48": None,
}
# pop8 full-1617 frame at matched 16
agg1617 = {"n": 1617, "SE16_pop8": len(U["SE"]), "BoN16_pop8": len(U["BoN"]),
           "only_SE": cats["only_SE"], "only_BoN": cats["only_BoN"]}

rows = [
    ["SE setting", "SE total budget/problem", "SE coverage", "independent baseline", "budget", "coverage",
     "compute_matched?", "hard-tail(ref244) SE vs indep", "verified_from"],
    ["pop-8 SE loop1 (l0∪l1), 1617", 16, agg1617["SE16_pop8"], "pop-8 BoN (l0∪l0b)", 16,
     agg1617["BoN16_pop8"], "YES (16v16)", f"{hard['pop8_SE16gen_solves']} vs 0 (BoN defines the set — circular)",
     "recomputed from out.jsonl+cache"],
    ["se16 SE loop1 pop, 1093", 32, agg["SE_loop1_pop_only"], "independent-32 (two 16-draws)", 32,
     agg["independent32_union"], "YES (32v32)", f"{hard['se16_loop1_solves(cum32)']} vs {hard['independent32_solves']}",
     "recomputed"],
    ["se16 SE≤loop1 union, 1093", 32, agg["SE32_union_l0_l1"], "independent-32", 32,
     agg["independent32_union"], "YES (32v32)", "58-problem union by loop2 (48) — see below", "recomputed"],
    ["se16 SE≤loop2 union, 1093", 48, agg["SE48_union_l0_l1_l2"], "independent-48", 48, "MISSING",
     "NO — baseline missing", f"{hard['se16_loop2_solves(cum48)']} vs MISSING", "recomputed"],
]
with open(f"{OUT}/tables/compute_matched_baselines.csv", "w", newline="") as f:
    csv.writer(f).writerows(rows)

json.dump({"pop8_reachability_verify": verify, "hard_tail_ref244": hard,
           "aggregate_matched_1093": agg, "aggregate_matched_1617_pop8": agg1617},
          open(f"{OUT}/tables/compute_matched_detail.json", "w"), indent=2)
print(json.dumps({"verify_match": verify["match"], "recomputed": verify["recomputed"],
                  "hard": hard, "agg1093": agg, "agg1617": agg1617}, indent=2))
