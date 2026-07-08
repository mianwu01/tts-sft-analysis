#!/usr/bin/env python3
"""Phase 8: EFT / self-evolution fine-tuning data MANIFESTS (references only — no training data is
materialized, no training is started). Built from tables/per_candidate_grades.jsonl.gz (oracle labels,
verified) + problem classes + the gpt-oss SVD accepts (strong-judge labels, Phase 6).

Manifest row schema:
  split, problem_id, candidate_id (shard::loop::idx), loop, source_model, correct_label,
  label_source (oracle|strong_judge), initial_bucket(loop0 correct), pos_neg,
  source_file, leakage_risk
"""
import csv
import gzip
import json
import os
from collections import defaultdict

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
os.chdir(REPO)
MODEL = "Qwen/Qwen3-4B"
SPLIT = "openthoughts114k-codeforces-nonsat1093"

cands = defaultdict(lambda: defaultdict(list))   # pid -> loop -> [(idx, passed, h, shard)]
for line in gzip.open(f"{OUT}/tables/per_candidate_grades.jsonl.gz", "rt"):
    r = json.loads(line)
    cands[r["pid"]][r["loop"]].append((r["idx"], r["passed"], r["h"], r["shard"]))

counts0 = {pid: sum(1 for i, p, h, s in loops.get(0, []) if p) for pid, loops in cands.items()}


def bucket(c):
    if c == 0:
        return "0"
    if c == 1:
        return "1"
    if c <= 4:
        return "2-4"
    if c <= 8:
        return "5-8"
    return "9-15"


def src(shard, loop):
    rn = f"cf_se16_{shard}" if not shard.startswith("redo") else f"cf_se16_{shard}"
    return f"outputs/openthoughts114k_codeforces_full_datagen/se16/{shard}/ck/{rn}_loop{loop}.json"


def row(pid, loop, idx, passed, shard, pos_neg, label_source="oracle", note=""):
    return {"split": SPLIT, "problem_id": pid, "candidate_id": f"{shard}::loop{loop}::{idx}",
            "loop": loop, "source_model": MODEL, "correct_label": passed,
            "label_source": label_source, "initial_bucket": bucket(counts0[pid]),
            "pos_neg": pos_neg, "source_file": src(shard, loop),
            "leakage_risk": "low(oracle-train-side-only)" if label_source == "oracle" else
                            "low(judge-fp~4%)", "note": note}


def write(name, rows):
    os.makedirs(f"{OUT}/manifests", exist_ok=True)
    cols = ["split", "problem_id", "candidate_id", "loop", "source_model", "correct_label",
            "label_source", "initial_bucket", "pos_neg", "source_file", "leakage_risk", "note"]
    with open(f"{OUT}/manifests/{name}", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")
    return len(rows)


stats = {}

# 1. final-correct-only: correct candidates of the LAST loop that has any correct (per problem)
rows1 = []
for pid, loops in cands.items():
    last = None
    for L in (2, 1, 0):
        if any(p for _, p, _, _ in loops.get(L, [])):
            last = L
            break
    if last is None:
        continue
    seen = set()
    for idx, p, h, sh in loops[last]:
        if p and h not in seen:
            seen.add(h)
            rows1.append(row(pid, last, idx, True, sh, "positive", note="final-loop unique correct"))
stats["final_correct_only"] = write("final_correct_only.csv", rows1)

# 2. evolution-chain: for problems first solved at loop>=1, all loops' unique correct up to first-solve loop
rows2 = []
for pid, loops in cands.items():
    first = None
    for L in (0, 1, 2):
        if any(p for _, p, _, _ in loops.get(L, [])):
            first = L
            break
    if first is None or first == 0:
        continue
    for L in range(0, first + 1):
        seen = set()
        for idx, p, h, sh in loops.get(L, []):
            if p and h not in seen:
                seen.add(h)
                rows2.append(row(pid, L, idx, True, sh, "positive",
                                 note=f"chain step {L}/{first} (first solved at loop{first})"))
stats["evolution_chain"] = write("evolution_chain.csv", rows2)

# 3. boundary-only: buckets 1..8 — all unique correct across loops
rows3 = []
for pid, loops in cands.items():
    if bucket(counts0[pid]) not in ("1", "2-4", "5-8"):
        continue
    seen = set()
    for L in (0, 1, 2):
        for idx, p, h, sh in loops.get(L, []):
            if p and h not in seen:
                seen.add(h)
                rows3.append(row(pid, L, idx, True, sh, "positive"))
stats["boundary_only"] = write("boundary_only.csv", rows3)

# 4. all-problem: every unique correct across loops (the maximal positive set)
rows4 = []
for pid, loops in cands.items():
    seen = set()
    for L in (0, 1, 2):
        for idx, p, h, sh in loops.get(L, []):
            if p and h not in seen:
                seen.add(h)
                rows4.append(row(pid, L, idx, True, sh, "positive"))
stats["all_problem"] = write("all_problem.csv", rows4)

# 5. positive/negative preference pairs: per problem per loop, 1 correct + 1 incorrect (same loop)
rows5 = []
for pid, loops in cands.items():
    for L in (0, 1, 2):
        pos = [(idx, h, sh) for idx, p, h, sh in loops.get(L, []) if p]
        neg = [(idx, sh) for idx, p, h, sh in loops.get(L, []) if p is False]
        if pos and neg:
            idx, h, sh = pos[0]
            rows5.append(row(pid, L, idx, True, sh, "positive", note="pref-pair"))
            nidx, nsh = neg[0]
            rows5.append(row(pid, L, nidx, False, nsh, "negative", note="pref-pair"))
stats["positive_negative_pairs"] = write("positive_negative_pairs.csv", rows5)

# 6. verifier-filtered (strong judge, TEST-FREE labels): gpt-oss SVD accepts on the 100-problem pilot
rows6 = []
D = "outputs/openthoughts114k_codeforces_full_datagen/self_verification_selection"
GR = json.load(open(f"{D}/_v1pp_analysis/grades.json"))
lab_se = {pid: [c["passed"] for c in sorted(cs, key=lambda c: c["idx"])]
          for pid, cs in GR["loop1_se_loop1_16"].items()}
for line in open(f"{D}/runs/se_loop1_16_svd_gptoss120b/selected.jsonl"):
    r = json.loads(line)
    pid = r["problem_id"]
    for cid in (r.get("accepted_candidate_ids") or []):
        idx = int(cid.split("::")[2])
        rows6.append({"split": "selfverif-pilot100-se-loop1-pool", "problem_id": pid,
                      "candidate_id": cid, "loop": 1, "source_model": MODEL,
                      "correct_label": True, "label_source": "strong_judge(gpt-oss-120b SVD)",
                      "initial_bucket": bucket(counts0.get(pid, 0)),
                      "pos_neg": "positive",
                      "source_file": "outputs/openthoughts114k_codeforces_full_datagen/svd_pilot_100/se_nofb/sh*/se_out.jsonl",
                      "leakage_risk": "low(test-free; oracle-precision 0.956)",
                      "note": f"oracle_truth={lab_se[pid][idx]}"})
stats["verifier_filtered"] = write("verifier_filtered.csv", rows6)

json.dump(stats, open(f"{OUT}/manifests/_stats.json", "w"), indent=2)
print(json.dumps(stats, indent=2))
