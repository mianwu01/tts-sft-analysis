#!/usr/bin/env python3
"""Phase 1 verification: recompute per-problem per-loop correct counts of the se16 pop-16 run
DIRECTLY from raw loop checkpoints + the append-only grading cache (cache-only; no code execution).

Independence from the repo's frontier pipeline: we re-implement the counting (id matching, code
extraction via the repo's own extractor, cache-key computation) and compare against the repo's
outputs/.../se16/frontier/per_problem_correct_counts.csv. Any cache miss is REPORTED, never executed.

Also verifies provenance of problem_classes/pass16_by_id.json against the pop-8 experiment's
loop0 ∪ loop0b independent grades (16 samples/problem) using the reachability_bon cache.

Outputs (under analysis_outputs/data_verification/):
  tables/recomputed_se16_per_problem.csv   problem_id, loopL_correct/unique/ncand/miss (L=0..3), class
  tables/recompute_vs_repo_diff.csv        rows where our counts differ from the repo CSV
  tables/pop8_pass16_recompute.csv         pop-8 loop0+loop0b per-problem counts vs pass16_by_id.json
  recompute_se16_summary.json              roll-up incl. cache-miss stats + provenance verdicts
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
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
PC = "outputs/openthoughts114k_codeforces_full_datagen/problem_classes"
POP8 = "outputs/openthoughts114k_codeforces_full_datagen/sharded_qwen3_4b"
SHARDS = ["sh0", "sh1", "sh2", "sh3", "sh4", "sh7", "sh8",
          "redo_sh0", "redo_sh1", "redo_sh2", "redo_sh3", "redo_sh4", "redo_sh5"]


def load_cache(path):
    d = {}
    for line in open(path):
        try:
            r = json.loads(line)
            d[r["k"]] = r["v"]
        except Exception:
            continue
    return d


def load_pool():
    pool = {}
    for line in open("data/openthoughts114k_codeforces_stdin_clean.jsonl"):
        r = json.loads(line)
        s = r["test_cases"]
        tj = s if isinstance(s, str) else json.dumps(s)
        t = json.loads(tj)
        pool[r["seed_id"]] = (tj, float(t.get("time_limit") or 6.0))
    return pool


def grade_candidates(cands, tj, tl, cache):
    """Return (n_cand, correct_raw, unique_correct, n_miss, n_nocode) — cache-only."""
    n_cand = len(cands)
    hashes, miss, nocode = [], 0, 0
    for cand in cands:
        code = extract_code(cand)
        if not code:
            nocode += 1
            continue
        v = cache.get(cache_key(HARNESS, code, tj, tl))
        if v is None:
            miss += 1
            continue
        if v.get("passed"):
            hashes.append(_norm(code))
    return n_cand, len(hashes), len(set(hashes)), miss, nocode


def main():
    pool = load_pool()
    cache = load_cache("outputs/grading_cache/se16.jsonl")
    print(f"[cache] se16.jsonl entries: {len(cache)}")

    # ---- recompute se16 loops 0..3 ----
    cc = defaultdict(dict)   # pid -> loop -> dict(counts)
    id_overlap = defaultdict(list)
    for sh in SHARDS:
        root = f"{SE16}/{sh}"
        ids = [json.loads(l)["id"] for l in open(f"{root}/out.jsonl")]
        for pid in ids:
            id_overlap[pid].append(sh)
        import glob
        import re
        rn = re.sub(r"_loop0\.json$", "", os.path.basename(glob.glob(f"{root}/ck/*_loop0.json")[0]))
        for loop in range(4):
            ck = f"{root}/ck/{rn}_loop{loop}.json"
            if not os.path.exists(ck):
                continue
            probs = json.load(open(ck)).get("problems", [])
            for i, prob in enumerate(probs):
                if i >= len(ids):
                    break
                pid = ids[i]
                tj, tl = pool[pid]
                n, raw, uniq, miss, nocode = grade_candidates(prob.get("candidates") or [], tj, tl, cache)
                cc[pid][loop] = {"ncand": n, "correct": raw, "unique": uniq, "miss": miss, "nocode": nocode}
        print(f"[shard] {sh}: {len(ids)} problems", flush=True)

    dup = {p: s for p, s in id_overlap.items() if len(s) > 1}
    n_probs = len(cc)

    os.makedirs(f"{OUT}/tables", exist_ok=True)
    with open(f"{OUT}/tables/recomputed_se16_per_problem.csv", "w", newline="") as f:
        w = csv.writer(f)
        hdr = ["problem_id"]
        for L in range(4):
            hdr += [f"loop{L}_correct", f"loop{L}_unique", f"loop{L}_ncand", f"loop{L}_miss"]
        w.writerow(hdr + ["problem_class_ref"])
        p16 = json.load(open(f"{PC}/pass16_by_id.json"))
        imp = set(x.strip() for x in open(f"{PC}/impossible_ids.txt") if x.strip())
        for pid in sorted(cc):
            row = [pid]
            for L in range(4):
                d = cc[pid].get(L)
                row += ([d["correct"], d["unique"], d["ncand"], d["miss"]] if d else ["", "", "", ""])
            v = p16.get(pid)
            k = "unknown" if v is None else ("saturated" if v >= 16 else ("impossible" if (pid in imp or v == 0) else "informative"))
            w.writerow(row + [k])

    # ---- compare vs repo CSV ----
    repo_rows = {r["problem_id"]: r for r in csv.DictReader(open(f"{SE16}/frontier/per_problem_correct_counts.csv"))}
    diffs = []
    for pid, loops in cc.items():
        rr = repo_rows.get(pid)
        if rr is None:
            diffs.append([pid, "missing_in_repo_csv", "", ""])
            continue
        for L in range(3):  # repo CSV has loops 0..2
            mine = loops.get(L, {}).get("correct")
            theirs = rr.get(f"loop{L}_correct", "")
            theirs = int(theirs) if theirs not in ("", None) else None
            if mine != theirs:
                diffs.append([pid, f"loop{L}", mine, theirs])
    with open(f"{OUT}/tables/recompute_vs_repo_diff.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["problem_id", "field", "recomputed", "repo_csv"])
        w.writerows(diffs)

    # ---- pop-8 loop0 ∪ loop0b vs pass16_by_id.json (provenance of problem classes) ----
    bon_cache = load_cache("outputs/grading_cache/reachability_bon.jsonl")
    print(f"[cache] reachability_bon.jsonl entries: {len(bon_cache)}")
    pop8 = {}
    pop8_miss = 0
    for sh in range(4):
        recs0 = [json.loads(l) for l in open(f"{POP8}/sh{sh}/loop0_out.jsonl")]
        recsb = [json.loads(l) for l in open(f"{POP8}/sh{sh}/loop0b_out.jsonl")]
        byid_b = {r["id"]: r for r in recsb}
        for r in recs0:
            pid = r["id"]
            tj, tl = pool[pid]
            cands = (r.get("candidates") or []) + ((byid_b.get(pid) or {}).get("candidates") or [])
            n, raw, uniq, miss, nocode = grade_candidates(cands, tj, tl, bon_cache)
            pop8[pid] = {"ncand": n, "correct": raw, "miss": miss}
            pop8_miss += miss
    p16 = json.load(open(f"{PC}/pass16_by_id.json"))
    match = sum(1 for pid, d in pop8.items() if p16.get(pid) == d["correct"])
    with open(f"{OUT}/tables/pop8_pass16_recompute.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["problem_id", "pop8_l0_plus_l0b_correct_of_16", "ncand", "cache_miss", "pass16_by_id", "match"])
        for pid in sorted(pop8):
            d = pop8[pid]
            w.writerow([pid, d["correct"], d["ncand"], d["miss"], p16.get(pid), p16.get(pid) == d["correct"]])

    # ---- summary ----
    summary = {
        "n_problems_se16": n_probs,
        "duplicate_ids_across_shards": len(dup),
        "per_loop": {},
        "repo_csv_diff_rows": len(diffs),
        "pop8_provenance": {
            "n": len(pop8),
            "match_pass16_by_id": match,
            "match_rate": round(match / max(1, len(pop8)), 4),
            "cache_misses": pop8_miss,
        },
    }
    for L in range(4):
        pids = [p for p in cc if L in cc[p]]
        if not pids:
            continue
        vals = [cc[p][L]["correct"] for p in pids]
        summary["per_loop"][f"loop{L}"] = {
            "n_problems": len(pids),
            "solvable": sum(1 for v in vals if v > 0),
            "raw_correct": sum(vals),
            "unique_correct": sum(cc[p][L]["unique"] for p in pids),
            "cache_miss_candidates": sum(cc[p][L]["miss"] for p in pids),
            "nocode_candidates": sum(cc[p][L]["nocode"] for p in pids),
            "ncand_total": sum(cc[p][L]["ncand"] for p in pids),
        }
    json.dump(summary, open(f"{OUT}/recompute_se16_summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
