#!/usr/bin/env python3
"""Phase 7 (+ shared per-candidate dump for Phase 8): offline stopping-rule simulation on the se16
loop trajectories. Also writes tables/per_candidate_grades.jsonl.gz
{pid, loop, idx, passed, h(md5 of normalized code), shard} for loops 0..3 (loop3 partial).

Rules simulated per problem (decision after each completed loop, using ONLY info available then):
  R0  full run (baseline): evolve everything for 2 loops (loop1+loop2).
  R1  stop when raw correct count DECREASES vs previous loop.
  R2  stop when cumulative-unique gain is zero (no new unique correct this loop).
  R3  stop when no newly-correct problem-level solve AND no unique gain (strict dry).
  R4  boundary-only: evolve only loop0 buckets 1..8 (drop 0 and 9-15 after loop0).
  R5  freeze near-saturated: evolve buckets 0..8 (drop 9-15), i.e. R4 + keep 0-bucket exploration.
  R6  R5 but stop each problem early per R1 as well.
Metrics per rule: generations spent (vs 34,976 = 1093*16*2 evolution gens), problems evolved per loop,
unique-correct retained (cumulative, best-so-far kept on disk), frontier problems preserved
(of the 58-problem ref-244 union), and hard-tail coverage.
"""
import csv
import glob
import gzip
import hashlib
import json
import os
import re
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
SHARDS = ["sh0", "sh1", "sh2", "sh3", "sh4", "sh7", "sh8",
          "redo_sh0", "redo_sh1", "redo_sh2", "redo_sh3", "redo_sh4", "redo_sh5"]

cache = {}
for line in open("outputs/grading_cache/se16.jsonl"):
    r = json.loads(line)
    cache[r["k"]] = r["v"]
pool = {}
for line in open("data/openthoughts114k_codeforces_stdin_clean.jsonl"):
    r = json.loads(line)
    s = r["test_cases"]
    tj = s if isinstance(s, str) else json.dumps(s)
    pool[r["seed_id"]] = (tj, float(json.loads(tj).get("time_limit") or 6.0))

# ---- per-candidate dump ----
rows = []
sets = defaultdict(lambda: defaultdict(set))   # pid -> loop -> set(hash of passing normalized code)
counts = defaultdict(dict)                     # pid -> loop -> raw correct
complete = defaultdict(dict)                   # pid -> loop -> fully graded bool
for sh in SHARDS:
    root = f"{SE16}/{sh}"
    ids = [json.loads(l)["id"] for l in open(f"{root}/out.jsonl")]
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
            miss = 0
            cc = 0
            for j, cand in enumerate(prob.get("candidates") or []):
                code = extract_code(cand)
                if not code:
                    rows.append((pid, loop, j, None, "", sh))
                    continue
                v = cache.get(cache_key(HARNESS, code, tj, tl))
                if v is None:
                    miss += 1
                    rows.append((pid, loop, j, None, "", sh))
                    continue
                p = bool(v.get("passed"))
                h = hashlib.md5(_norm(code).encode()).hexdigest()[:16] if p else ""
                rows.append((pid, loop, j, p, h, sh))
                if p:
                    sets[pid][loop].add(h)
                    cc += 1
            counts[pid][loop] = cc
            complete[pid][loop] = (miss == 0)
    print(f"[dump] {sh}", flush=True)

with gzip.open(f"{OUT}/tables/per_candidate_grades.jsonl.gz", "wt") as f:
    for pid, loop, j, p, h, sh in rows:
        f.write(json.dumps({"pid": pid, "loop": loop, "idx": j, "passed": p, "h": h, "shard": sh}) + "\n")
print(f"[dump] {len(rows)} candidate rows")

pids = sorted(counts)
imp_ids = set(x.strip() for x in open(
    "outputs/openthoughts114k_codeforces_full_datagen/problem_classes/impossible_ids.txt") if x.strip())
frontier58 = {p for p in pids if p in imp_ids and (sets[p].get(1) or sets[p].get(2))}


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


def simulate(rule):
    """Return metrics. Decisions use loop-by-loop info; evolution loops available: 1 and 2."""
    gens = 0
    evolved = {1: 0, 2: 0}
    evolved2_ids = set()
    uniq_retained = 0
    solved = set()
    frontier_kept = set()
    for pid in pids:
        c0 = counts[pid][0]
        b = bucket(c0)
        u_cum = set(sets[pid].get(0, set()))
        prev_c = c0
        active = True
        for L in (1, 2):
            if not active:
                break
            # eligibility rules that depend only on loop0 bucket
            if rule in ("R4",) and b not in ("1", "2-4", "5-8"):
                break
            if rule in ("R5", "R6") and b == "9-15":
                break
            # run loop L
            gens += 16
            evolved[L] += 1
            if L == 2:
                evolved2_ids.add(pid)
            cL = counts[pid][L]
            new_u = len(sets[pid].get(L, set()) - u_cum)
            u_cum |= sets[pid].get(L, set())
            # stopping rules evaluated AFTER the loop
            if rule in ("R1", "R6") and cL < prev_c:
                active = False
            if rule == "R2" and new_u == 0:
                active = False
            if rule == "R3" and new_u == 0 and not (prev_c == 0 and cL > 0):
                active = False
            prev_c = cL
        uniq_retained += len(u_cum)
        if u_cum:
            solved.add(pid)
        if pid in frontier58 and (sets[pid].get(1, set()) | sets[pid].get(2, set())) & u_cum:
            frontier_kept.add(pid)
    boundary = {p for p in pids if bucket(counts[p][0]) in ("1", "2-4", "5-8")}
    return {"rule": rule, "gens_evolution": gens, "gens_saved_vs_full": 34976 - gens,
            "pct_inference_saved": round(100 * (34976 - gens) / 34976, 1),
            "problems_loop1": evolved[1], "problems_loop2": evolved[2],
            "unique_correct_retained": uniq_retained,
            "coverage_any": len(solved),
            "frontier58_preserved": len(frontier_kept), "frontier58_lost": 58 - len(frontier_kept),
            "boundary_retained_loop2": round(len(evolved2_ids & boundary) / max(1, len(boundary)), 3)}


results = [simulate(r) for r in ("R0", "R1", "R2", "R3", "R4", "R5", "R6")]
with open(f"{OUT}/tables/curriculum_stopping_simulation.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0]))
    w.writeheader()
    w.writerows(results)
print(json.dumps(results, indent=2))
