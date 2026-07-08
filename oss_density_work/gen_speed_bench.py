"""Benchmark gpt-oss-120B as a GENERATOR for SE loop0 (pop=16 independent solutions/problem).
Measures sustained throughput (tokens/s at concurrency), tokens/candidate, seconds/problem,
and extrapolates to full-dataset wall-clock. Sweeps reasoning_effort (dominates gen length)."""
import os, json, glob, random, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
os.chdir("/mnt/cpfs/yangboxue/opsd/TTS/tts-sft")
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
PORT, MODEL = "8000", "gpt-oss-120b"
N_PROB = int(os.environ.get("N_PROB", "4"))
POP = int(os.environ.get("POP", "16"))
CONC = int(os.environ.get("CONC", "64"))
MAXTOK = int(os.environ.get("MAXTOK", "16384"))
EFFORTS = os.environ.get("EFFORTS", "low,medium,high").split(",")

# grab N_PROB real problem statements
random.seed(3)
qs = []
for root in sorted(glob.glob(f"{SE16}/sh*/")):
    out = f"{root}out.jsonl"
    if not os.path.exists(out): continue
    for l in open(out):
        row = json.loads(l); q = row.get("question")
        if q and 400 < len(q) < 6000: qs.append(q)
    if len(qs) > 400: break
random.shuffle(qs); qs = qs[:N_PROB]
print(f"problems={len(qs)} pop={POP} concurrency={CONC} max_tokens={MAXTOK} efforts={EFFORTS}", flush=True)

def gen(q, effort):
    prompt = (f"Solve this competitive programming problem. Reason step by step, then give a complete, correct "
              f"Python 3 solution that reads from stdin and writes to stdout.\n\nPROBLEM:\n{q}\n\n"
              f"Put the final program in a single ```python``` code block.")
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0, "top_p": 0.95, "max_tokens": MAXTOK, "reasoning_effort": effort}
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=1200).read())
        u = r.get("usage", {}); ct = u.get("completion_tokens", 0)
        txt = r["choices"][0]["message"]["content"] or ""
        has_code = "```" in txt
        fin = r["choices"][0].get("finish_reason", "")
        return {"ok": True, "ct": ct, "lat": time.time()-t0, "cap": fin == "length", "code": has_code}
    except Exception as e:
        return {"ok": False, "ct": 0, "lat": time.time()-t0, "cap": False, "code": False, "err": str(e)[:60]}

results = {}
for eff in EFFORTS:
    tasks = [(q, eff) for q in qs for _ in range(POP)]
    t0 = time.time()
    outs = []
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        for o in ex.map(lambda t: gen(*t), tasks):
            outs.append(o)
    wall = time.time() - t0
    ok = [o for o in outs if o["ok"]]
    tot_ct = sum(o["ct"] for o in ok)
    n = len(tasks); nok = len(ok)
    thr = tot_ct / wall if wall else 0
    mean_ct = tot_ct / nok if nok else 0
    capped = sum(1 for o in ok if o["cap"]); withcode = sum(1 for o in ok if o["code"])
    sec_per_problem = wall / len(qs)                      # POP candidates per problem, at this concurrency
    results[eff] = {"wall_s": round(wall, 1), "n": n, "ok": nok, "tot_out_tok": tot_ct,
                    "throughput_tok_s": round(thr), "mean_tok_per_cand": round(mean_ct),
                    "mean_lat_s": round(sum(o["lat"] for o in ok)/nok, 1) if nok else 0,
                    "capped_pct": round(100*capped/nok, 1) if nok else 0,
                    "has_code_pct": round(100*withcode/nok, 1) if nok else 0,
                    "sec_per_problem_16": round(sec_per_problem, 1)}
    r = results[eff]
    # extrapolate: full-dataset hours = (Nprob * POP * mean_tok) / throughput
    def hrs(Nds): return round((Nds * POP * mean_ct) / thr / 3600, 1) if thr else float("inf")
    print(f"\n=== effort={eff} ===")
    print(f"  wall={r['wall_s']}s for {nok}/{n} gens | throughput={r['throughput_tok_s']} tok/s | mean {r['mean_tok_per_cand']} tok/cand (lat {r['mean_lat_s']}s)")
    print(f"  capped@{MAXTOK}: {r['capped_pct']}% | has-code: {r['has_code_pct']}% | ~{r['sec_per_problem_16']}s per problem (pop16 @conc{CONC})")
    print(f"  EXTRAPOLATED loop0-pop16 wall-clock @ this throughput: cc-nonsat(3487)={hrs(3487)}h  full-pool(8124)={hrs(8124)}h", flush=True)

json.dump({"cfg": {"n_prob": N_PROB, "pop": POP, "conc": CONC, "max_tok": MAXTOK}, "results": results},
          open("/mnt/cpfs/yangboxue/opsd/oss_density_work/gen_speed_results.json", "w"), indent=2)
print("\n[saved] gen_speed_results.json")
