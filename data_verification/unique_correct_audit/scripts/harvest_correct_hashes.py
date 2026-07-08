#!/usr/bin/env python3
"""Unique-correct audit: harvest, per (problem, loop), the SET of exact and canonical
hashes of the ORACLE-correct candidates among the 16, so we can distinguish true diversity
from raw correct-candidate density (copy amplification).

Method / independence:
  * Oracle correctness is taken ONLY from the append-only full-test grading cache
    outputs/grading_cache/se16.jsonl (cache-only; NO code is executed here). A candidate is
    "correct" iff extract_code(cand) grades passed==True. This is the SAME oracle used by the
    existing recompute (recompute_se16_counts.py) and matches the repo frontier CSV (0 diffs).
  * Dedup is applied ONLY to already-correct candidates, so oracle correctness stays fully
    separate from candidate-level diversity.

Two normalizations (documented, conservative — NEITHER claims semantic equivalence):
  exact_norm     : normalize line endings (\\r\\n,\\r -> \\n); strip trailing whitespace per
                   line; strip leading/trailing blank lines. Indentation, blank lines in the
                   middle, comments and all code content are PRESERVED. -> "exact" dedup.
  canonical_norm : Python-tokenizer canonicalization. Drop COMMENT tokens and blank-line NL
                   tokens; normalize all inter-token whitespace; but KEEP token identity,
                   string/number literals verbatim, and INDENT/DEDENT/NEWLINE structural
                   markers so block structure & statement boundaries are preserved. Variables
                   are NOT renamed. If tokenize() fails (syntactically broken text), fall back
                   to a naive comment strip + whitespace collapse and TAG the candidate
                   canon_method='fallback' so the limitation is auditable.
  Limitation: canonical dedup still treats alpha-renamed / reordered but equivalent programs
  as DISTINCT (conservative: it can only OVER-count uniqueness, never invent duplicates).

Outputs (JSON, consumed by analyze_unique_correct.py):
  unique_correct_audit/per_problem_hashes.json
"""
import io
import json
import os
import sys
import tokenize
from collections import defaultdict

REPO = "/mnt/cpfs/yangboxue/opsd/TTS/tts-sft"
OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/unique_correct_audit"
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.chdir(REPO)

from score_diversify_ab import extract_code  # noqa: E402  (repo's own extractor)
from lcb_grading import cache_key            # noqa: E402  (repo's own cache-key)

HARNESS = os.path.join(REPO, "scripts", "lcb_exec_harness.py")
SE16 = "outputs/openthoughts114k_codeforces_full_datagen/se16"
PC = "outputs/openthoughts114k_codeforces_full_datagen/problem_classes"
SHARDS = ["sh0", "sh1", "sh2", "sh3", "sh4", "sh7", "sh8",
          "redo_sh0", "redo_sh1", "redo_sh2", "redo_sh3", "redo_sh4", "redo_sh5"]
LOOPS = (0, 1, 2)  # loop3 is partial (only 486 problems, 2868 cache misses) -> excluded here.

_FENCE_PREFIXES = ("```",)


def strip_fences(code):
    """Remove any stray markdown fence lines (extract_code usually strips these already)."""
    lines = [ln for ln in code.split("\n") if not ln.strip().startswith(_FENCE_PREFIXES)]
    return "\n".join(lines)


def exact_norm(code):
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in code.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _fallback_canon(code):
    """Naive: drop full-line and inline # comments (may clip a # inside a string literal --
    documented limitation, tagged 'fallback'), then collapse all whitespace."""
    out = []
    for ln in code.split("\n"):
        h = ln.find("#")
        if h != -1:
            ln = ln[:h]
        out.append(ln)
    import re
    return re.sub(r"\s+", " ", "\n".join(out)).strip()


def canonical_norm(code):
    """Return (canon_string, method). See module docstring for the exact policy."""
    code = strip_fences(code.replace("\r\n", "\n").replace("\r", "\n"))
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except Exception:
        return _fallback_canon(code), "fallback"
    parts = []
    for tok in toks:
        t = tok.type
        if t in (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER):
            continue  # comments, blank-line NLs, and stream markers carry no logic
        if t == tokenize.NEWLINE:
            parts.append("⏎")   # logical statement boundary
        elif t == tokenize.INDENT:
            parts.append("→")   # block open
        elif t == tokenize.DEDENT:
            parts.append("←")   # block close
        else:
            parts.append(tok.string)  # NAME/OP/STRING/NUMBER kept verbatim (no renaming)
    return " ".join(parts), "tokenize"


