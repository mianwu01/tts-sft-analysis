# gpt-oss-120B SqueezeEvolve generation — cost & token estimate

**Question (Sewon):** which API do we need and what does ~a month of gpt-oss-120B **SE generation** cost — not just
short verifier judgments, but full loop0 direct generation + loop1/loop2 recombination with full solution/reasoning outputs.

**Method (no inference, no repo edits).** All token counts are measured from the **actual se16 loop0/1/2 artifacts**,
tokenized with the **gpt-oss-120B tokenizer**, reconstructing the real SE prompts. gpt-oss output length is taken from
a **direct measurement** of gpt-oss-120B on these problems (`oss_density_work/gen_speed_results.json`). Prices are
**parametric** — no endpoint pricing exists in the repo (config uses a local vLLM endpoint, `api_key: EMPTY`).

## TL;DR (`RESULT-DEPENDENT`)

- **Data denominator:** existing set = **1,093 problems × 3 loops (0/1/2) × 16 candidates = 52,464 generation calls.**
- **The output model matters ~10×.** The existing candidates were made by **Qwen3-4B**, which emits **~23k–31k
  tokens/candidate** (99% reasoning; the *code* is only ~150–250 tokens; 12–33% hit the 40,960 cap). **gpt-oss-120B is
  ~10× more concise** — **2,268 (low) / 3,493 (medium) tok/candidate, 0% capped**. Use gpt-oss numbers for the estimate;
  reproducing the verbose Qwen run verbatim would cost ~10× more in output.
- **loop0 is a reusable one-time asset** (independent base samples reused by other experiments / the reachability
  diagnostic / SFT). Prompt-variant reruns re-pay **only loop1+loop2**, not loop0 (~25–30% of a run).
- **Full 44k × 3 × 16, single run, gpt-oss medium output ≈ $1.7k–8.5k** depending on endpoint price; **8-candidate ≈
  half** ($0.8k–4.3k). Staged pilots are cheap: **1k ≈ $40–210, 5k ≈ $190–970, 10k ≈ $380–1,940.**

## Config facts (se16, `outputs/…/se16/sh0/config.yaml`)

`population: 16`, `routing.k: 4` (parents per aggregate), `loops: 2` (→ loop0/1/2), `recombination:
livecodebench-aggregate`, `strip_think: true`, `max_tokens: 40960`, `temperature: 1.0`. **loop0 prompt = the raw
problem** (SE `recomb(orig_prompt, [])` returns the query unchanged); **loop1/2 prompt = aggregate template + 4
strip_think'd parents** (`common.py:make_aggregate_prompt`). strip_think means capped/unfinished parents contribute
**empty** to recombination input.

## Measured token lengths (gpt-oss tokenizer; `token_stats_summary.json`)

**Input per call** (kept separate from output; loop0 = direct, loop1/2 = SE recombination):

| loop | type | mean | median | p75 | p90 | p95 | components |
|---|---|---|---|---|---|---|---|
| 0 | direct gen | **522** | 511 | 581 | 743 | 764 | problem (~427) + chat scaffolding (~80) |
| 1 | SE aggregate | **2,668** | 2,670 | 3,745 | 4,482 | 4,810 | problem + **4 parents (~1,869)** + template |
| 2 | SE aggregate | **2,333** | 2,056 | 3,029 | 4,210 | 4,915 | problem + 4 parents (loop1, stripped) |

**Output per candidate:**

| source | loop0 | loop1 | loop2 | cap-hit | note |
|---|---|---|---|---|---|
| existing **Qwen3-4B** (full) | 31,058 | 23,466 | 23,378 | 33/20/12% | verbose reasoning; code-only is ~150–244 tok |
| **gpt-oss-120B measured** | 2,268 / 3,493 / 11,282 (low/med/high) | (≈ same per call, assumed) | | 0/0/30% | high-effort caps at 16k → impractical |

> gpt-oss output is assumed ~constant across loops (each call emits one full reasoned solution; the Qwen data shows
> loop1/2 slightly *shorter* than loop0, so this is mildly conservative). **high effort is not usable** (30% capped).

## Current ~1k calibration budget (existing set, 52,464 calls)

| output setting | input tok | output tok | total tok | 1× cost (very-low → high price) |
|---|---|---|---|---|
| gpt-oss **low** (2,268) | 96.6M | 119.0M | 216M | ~$30 → $170 |
| gpt-oss **medium** (3,493) | 96.6M | 183.2M | 280M | **$41 → $212** |
| (reproduce verbose **Qwen**) | 96.6M | ~1.35B | ~1.45B | ~$0.3k → $1.6k |

