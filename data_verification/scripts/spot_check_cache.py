#!/usr/bin/env python3
"""Phase 1 spot-check: re-EXECUTE a random sample of se16 candidates on the full hidden tests and
compare fresh verdicts against the grading cache (validates the cache wasn't stale/corrupt).
Uses the repo's own harness (scripts/lcb_exec_harness.py) via a throwaway cache file."""
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification"
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.chdir(REPO)
from score_diversify_ab import extract_code  # noqa: E402
from lcb_grading import GradingCache, cache_key, run_harness_cached  # noqa: E402

HARNESS = os.path.join(REPO, "scripts", "lcb_exec_harness.py")
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
random.seed(20260702)

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

# collect candidate universe from 4 random shards x loops 0-2
import glob
import re
univ = []
for sh in ["sh0", "sh4", "redo_sh2", "sh8"]:
    root = f"{SE16}/{sh}"
    ids = [json.loads(l)["id"] for l in open(f"{root}/out.jsonl")]
    rn = re.sub(r"_loop0\.json$", "", os.path.basename(glob.glob(f"{root}/ck/*_loop0.json")[0]))
    for loop in range(3):
        probs = json.load(open(f"{root}/ck/{rn}_loop{loop}.json")).get("problems", [])
        for i, prob in enumerate(probs):
            if i >= len(ids):
                break
            for j, cand in enumerate(prob.get("candidates") or []):
                univ.append((ids[i], loop, j, cand))

random.shuffle(univ)
passed_s, failed_s = [], []
for item in univ:
    pid, loop, j, cand = item
    code = extract_code(cand)
    if not code:
        continue
    tj, tl = pool[pid]
    v = cache.get(cache_key(HARNESS, code, tj, tl))
    if v is None:
        continue
    (passed_s if v.get("passed") else failed_s).append((item, code, v))
    if len(passed_s) >= (N * 2 // 3) and len(failed_s) >= (N - N * 2 // 3):
        break
sample = passed_s[: N * 2 // 3] + failed_s[: N - N * 2 // 3]
print(f"sample: {len(sample)} candidates ({len(passed_s[:N*2//3])} cached-pass, {len(failed_s[:N-N*2//3])} cached-fail)")

fresh_cache = GradingCache(f"{OUT}/tables/_spot_fresh_cache.jsonl")


def run(x):
    (pid, loop, j, cand), code, v_old = x
    tj, tl = pool[pid]
    n = len(json.loads(tj)["inputs"])
    v_new = run_harness_cached(HARNESS, code, tj, n, tl=tl, cache=fresh_cache)
    return pid, loop, j, v_old, v_new


rows = []
with ThreadPoolExecutor(max_workers=10) as ex:
    for pid, loop, j, v_old, v_new in ex.map(run, sample):
        agree = bool(v_new) and (v_new.get("passed") == v_old.get("passed"))
        rows.append({"pid": pid, "loop": loop, "cand": j, "cached_passed": v_old.get("passed"),
                     "fresh_passed": None if not v_new else v_new.get("passed"), "agree": agree,
                     "cached_np": v_old.get("n_passed"), "fresh_np": None if not v_new else v_new.get("n_passed")})
        print(rows[-1], flush=True)

n_agree = sum(1 for r in rows if r["agree"])
res = {"n": len(rows), "agree": n_agree, "agree_rate": round(n_agree / max(1, len(rows)), 4), "rows": rows}
json.dump(res, open(f"{OUT}/tables/spot_check_cache.json", "w"), indent=2)
print(f"\nAGREEMENT: {n_agree}/{len(rows)}")