def load_pool():
    pool = {}
    for line in open("data/openthoughts114k_codeforces_stdin_clean.jsonl"):
        r = json.loads(line)
        s = r["test_cases"]
        tj = s if isinstance(s, str) else json.dumps(s)
        t = json.loads(tj)
        pool[r["seed_id"]] = (tj, float(t.get("time_limit") or 6.0))
    return pool


def load_cache(path):
    d = {}
    for line in open(path):
        try:
            r = json.loads(line)
            d[r["k"]] = r["v"]
        except Exception:
            continue
    return d


def main():
    import glob
    import re
    pool = load_pool()
    cache = load_cache("outputs/grading_cache/se16.jsonl")
    print(f"[cache] se16.jsonl entries: {len(cache)}", flush=True)

    # pid -> loop -> record
    rec = defaultdict(dict)
    fallback_total = 0
    for sh in SHARDS:
        root = f"{SE16}/{sh}"
        ids = [json.loads(l)["id"] for l in open(f"{root}/out.jsonl")]
        rn = re.sub(r"_loop0\.json$", "", os.path.basename(glob.glob(f"{root}/ck/*_loop0.json")[0]))
        for loop in LOOPS:
            ck = f"{root}/ck/{rn}_loop{loop}.json"
            if not os.path.exists(ck):
                continue
            probs = json.load(open(ck)).get("problems", [])
            for i, prob in enumerate(probs):
                if i >= len(ids):
                    break
                pid = ids[i]
                tj, tl = pool[pid]
                cands = prob.get("candidates") or []
                raw = 0
                miss = nocode = 0
                exact_hashes, canon_hashes, canon_codes = [], [], []
                fb = 0
                for cand in cands:
                    code = extract_code(cand)
                    if not code:
                        nocode += 1
                        continue
                    v = cache.get(cache_key(HARNESS, code, tj, tl))
                    if v is None:
                        miss += 1
                        continue
                    if not v.get("passed"):
                        continue
                    raw += 1
                    exact_hashes.append(exact_norm(code))
                    cn, method = canonical_norm(code)
                    if method == "fallback":
                        fb += 1
                    canon_hashes.append(cn)
                    canon_codes.append(code)
                fallback_total += fb
                rec[pid][loop] = {
                    "ncand": len(cands),
                    "raw_correct": raw,
                    "miss": miss,
                    "nocode": nocode,
                    "fallback_canon": fb,
                    "exact_hashes": exact_hashes,   # list, length == raw
                    "canon_hashes": canon_hashes,   # list, length == raw
                    "correct_codes": canon_codes,   # raw extracted code of correct cands (for near-dup)
                }
        print(f"[shard] {sh}: {len(ids)} problems", flush=True)

    # problem class ref (oracle-independent provenance label from pop-8 pass16)
    p16 = json.load(open(f"{PC}/pass16_by_id.json"))
    imp = set(x.strip() for x in open(f"{PC}/impossible_ids.txt") if x.strip())
    classes = {}
    for pid in rec:
        v = p16.get(pid)
        classes[pid] = ("unknown" if v is None else
                        ("saturated" if v >= 16 else
                         ("impossible" if (pid in imp or v == 0) else "informative")))

    payload = {
        "meta": {
            "n_problems": len(rec),
            "loops": list(LOOPS),
            "cache": "outputs/grading_cache/se16.jsonl",
            "pool": "data/openthoughts114k_codeforces_stdin_clean.jsonl",
            "checkpoints": f"{SE16}/<shard>/ck/*_loop{{0,1,2}}.json",
            "shards": SHARDS,
            "fallback_canon_candidates": fallback_total,
        },
        "classes": classes,
        "problems": {pid: rec[pid] for pid in rec},
    }
    os.makedirs(OUT, exist_ok=True)
    json.dump(payload, open(f"{OUT}/per_problem_hashes.json", "w"))
    # sanity vs existing recompute
    tot_raw = {L: sum(rec[p][L]["raw_correct"] for p in rec if L in rec[p]) for L in LOOPS}
    tot_miss = {L: sum(rec[p][L]["miss"] for p in rec if L in rec[p]) for L in LOOPS}
    print(json.dumps({"n_problems": len(rec), "raw_correct_by_loop": tot_raw,
                      "cache_miss_by_loop": tot_miss,
                      "fallback_canon_candidates": fallback_total}, indent=2))


if __name__ == "__main__":
    main()
