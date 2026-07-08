#!/usr/bin/env python3
"""Measure SE-generation token distributions from the ACTUAL se16 loop0/1/2 data, tokenized with the
gpt-oss-120B tokenizer. No model inference; no repo modification. Reconstructs the REAL prompts:
 - loop0 input  = raw problem (orig_prompt); SE loop-0 recomb([]) returns the query unchanged.
 - loop1/2 input = make_aggregate_prompt(query, k=4 strip_think'd parents)  (config: k=4, population=16, loops=2).
Output tokens: measured from the existing (Qwen3-4B) candidates (reference/upper-bound, incl. 40960-cap tail);
the gpt-oss cost basis uses separately-measured gpt-oss direct-gen lengths (gen_speed_results.json)."""
import os, json, glob, re, random, csv
import numpy as np
from transformers import AutoTokenizer

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
SE16 = f"{REPO}/outputs/openthoughts114k_codeforces_full_datagen/se16"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/oss120b_generation_cost_estimate"
os.makedirs(f"{OUT}/tables", exist_ok=True)
random.seed(0)
tok = AutoTokenizer.from_pretrained("/mnt/cpfs/yangboxue/opsd/models/gpt-oss-120b")
def ntok(s): return len(tok.encode(s or "", add_special_tokens=False))

CAP = 40960                    # config max_tokens for the existing Qwen3-4B se16 run
CHAT_OH = 80                   # harmony/chat scaffolding added by an OpenAI-compatible endpoint (documented estimate)
K_PARENTS = 4                  # config routing.k
N_SAMPLE = int(os.environ.get("N_SAMPLE", "100"))
SHARDS = ["sh0", "sh1", "sh2", "sh3", "sh4", "sh7", "sh8",
          "redo_sh0", "redo_sh1", "redo_sh2", "redo_sh3", "redo_sh4", "redo_sh5"]

# ---- faithful replicas of the repo's operators ----
def strip_think_blocks(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in text and "</think>" not in text:
        text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^.*?</think>", "", text, flags=re.DOTALL).strip()
    return text

def extract_code(text):
    m = re.findall(r"```(?:python)?\s*(.*?)```", strip_think_blocks(text) or "", re.DOTALL)
    return max(m, key=len).strip() if m else ""

def aggregate_prompt(query, parents):  # replica of make_aggregate_prompt (is_code=True, multi-candidate)
    kind = "competitive programming problem"; answer_format = "a ```python ...``` code block"
    parts = [f"You are given a {kind} and several candidate solutions. Some candidates may be better than "
             "others. Combine the best ideas and fix issues in weaker solutions. Produce a single, improved "
             f"solution. Return your final code in {answer_format}.\n", "Problem:\n", query.strip() + "\n",
             "Candidate solutions (may contain mistakes):\n"]
    for i, ans in enumerate(parents, 1):
        parts.append(f"---- Solution {i} ----\n{(ans or '').strip()}\n")
    parts.append(f"Now write a single improved solution. Provide clear reasoning and return the final code in {answer_format}.")
    return "\n".join(parts)

# ---- load problems + candidates ----
def rn_of(root):
    c = glob.glob(f"{root}/ck/*_loop0.json"); return re.sub(r"_loop0\.json$", "", os.path.basename(c[0])) if c else None

allq = {}          # pid -> question (all problems, for problem-token dist)
cand = {}          # pid -> {loop: [candidates]}
for sh in SHARDS:
    root = f"{SE16}/{sh}"; out = f"{root}/out.jsonl"
    if not os.path.exists(out): continue
    rows = [json.loads(l) for l in open(out)]; rn = rn_of(root)
    for r in rows: allq[r["id"]] = r.get("question") or ""
    for L in (0, 1, 2):
        ck = f"{root}/ck/{rn}_loop{L}.json"
        if not os.path.exists(ck): continue
        probs = json.load(open(ck)).get("problems", [])
        for i, r in enumerate(rows):
            if i < len(probs):
                cand.setdefault(r["id"], {})[L] = probs[i].get("candidates") or []
pids_all = [p for p in allq if p in cand and all(L in cand[p] for L in (0, 1, 2))]
print(f"problems with loop0/1/2 candidates: {len(pids_all)}", flush=True)

# ---- Task 1: generation call counts ----
n_prob = len(pids_all); cpp = 16
with open(f"{OUT}/tables/generation_call_counts.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["loop", "n_problems", "candidates_per_problem", "generation_calls",
                                   "degenerate_outputs(capped/no-code)", "denominator_note"])
    deg = {}
    for L in (0, 1, 2):
        d = 0
        for p in pids_all:
            for c in cand[p][L]:
                if extract_code(c) == "": d += 1
        deg[L] = d
        w.writerow([L, n_prob, cpp, n_prob * cpp, d, f"{n_prob} problems x 16 candidates"])
    w.writerow(["TOTAL", n_prob, cpp, n_prob * cpp * 3, sum(deg.values()), f"{n_prob} x 3 loops x 16 = {n_prob*cpp*3}"])
print(f"[task1] calls total={n_prob*cpp*3} degenerate={deg}", flush=True)

# ---- problem-token distribution (all problems) ----
prob_tok = np.array([ntok(allq[p]) for p in pids_all])

# ---- sample problems for candidate-level distributions ----
sample = random.sample(pids_all, min(N_SAMPLE, len(pids_all)))
def pct(a): a = np.asarray(a, float); return {"mean": round(float(a.mean()), 1), "median": float(np.median(a)),
    "p75": round(float(np.percentile(a, 75)), 1), "p90": round(float(np.percentile(a, 90)), 1),
    "p95": round(float(np.percentile(a, 95)), 1), "max": round(float(a.max()), 1)}

