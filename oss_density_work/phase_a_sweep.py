"""Phase A: find the best gpt-oss-120B self-verification setting for per-problem DENSITY estimation.
Data: se16 loop0 (pop16), gold loop0_correct from frontier csv. For a stratified sample, estimate the
density (expected #correct of 16) with several variants, compare to gold. Cached+resumable.
Goal metric prioritizes SATURATED/near-saturated identification (what the freeze rule needs)."""
import os, sys, json, glob, random, re, math, csv, hashlib, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
os.chdir("/mnt/cpfs/yangboxue/opsd/TTS/tts-sft")
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
WORK = "/mnt/cpfs/yangboxue/opsd/oss_density_work"
CACHE = f"{WORK}/calls_cache.jsonl"
PORT, MODEL = "8000", "gpt-oss-120b"

# ---- persistent call cache (survives pod restarts) ----
_cache = {}
if os.path.exists(CACHE):
    for l in open(CACHE):
        try:
            d = json.loads(l); _cache[d["k"]] = d["v"]
        except Exception:
            pass
_cf = open(CACHE, "a")
def cached_call(key, fn):
    if key in _cache:
        return _cache[key]
    v = fn()
    _cache[key] = v
    _cf.write(json.dumps({"k": key, "v": v}) + "\n"); _cf.flush()
    return v

# ---- data: gold loop0 + 16 loop0 candidates + question ----
gold = {}
for r in csv.DictReader(open(f"{SE16}/frontier/per_problem_correct_counts.csv")):
    if r.get("loop0_correct") not in (None, ""):
        gold[r["problem_id"]] = int(r["loop0_correct"])
random.seed(0)
def coarse(c): return "0" if c == 0 else "1-4" if c <= 4 else "5-8" if c <= 8 else "9-15" if c <= 15 else "16"
by = defaultdict(list)
for p in gold: by[coarse(gold[p])].append(p)
K_PER = int(os.environ.get("K_PER", "30"))
sample = []
for b in ["0", "1-4", "5-8", "9-15", "16"]:
    sample += random.sample(by[b], min(K_PER, len(by[b])))
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
print(f"sample={len(sample)} problems ; gold buckets: {{b: n}} = " +
      str({b: sum(1 for p in sample if coarse(gold[p]) == b) for b in ['0','1-4','5-8','9-15','16']}), flush=True)

def code(s):
    m = re.findall(r"```(?:python)?\s*(.*?)```", s or "", re.S); return (max(m, key=len).strip() if m else (s or ""))[:1700]

def graded_prob(pid, i, effort, rep):
    key = f"g|{effort}|{pid}|{i}|{rep}"
    def call():
        prompt = (f"Verify a candidate solution to a competitive programming problem. Estimate the PROBABILITY "
                  f"it is FULLY CORRECT for ALL valid inputs (algorithm, edge cases, exact stdin/stdout). Be "
                  f"calibrated: 100=certain correct, 0=certain wrong, 50=unsure.\n\nPROBLEM:\n{ques[pid][:2800]}\n\n"
                  f"SOLUTION:\n```python\n{code(cand[pid][i])}\n```\n\nReason briefly, end with exactly: 'PROB: <0-100>'.")
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0,
                "max_tokens": 1400, "reasoning_effort": effort}
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=240).read()); txt = r["choices"][0]["message"]["content"] or ""
            m = re.findall(r"PROB:\s*(\d{1,3})", txt.upper())
            p = int(m[-1]) if m else (int(re.findall(r"(\d{1,3})", txt)[-1]) if re.findall(r"(\d{1,3})", txt) else 50)
            return max(0, min(100, p)) / 100.0
        except Exception:
            return 0.5
    return cached_call(key, call)

VARIANTS = [("low_k1", "low", 1), ("low_k3", "low", 3), ("medium_k1", "medium", 1)]
# build all needed tasks, run once (cache dedups), then aggregate per variant
tasks = []
for name, effort, k in VARIANTS:
    for pid in sample:
        for i in range(NC[pid]):
            for rep in range(k):
                tasks.append((pid, i, effort, rep))
seen = set(); tasks = [t for t in tasks if (t not in seen and not seen.add(t))]
print(f"total unique calls needed: {len(tasks)} (cached so far: {len(_cache)})", flush=True)
done = 0
with ThreadPoolExecutor(max_workers=40) as ex:
    for _ in ex.map(lambda t: graded_prob(*t), tasks):
        done += 1
        if done % 500 == 0: print(f"  {done}/{len(tasks)} calls", flush=True)

def pearson(x, y):
    n = len(x); mx = sum(x)/n; my = sum(y)/n; num = sum((a-mx)*(b-my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a-mx)**2 for a in x)); dy = math.sqrt(sum((b-my)**2 for b in y)); return num/(dx*dy) if dx and dy else float("nan")

results = {}
for name, effort, k in VARIANTS:
    est = {}
    for pid in sample:
        est[pid] = sum(sum(graded_prob(pid, i, effort, rep) for rep in range(k))/k for i in range(NC[pid]))
    G = [gold[p] for p in sample]; E = [est[p] for p in sample]; n = len(sample)
    r = pearson(E, G); mae = sum(abs(a-b) for a, b in zip(E, G))/n; bias = sum(a-b for a, b in zip(E, G))/n
    # SATURATED/near-sat = the freeze target: gold>=9 (of 16). est threshold swept.
    best = None
    for thr in [x*0.5 for x in range(12, 32)]:   # 6.0 .. 15.5
        tp = sum(1 for p in sample if est[p] >= thr and gold[p] >= 9); fp = sum(1 for p in sample if est[p] >= thr and gold[p] < 9); fn = sum(1 for p in sample if est[p] < thr and gold[p] >= 9)
        P = tp/(tp+fp) if tp+fp else 0; R = tp/(tp+fn) if tp+fn else 0; f1 = 2*P*R/(P+R) if P+R else 0
        if best is None or f1 > best[3]: best = (thr, P, R, f1)
    results[name] = {"r": round(r, 3), "mae": round(mae, 2), "bias": round(bias, 2),
                     "freeze(gold>=9) best_thr": round(best[0], 1), "freeze_P": round(best[1], 2),
                     "freeze_R": round(best[2], 2), "freeze_F1": round(best[3], 2),
                     "calib": {c: round(sum(est[p] for p in sample if gold[p] == c)/max(1, sum(1 for p in sample if gold[p] == c)), 2) for c in range(0, 17)}}
    # save per-problem est for Phase B reuse
    json.dump({p: {"gold": gold[p], "est": round(est[p], 3), "nc": NC[p]} for p in sample},
              open(f"{WORK}/estA_{name}.json", "w"))

print("\n=== PHASE A RESULTS (gpt-oss-120B density estimate vs gold loop0 count /16) ===")
print(f"{'variant':12} {'r':>5} {'MAE':>5} {'bias':>6} | freeze(gold>=9): {'thr':>4} {'P':>4} {'R':>4} {'F1':>4}")
for name in results:
    d = results[name]
    print(f"{name:12} {d['r']:>5} {d['mae']:>5} {d['bias']:>6} | {d['freeze(gold>=9) best_thr']:>18} {d['freeze_P']:>4} {d['freeze_R']:>4} {d['freeze_F1']:>4}")
json.dump({"sample_n": len(sample), "variants": results}, open(f"{WORK}/phase_a_results.json", "w"), indent=2)
print(f"\n[saved] {WORK}/phase_a_results.json + estA_*.json")
