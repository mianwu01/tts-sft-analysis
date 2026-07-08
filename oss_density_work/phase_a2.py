"""Phase A2: (1) test a 'trace concrete inputs' prompt variant (can it beat the r=0.73 ceiling?),
(2) linear leave-one-out calibration of the low_k1 estimate (fixes the absolute-count bias).
Reuses the same 120-problem sample + persistent call cache."""
import os, json, glob, random, re, math, csv, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
os.chdir("/mnt/cpfs/yangboxue/opsd/TTS/tts-sft")
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
WORK = "/mnt/cpfs/yangboxue/opsd/oss_density_work"
CACHE = f"{WORK}/calls_cache.jsonl"
PORT, MODEL = "8000", "gpt-oss-120b"
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

gold = {}
for r in csv.DictReader(open(f"{SE16}/frontier/per_problem_correct_counts.csv")):
    if r.get("loop0_correct") not in (None, ""): gold[r["problem_id"]] = int(r["loop0_correct"])
random.seed(0)
def coarse(c): return "0" if c == 0 else "1-4" if c <= 4 else "5-8" if c <= 8 else "9-15" if c <= 15 else "16"
by = defaultdict(list)
for p in gold: by[coarse(gold[p])].append(p)
sample = []
for b in ["0", "1-4", "5-8", "9-15", "16"]:
    sample += random.sample(by[b], min(30, len(by[b])))
sset = set(sample)
def rn_of(root):
    c = glob.glob(f"{root}/ck/*_loop0.json"); return re.sub(r"_loop0\.json$", "", os.path.basename(c[0])) if c else None
cand, ques = {}, {}
for root in sorted(glob.glob(f"{SE16}/sh*/") + glob.glob(f"{SE16}/redo_sh*/")):
    rn = rn_of(root); out = f"{root}out.jsonl"
    if not rn or not os.path.exists(out): continue
    ids = [json.loads(l) for l in open(out)]
    ck = f"{root}ck/{rn}_loop0.json"
    if not os.path.exists(ck): continue
    probs = json.load(open(ck)).get("problems", [])
    for i, row in enumerate(ids):
        if row["id"] in sset and i < len(probs):
            cand[row["id"]] = probs[i].get("candidates") or []
            ques[row["id"]] = row.get("question") or probs[i].get("question") or ""
sample = [p for p in sample if cand.get(p)]
NC = {p: len(cand[p]) for p in sample}
def code(s):
    m = re.findall(r"```(?:python)?\s*(.*?)```", s or "", re.S); return (max(m, key=len).strip() if m else (s or ""))[:1700]

def trace_prob(pid, i):
    key = f"t|low|{pid}|{i}|0"
    def call():
        prompt = (f"You are stress-testing a candidate solution to a competitive programming problem.\n\n"
                  f"PROBLEM:\n{ques[pid][:2800]}\n\nSOLUTION:\n```python\n{code(cand[pid][i])}\n```\n\n"
                  f"Steps: (1) name 2-3 concrete inputs incl. edge cases (min/max sizes, empty, ties, overflow). "
                  f"(2) trace the code on each and compare to the correct expected output. (3) judge overall correctness "
                  f"for ALL valid inputs. Then give the PROBABILITY it is FULLY CORRECT (calibrated: 100=certain, 0=certain wrong). "
                  f"End with exactly: 'PROB: <0-100>'.")
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0,
                "max_tokens": 1800, "reasoning_effort": "low"}
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
print(f"trace variant: {len(tasks)} calls (sample={len(sample)})", flush=True)
done = 0
with ThreadPoolExecutor(max_workers=40) as ex:
    for _ in ex.map(lambda t: trace_prob(*t), tasks):
        done += 1
        if done % 400 == 0: print(f"  {done}/{len(tasks)}", flush=True)

def pearson(x, y):
    n = len(x); mx = sum(x)/n; my = sum(y)/n; num = sum((a-mx)*(b-my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a-mx)**2 for a in x)); dy = math.sqrt(sum((b-my)**2 for b in y)); return num/(dx*dy) if dx and dy else float("nan")
est = {p: sum(trace_prob(p, i) for i in range(NC[p])) for p in sample}
G = [gold[p] for p in sample]; E = [est[p] for p in sample]; n = len(sample)
r = pearson(E, G); mae = sum(abs(a-b) for a, b in zip(E, G))/n; bias = sum(a-b for a, b in zip(E, G))/n
best = None
for thr in [x*0.5 for x in range(12, 32)]:
    tp = sum(1 for p in sample if est[p] >= thr and gold[p] >= 9); fp = sum(1 for p in sample if est[p] >= thr and gold[p] < 9); fn = sum(1 for p in sample if est[p] < thr and gold[p] >= 9)
    P = tp/(tp+fp) if tp+fp else 0; R = tp/(tp+fn) if tp+fn else 0; f1 = 2*P*R/(P+R) if P+R else 0
    if best is None or f1 > best[3]: best = (thr, P, R, f1)
json.dump({p: {"gold": gold[p], "est": round(est[p], 3), "nc": NC[p]} for p in sample}, open(f"{WORK}/estA_trace.json", "w"))
print(f"\n=== TRACE prompt variant ===\n  r={r:.3f} MAE={mae:.2f} bias={bias:.2f} | freeze(gold>=9): thr={best[0]:.1f} P={best[1]:.2f} R={best[2]:.2f} F1={best[3]:.2f}")

# ---- linear leave-one-out calibration of low_k1 (fixes absolute-count bias) ----
lk = json.load(open(f"{WORK}/estA_low_k1.json"))
pts = [(v["est"], v["gold"]) for v in lk.values()]
def linfit(pts):
    n = len(pts); sx = sum(x for x, _ in pts); sy = sum(y for _, y in pts)
    sxx = sum(x*x for x, _ in pts); sxy = sum(x*y for x, y in pts)
    den = n*sxx - sx*sx; a = (n*sxy - sx*sy)/den if den else 1.0; b = (sy - a*sx)/n; return a, b
raw_mae = sum(abs(x-y) for x, y in pts)/len(pts)
loo = []
for j in range(len(pts)):
    a, b = linfit(pts[:j]+pts[j+1:]); x, y = pts[j]; loo.append(abs(max(0, min(16, a*x+b))-y))
a_all, b_all = linfit(pts)
print(f"\n=== low_k1 linear LOO calibration ===\n  fit: gold ~= {a_all:.2f}*est + {b_all:.2f}")
print(f"  raw MAE={raw_mae:.2f}  ->  calibrated LOO MAE={sum(loo)/len(loo):.2f}")
json.dump({"trace": {"r": round(r,3), "mae": round(mae,2), "bias": round(bias,2), "freeze_F1": round(best[3],2),
                     "freeze_thr": best[0], "freeze_P": round(best[1],2), "freeze_R": round(best[2],2)},
           "low_k1_calib": {"a": round(a_all,3), "b": round(b_all,3), "raw_mae": round(raw_mae,2),
                            "loo_mae": round(sum(loo)/len(loo),2)}}, open(f"{WORK}/phase_a2_results.json", "w"), indent=2)
print(f"[saved] {WORK}/phase_a2_results.json + estA_trace.json")