out_tok = {L: [] for L in (0, 1, 2)}     # full output tokens (existing Qwen candidates)
code_tok = {L: [] for L in (0, 1, 2)}    # code-only tokens
parent_tok = {L: [] for L in (0, 1, 2)}  # strip_think parent tokens (what gets embedded next loop)
capped = {L: 0 for L in (0, 1, 2)}; ncand = {L: 0 for L in (0, 1, 2)}
for p in sample:
    for L in (0, 1, 2):
        for c in cand[p][L]:
            t = ntok(c); out_tok[L].append(t); ncand[L] += 1
            if t >= int(0.98 * CAP): capped[L] += 1
            code_tok[L].append(ntok(extract_code(c)))
            parent_tok[L].append(ntok(strip_think_blocks(c)))

# ---- input tokens per call ----
inp0, inp1, inp2 = [], [], []
p0comp = {"problem": [], "overhead": []}; p1comp = {"problem": [], "parents": [], "overhead": []}
for p in sample:
    q = allq[p]; qt = ntok(q)
    inp0.append(qt + CHAT_OH)                                   # loop0: raw problem + chat scaffolding
    p0comp["problem"].append(qt); p0comp["overhead"].append(CHAT_OH)
    for L, store, comp in [(1, inp1, p1comp), (2, inp2, p1comp)]:
        parents = [strip_think_blocks(c) for c in random.sample(cand[p][L - 1], min(K_PARENTS, len(cand[p][L - 1])))]
        full = aggregate_prompt(q, parents); t = ntok(full) + CHAT_OH
        store.append(t)
        par_tok = sum(ntok(x) for x in parents)
        comp["problem"].append(qt); comp["parents"].append(par_tok)
        comp["overhead"].append(t - qt - par_tok)

# ---- write token_stats_by_generation_call.csv (INPUT stats by loop + component) ----
with open(f"{OUT}/tables/token_stats_by_generation_call.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["loop", "component", "mean", "median", "p75", "p90", "p95", "max", "n_calls_denominator"])
    def row(L, comp, arr): d = pct(arr); w.writerow([L, comp, d["mean"], d["median"], d["p75"], d["p90"], d["p95"], d["max"], len(arr)])
    row(0, "input_total", inp0); row(0, "input_problem", p0comp["problem"])
    row(1, "input_total", inp1); row(1, "input_problem", p1comp["problem"][:len(inp1)]); row(1, "input_parents(4)", p1comp["parents"][:len(inp1)])
    row(2, "input_total", inp2)
    row(0, "problem_statement_tokens", prob_tok)

# ---- write output_token_stats_by_loop.csv ----
gs = json.load(open("/mnt/cpfs/yangboxue/opsd/oss_density_work/gen_speed_results.json"))["results"]
with open(f"{OUT}/tables/output_token_stats_by_loop.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["source", "loop", "mean", "median", "p75", "p90", "p95", "max", "cap_hit_rate", "n_denominator"])
    for L in (0, 1, 2):
        d = pct(out_tok[L]); dc = pct(code_tok[L])
        w.writerow(["existing_Qwen3-4B_full_output", L, d["mean"], d["median"], d["p75"], d["p90"], d["p95"], d["max"],
                    round(capped[L] / ncand[L], 3), ncand[L]])
        w.writerow(["existing_Qwen3-4B_code_only", L, dc["mean"], dc["median"], dc["p75"], dc["p90"], dc["p95"], dc["max"], "", ncand[L]])
    for eff in ("low", "medium", "high"):
        w.writerow([f"gpt-oss-120B_measured_effort={eff}", "0(direct-gen)", gs[eff]["mean_tok_per_cand"], "", "", "", "", "",
                    round(gs[eff]["capped_pct"] / 100, 3), gs[eff]["n"]])

summary = {
    "config": {"population": 16, "k_parents": K_PARENTS, "loops_available": [0, 1, 2], "max_tokens_existing": CAP,
               "temperature": 1.0, "recombination": "livecodebench-aggregate", "strip_think": True,
               "tokenizer": "gpt-oss-120b", "chat_overhead_tokens_assumed": CHAT_OH},
    "n_problems": n_prob, "generation_calls_total": n_prob * 16 * 3, "sample_problems": len(sample),
    "problem_statement_tokens": pct(prob_tok),
    "input_tokens": {"loop0": pct(inp0), "loop1": pct(inp1), "loop2": pct(inp2)},
    "input_components": {"loop0_problem": pct(p0comp["problem"]),
                         "loop1_2_parents_sum(4)": pct(p1comp["parents"]), "loop1_2_overhead": pct(p1comp["overhead"])},
    "output_tokens_existing_Qwen": {f"loop{L}": pct(out_tok[L]) | {"cap_hit_rate": round(capped[L] / ncand[L], 3)} for L in (0, 1, 2)},
    "output_tokens_code_only_existing": {f"loop{L}": pct(code_tok[L]) for L in (0, 1, 2)},
    "parent_tokens_stripped_existing": {f"loop{L}": pct(parent_tok[L]) for L in (0, 1, 2)},
    "gpt_oss_measured_output": {eff: gs[eff]["mean_tok_per_cand"] for eff in ("low", "medium", "high")},
    "gpt_oss_measured_cap_rate": {eff: gs[eff]["capped_pct"] / 100 for eff in ("low", "medium", "high")},
}
json.dump(summary, open(f"{OUT}/token_stats_summary.json", "w"), indent=2)
print(json.dumps(summary, indent=2))
