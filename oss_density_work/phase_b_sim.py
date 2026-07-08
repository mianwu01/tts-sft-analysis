"""Phase B: simulate an OSS-estimated FREEZE/stopping rule vs the ORACLE gold-test freeze rule on se16.
Oracle freeze = gold loop0_correct >= 9 (the 9-15 near-saturated bucket, ~'freeze-9-15 = 48% compute free').
OSS freeze = OSS-estimated loop0 density >= threshold (from Phase A best variant).
Representative RANDOM sample (so compute-saved % reflects the true mix). Cached/resumable.
Metrics: compute-saved %, frontier-lost (frozen problems that gold loop1/2 shows would still gain
solvability), agreement vs the oracle freeze set, threshold sweep."""
import os, json, glob, random, re, math, csv, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
os.chdir("/mnt/cpfs/yangboxue/opsd/TTS/tts-sft")
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
WORK = "/mnt/cpfs/yangboxue/opsd/oss_density_work"
CACHE = f"{WORK}/calls_cache.jsonl"
PORT, MODEL = "8000", "gpt-oss-120b"
VARIANT = os.environ.get("VARIANT", "low_k1")   # low_k1 | trace
N_SAMPLE = int(os.environ.get("N_SAMPLE", "300"))
_cache = {}
if os.path.exists(CACHE):
    for l in open(CACHE):
        try:
            d = json.loads(l); _cache[d["k"]] = d["v"]
        except Exception: pass
_cf = open(CACHE, "a")
def cached_call(key, fn):
    if key in _cache: return _cache[key]
    v = fn(); _cache[key] = v; _cf.write(json.dumps({"k": key, "v": v}) + "\n"); _cf.flush(); return v

# gold loop0/1/2
g0, g1, g2 = {}, {}, {}
for r in csv.DictReader(open(f"{SE16}/frontier/per_problem_correct_counts.csv")):
    if r.get("loop0_correct") in (None, ""): continue
    pid = r["problem_id"]; g0[pid] = int(r["loop0_correct"])
    g1[pid] = int(r["loop1_correct"]) if r.get("loop1_correct") not in (None, "") else None
    g2[pid] = int(r["loop2_correct"]) if r.get("loop2_correct") not in (None, "") else None

SEED = int(os.environ.get("SEED", "7"))
random.seed(SEED)
allp = [p for p in g0 if g2.get(p) is not None]      # need loop2 gold to score frontier
random.shuffle(allp)
picked = allp[:N_SAMPLE * 2]                          # oversample; keep those with candidates
def rn_of(root):
    c = glob.glob(f"{root}/ck/*_loop0.json"); return re.sub(r"_loop0\.json$", "", os.path.basename(c[0])) if c else None
pset = set(picked); cand, ques = {}, {}
for root in sorted(glob.glob(f"{SE16}/sh*/") + glob.glob(f"{SE16}/redo_sh*/")):
    rn = rn_of(root); out = f"{root}out.jsonl"
    if not rn or not os.path.exists(out): continue
    ids = [json.loads(l) for l in open(out)]
    ck = f"{root}ck/{rn}_loop0.json"
    if not os.path.exists(ck): continue
    probs = json.load(open(ck)).get("problems", [])
    for i, row in enumerate(ids):
        if row["id"] in pset and i < len(probs) and row["id"] not in cand:
            cand[row["id"]] = probs[i].get("candidates") or []
            ques[row["id"]] = row.get("question") or probs[i].get("question") or ""
sample = [p for p in picked if cand.get(p)][:N_SAMPLE]
NC = {p: len(cand[p]) for p in sample}
print(f"Phase B sample={len(sample)} (variant={VARIANT}); gold-loop0 dist: " +
      str({b: sum(1 for p in sample if (g0[p]==0 if b=='0' else g0[p]<=4 if b=='1-4' else g0[p]<=8 if b=='5-8' else g0[p]>=9)) for b in ['0','1-4','5-8','9+']}), flush=True)

def code(s):
    m = re.findall(r"```(?:python)?\s*(.*?)```", s or "", re.S); return (max(m, key=len).strip() if m else (s or ""))[:1700]

def est_one(pid, i):
    if VARIANT == "trace":
        key = f"t|low|{pid}|{i}|0"
        prompt = (f"You are stress-testing a candidate solution to a competitive programming problem.\n\n"
                  f"PROBLEM:\n{ques[pid][:2800]}\n\nSOLUTION:\n```python\n{code(cand[pid][i])}\n```\n\n"
                  f"Steps: (1) name 2-3 concrete inputs incl. edge cases (min/max sizes, empty, ties, overflow). "
                  f"(2) trace the code on each and compare to the correct expected output. (3) judge overall correctness "
                  f"for ALL valid inputs. Then give the PROBABILITY it is FULLY CORRECT (calibrated: 100=certain, 0=certain wrong). "
                  f"End with exactly: 'PROB: <0-100>'.")
        mx = 1800
    else:
        key = f"g|low|{pid}|{i}|0"
        prompt = (f"Verify a candidate solution to a competitive programming problem. Estimate the PROBABILITY "
                  f"it is FULLY CORRECT for ALL valid inputs (algorithm, edge cases, exact stdin/stdout). Be "
                  f"calibrated: 100=certain correct, 0=certain wrong, 50=unsure.\n\nPROBLEM:\n{ques[pid][:2800]}\n\n"
                  f"SOLUTION:\n```python\n{code(cand[pid][i])}\n```\n\nReason briefly, end with exactly: 'PROB: <0-100>'.")
        mx = 1400
    def call():
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0,
                "max_tokens": mx, "reasoning_effort": "low"}
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=300).read()); txt = r["choices"][0]["message"]["content"] or ""
            m = re.findall(r"PROB:\s*(\d{1,3})", txt.upper())
            p = int(m[-1]) if m else (int(re.findall(r"(\d{1,3})", txt)[-1]) if re.findall(r"(\d{1,3})", txt) else 50)
            return max(0, min(100, p)) / 100.0
        except Exception:
            return 0.5
    return cached_call(key, call)

