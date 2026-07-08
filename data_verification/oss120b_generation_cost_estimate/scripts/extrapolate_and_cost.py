#!/usr/bin/env python3
"""Extrapolate SE-generation token budgets to 1k/5k/10k/44k (16 & 8 candidates) and produce a parametric
$ cost table. Uses measured per-loop token distributions (token_stats_summary.json) + gpt-oss-120B measured
output length. Key economics: LOOP0 IS A REUSABLE ONE-TIME ASSET (independent base samples reused by other
experiments / the reachability diagnostic / SFT) — so prompt-variant reruns re-pay ONLY loop1+loop2."""
import json, csv, os

OUT = "/mnt/cpfs/yangboxue/opsd/TTS/analysis_outputs/data_verification/oss120b_generation_cost_estimate"
S = json.load(open(f"{OUT}/token_stats_summary.json"))

# per-call INPUT tokens by loop (mean / p75 / p90) from measurement
def g(loop, q): return S["input_tokens"][loop][q]
IN = {"mean": {0: g("loop0", "mean"), 1: g("loop1", "mean"), 2: g("loop2", "mean")},
      "p75":  {0: g("loop0", "p75"),  1: g("loop1", "p75"),  2: g("loop2", "p75")},
      "p90":  {0: g("loop0", "p90"),  1: g("loop1", "p90"),  2: g("loop2", "p90")}}

# per-call OUTPUT tokens: gpt-oss-120B measured direct-gen (assume ~constant across loops; each call emits one
# full reasoned solution). low=cost-efficient, medium=quality. (Existing Qwen outputs are far longer/cap-heavy;
# reported separately as an upper bound.)
OUT_TOK = {"low": S["gpt_oss_measured_output"]["low"], "medium": S["gpt_oss_measured_output"]["medium"]}
QWEN_OUT_MEAN = (S["output_tokens_existing_Qwen"]["loop0"]["mean"] + S["output_tokens_existing_Qwen"]["loop1"]["mean"]
                 + S["output_tokens_existing_Qwen"]["loop2"]["mean"]) / 3

SCALES = [("1k", 1093), ("5k", 5000), ("10k", 10000), ("44k", 44000)]
LOOPS = (0, 1, 2)

def budget(nprob, cand, in_q, out_tok):
    """Return dict of token totals; loop0 vs loop1+2 split (loop0 reusable)."""
    inp = {L: nprob * cand * IN[in_q][L] for L in LOOPS}
    out = {L: nprob * cand * out_tok for L in LOOPS}
    calls = {L: nprob * cand for L in LOOPS}
    loop0_in, loop0_out = inp[0], out[0]
    l12_in, l12_out = inp[1] + inp[2], out[1] + out[2]
    return {"calls_total": sum(calls.values()), "calls_loop0": calls[0], "calls_l12": calls[1] + calls[2],
            "in_total": sum(inp.values()), "out_total": sum(out.values()),
            "loop0_in": loop0_in, "loop0_out": loop0_out, "l12_in": l12_in, "l12_out": l12_out,
            "in_by_loop": inp, "out_by_loop": out}

# ---- extrapolated_generation_tokens.csv ----
with open(f"{OUT}/tables/extrapolated_generation_tokens.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["scale", "candidates", "input_assumption", "output_assumption(gpt-oss)",
                "gen_calls", "input_tokens", "output_tokens", "total_tokens",
                "loop0_tokens(reusable_onetime)", "loop1+2_tokens(per_variant)"])
    for sname, nprob in SCALES:
        for cand in (16, 8):
            if sname != "44k" and cand == 8:
                continue  # 8-candidate protocol requested for 44k; 16 is the default elsewhere
            for in_q in ("mean", "p75", "p90"):
                for oeff in ("low", "medium"):
                    b = budget(nprob, cand, in_q, OUT_TOK[oeff])
                    l0 = b["loop0_in"] + b["loop0_out"]; l12 = b["l12_in"] + b["l12_out"]
                    w.writerow([sname, cand, in_q, f"{oeff}({OUT_TOK[oeff]}/cand)", b["calls_total"],
                                b["in_total"], b["out_total"], b["in_total"] + b["out_total"], l0, l12])