Reruns/prompt-variants: input is fixed; **loop0 (~$14–70 of a medium run) is reusable**, so a 2×/3× variant sweep
re-pays only loop1+2.

## Extrapolation to target scale (`tables/extrapolated_generation_tokens.csv`)

Token totals (gpt-oss **medium** output, mean input), billions of tokens:

| scale | cand | calls | input | output | total | loop0 (reusable) | loop1+2 (per variant) |
|---|---|---|---|---|---|---|---|
| 1k | 16 | 52k | 0.10B | 0.18B | 0.28B | 0.07B | 0.21B |
| 5k | 16 | 240k | 0.44B | 0.84B | 1.28B | 0.32B | 0.96B |
| 10k | 16 | 480k | 0.88B | 1.68B | 2.56B | 0.64B | 1.92B |
| **44k** | **16** | **2.11M** | **3.89B** | **7.38B** | **11.3B** | **2.83B** | **8.44B** |
| **44k** | **8** | **1.06M** | **1.94B** | **3.69B** | **5.6B** | **1.42B** | **4.22B** |

## Dollar cost table (parametric — plug in the real endpoint quote; `cost_table.csv`)

Prices are **illustrative brackets for open-weight gpt-oss-120B hosting**, NOT quoted from a provider (none found in
repo). Output = gpt-oss **medium** (3,493/cand); for **low** effort multiply total ≈ ×0.7 (output only).
Variant columns **reuse loop0** (loop0 once + loop1+2 × N).

| scenario | in $/M | out $/M | 1k×16 | 5k×16 | 10k×16 | **44k×16** | **44k×8** | 44k×16 ×2 var | 44k×16 ×3 var |
|---|---|---|---|---|---|---|---|---|---|
| very-low | 0.05 | 0.20 | $42 | $190 | $380 | **$1,670** | **$835** | $2,830 | $3,989 |
| low | 0.10 | 0.40 | $83 | $380 | $759 | **$3,340** | **$1,670** | $5,659 | $7,978 |
| medium | 0.15 | 0.60 | $124 | $569 | $1,139 | **$5,010** | **$2,505** | $8,489 | $11,968 |
| high | 0.30 | 1.00 | $212 | $971 | $1,942 | **$8,544** | **$4,272** | $14,518 | $20,492 |

**loop0-reuse economics (44k×16, medium price):** loop0 ≈ **$1,530 one-time (reusable)**; each subsequent full
SE-variant rerun adds only ≈ **$3,480** (loop1+2), not another $5,010. Input is cheap (~$0.5k of the $5k); **output
decode dominates.**

## Key assumptions (be explicit)
1. **Output basis = gpt-oss measured direct-gen** (2,268/3,493), assumed ~constant across loops. Real loop1/2 output
   could differ ±10–20%; the Qwen data suggests slightly shorter, so this is mildly conservative.
2. **Input reconstructed** from the exact SE templates + real problems/parents; chat scaffolding assumed ~80 tok/call.
3. **No prompt caching** assumed (caching the shared problem across a problem's 16 candidates would cut input further).
4. **Prices are parametric** — the four scenarios bracket plausible gpt-oss-120B hosting; substitute the actual quote.
5. 8-candidate protocol = population 8 (still k=4 parents) → **half the calls** of 16-candidate → ~half cost.
6. Distributions measured on an 80-problem sample (candidate-level) + all 1,093 (problem-level); 0 grading/cache gaps.

## Appendix (optional) — verifier-only cost, kept SEPARATE and much cheaper
The base SE run above uses `fitness: diversity` and needs **no verifier**. *If* a self-verification pass is added
(1 short judge call per candidate): input ≈ problem + 1 code (~1k tok), output ≈ ~500 tok. For 44k×16×3 = 2.11M judge
calls ≈ 2.1B in + 1.05B out ≈ **$0.3k–1.0k** at the low–medium price scenarios — i.e. **~10–20% of generation cost**,
and usually you'd verify only loop0 or a subset. **This is an add-on; it does not enter the SE-generation numbers above.**

## Created files
- `oss120b_generation_cost_estimate.md` (this), `token_stats_summary.json`, `cost_rollup.json`
- `tables/generation_call_counts.csv`, `token_stats_by_generation_call.csv`, `tables/output_token_stats_by_loop.csv`, `tables/extrapolated_generation_tokens.csv`, `cost_table.csv`
- `runtime_throughput_estimate.md`, `sewon_reply_draft.md`
- `scripts/measure_tokens.py`, `scripts/extrapolate_and_cost.py`