tasks = [(pid, i) for pid in sample for i in range(NC[pid])]
print(f"calls needed: {len(tasks)} (cached: {sum(1 for t in tasks if ('t|low|' if VARIANT=='trace' else 'g|low|')+t[0]+'|'+str(t[1])+'|0' in _cache)})", flush=True)
done = 0
with ThreadPoolExecutor(max_workers=40) as ex:
    for _ in ex.map(lambda t: est_one(*t), tasks):
        done += 1
        if done % 500 == 0: print(f"  {done}/{len(tasks)}", flush=True)
est = {p: sum(est_one(p, i) for i in range(NC[p])) for p in sample}

# calibration (fixed transform learned in Phase A2)
a, b = 1.0, 0.0
try:
    c = json.load(open(f"{WORK}/phase_a2_results.json"))["low_k1_calib"]; a, b = c["a"], c["b"]
except Exception: pass
cest = {p: max(0.0, min(16.0, a*est[p]+b)) for p in sample}

# gold-derived frontier facts (per problem)
def newsolve(p): return g0[p] == 0 and (g2[p] or 0) > 0                    # crossed reachability frontier via loops
def dens_gain(p): return (g2[p] or 0) - g0[p]                              # extra correct from loops (may be dups)
def real_gain(p): return newsolve(p) or dens_gain(p) >= 3                  # a loop payoff worth NOT freezing
n = len(sample)
tot_newsolve = sum(1 for p in sample if newsolve(p))
tot_realgain = sum(1 for p in sample if real_gain(p))

def evaluate(frozen):
    fz = set(frozen); nf = len(fz)
    lost_ns = sum(1 for p in fz if newsolve(p))
    lost_rg = sum(1 for p in fz if real_gain(p))
    return {"n_frozen": nf, "compute_saved_pct": round(100*nf/n, 1),
            "frontier_lost_newsolve": lost_ns, "frontier_lost_realgain": lost_rg}

oracle = [p for p in sample if g0[p] >= 9]
oracle_set = set(oracle)
res = {"n": n, "tot_newsolve": tot_newsolve, "tot_realgain": tot_realgain, "variant": VARIANT,
       "calib": {"a": a, "b": b}, "oracle_freeze(loop0>=9)": evaluate(oracle)}

# OSS raw threshold sweep
sweep = []
for thr in [x*0.5 for x in range(8, 30)]:            # 4.0 .. 14.5
    frozen = [p for p in sample if est[p] >= thr]; ev = evaluate(frozen)
    fs = set(frozen)
    tp = len(fs & oracle_set); prec = tp/len(fs) if fs else 0; rec = tp/len(oracle_set) if oracle_set else 0
    ev.update({"thr": thr, "agree_prec_vs_oracle": round(prec, 2), "agree_rec_vs_oracle": round(rec, 2)})
    sweep.append(ev)
res["oss_raw_sweep"] = sweep
# OSS calibrated at the natural threshold (calibrated density >= 9)
res["oss_calibrated_freeze(calib>=9)"] = evaluate([p for p in sample if cest[p] >= 9])
res["oss_calibrated_freeze(calib>=10)"] = evaluate([p for p in sample if cest[p] >= 10])

# operating point matched to oracle compute-saved
oracle_cs = res["oracle_freeze(loop0>=9)"]["compute_saved_pct"]
matched = min(sweep, key=lambda e: abs(e["compute_saved_pct"] - oracle_cs))
res["oss_matched_to_oracle_compute"] = matched

OUT = f"{WORK}/phase_b_results.json" if SEED == 7 else f"{WORK}/phase_b_results_{VARIANT}_seed{SEED}.json"
json.dump(res, open(OUT, "w"), indent=2)
print("\n=== PHASE B: OSS freeze vs ORACLE freeze (se16, random n=%d) ===" % n)
print(f"  total new-solves (loop0=0 -> loop2>0) in sample: {tot_newsolve} ; real-gain problems (newsolve or +>=3 density): {tot_realgain}")
o = res["oracle_freeze(loop0>=9)"]
print(f"  ORACLE freeze(loop0>=9): freeze {o['n_frozen']} ({o['compute_saved_pct']}% compute saved), frontier-lost newsolve={o['frontier_lost_newsolve']} realgain={o['frontier_lost_realgain']}")
m = matched
print(f"  OSS matched@compute={m['compute_saved_pct']}% (thr={m['thr']}): freeze {m['n_frozen']}, frontier-lost newsolve={m['frontier_lost_newsolve']} realgain={m['frontier_lost_realgain']}, agree P={m['agree_prec_vs_oracle']} R={m['agree_rec_vs_oracle']}")
cc = res["oss_calibrated_freeze(calib>=9)"]
print(f"  OSS calibrated(calib>=9): freeze {cc['n_frozen']} ({cc['compute_saved_pct']}%), frontier-lost newsolve={cc['frontier_lost_newsolve']} realgain={cc['frontier_lost_realgain']}")
print(f"[saved] {OUT}")