# ---- cost_table.csv (parametric; illustrative scenario prices, NOT quoted from a provider) ----
# NO provider pricing found in repo/config (config uses a local vLLM endpoint, api_key EMPTY). Prices below are
# ILLUSTRATIVE brackets for open-weight gpt-oss-120B hosting — plug in the real endpoint quote.
SCEN = [("very_low", 0.05, 0.20), ("low", 0.10, 0.40), ("medium", 0.15, 0.60), ("high", 0.30, 1.00)]
OUT_FOR_COST = OUT_TOK["medium"]  # base cost table at gpt-oss medium output; low ~*0.65 (see report)

def cost(b, pin, pout):
    return b["in_total"] * pin / 1e6 + b["out_total"] * pout / 1e6

def cost_split(b, pin, pout):  # (loop0 reusable, loop1+2 per-variant)
    l0 = b["loop0_in"] * pin / 1e6 + b["loop0_out"] * pout / 1e6
    l12 = b["l12_in"] * pin / 1e6 + b["l12_out"] * pout / 1e6
    return l0, l12

def variant_cost(b, pin, pout, nvar):  # loop0 once + loop1+2 x nvar (loop0 reusable)
    l0, l12 = cost_split(b, pin, pout); return l0 + nvar * l12

B = {(s, c): budget(n, c, "mean", OUT_FOR_COST) for s, n in SCALES for c in (16, 8)}
with open(f"{OUT}/cost_table.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["scenario", "input_$/M", "output_$/M",
                "1k_16cand", "5k_16cand", "10k_16cand", "44k_16cand", "44k_8cand",
                "44k_16cand_2variants(loop0_reused)", "44k_16cand_3variants(loop0_reused)"])
    for name, pin, pout in SCEN:
        w.writerow([name, pin, pout,
                    round(cost(B[("1k", 16)], pin, pout), 1), round(cost(B[("5k", 16)], pin, pout), 1),
                    round(cost(B[("10k", 16)], pin, pout), 1), round(cost(B[("44k", 16)], pin, pout), 1),
                    round(cost(B[("44k", 8)], pin, pout), 1),
                    round(variant_cost(B[("44k", 16)], pin, pout, 2), 1),
                    round(variant_cost(B[("44k", 16)], pin, pout, 3), 1)])

# rollup for the reports
def summ(b): return {"calls": b["calls_total"], "in_B": round(b["in_total"] / 1e9, 2), "out_B": round(b["out_total"] / 1e9, 2),
                     "total_B": round((b["in_total"] + b["out_total"]) / 1e9, 2),
                     "loop0_B": round((b["loop0_in"] + b["loop0_out"]) / 1e9, 2),
                     "l12_B": round((b["l12_in"] + b["l12_out"]) / 1e9, 2)}
roll = {"per_call_input_mean": IN["mean"], "gpt_oss_out_per_cand": OUT_TOK, "qwen_existing_out_mean_percand": round(QWEN_OUT_MEAN),
        "budgets_medium_out": {f"{s}_{c}": summ(budget(n, c, "mean", OUT_TOK["medium"])) for s, n in SCALES for c in (16, 8)},
        "budgets_low_out": {f"{s}_{c}": summ(budget(n, c, "mean", OUT_TOK["low"])) for s, n in SCALES for c in (16, 8)},
        "cost_scenarios": {name: {"in_per_M": pin, "out_per_M": pout,
                                  "44k_16_1x": round(cost(B[("44k", 16)], pin, pout)),
                                  "44k_8_1x": round(cost(B[("44k", 8)], pin, pout)),
                                  "44k_16_3variants": round(variant_cost(B[("44k", 16)], pin, pout, 3)),
                                  "1k_16": round(cost(B[("1k", 16)], pin, pout), 1),
                                  "5k_16": round(cost(B[("5k", 16)], pin, pout)),
                                  "10k_16": round(cost(B[("10k", 16)], pin, pout))} for name, pin, pout in SCEN}}
json.dump(roll, open(f"{OUT}/cost_rollup.json", "w"), indent=2)
print(json.dumps(roll, indent=2))
