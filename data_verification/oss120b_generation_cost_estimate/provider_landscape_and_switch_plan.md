# Qwen3-4B → gpt-oss-120b switch: provider landscape, real-price costs, acceleration levers, and alternatives

**Date:** 2026-07-08.
**Extends:** `oss120b_generation_cost_estimate.md` (measured token basis) and `runtime_throughput_estimate.md` (wall-clock basis).
Those docs priced the run with *illustrative* $/M brackets; this doc replaces the brackets with **actual published provider prices** (checked 2026-07), adds the **batch-tier discounts**, evaluates **acceleration options for staying on Qwen3-4B**, and lists **alternative models** with the migration and science trade-offs of each.

---

## 1. Why the Qwen3-4B rollout is slow (recap, measured)

The run is **decode-bound on reasoning tokens**, not compute-bound on model size:

- Qwen3-4B emits **~23.4k–31.1k output tokens per candidate** (mean, by loop), ~99% of it `<think>` reasoning; final code is only ~150–250 tokens (`token_stats_summary.json`).
- **33.5% of loop0 candidates hit the 40,960 cap** (19.7% loop1, 11.7% loop2) — the known Qwen3-thinking failure mode of not closing the think block. Capped candidates are auto-fails and contribute *empty parents* to recombination.
- gpt-oss-120b measured on the same problems: **2,268 (low) / 3,493 (medium) tok/candidate, 0% cap-hit** — ~7–13× less decode per candidate. Despite being 30× larger nominally, it is MoE (~5.1B active params), so per-token speed is in the same class as a small dense model.

So the slowness has two independent fixes: **shorter outputs** (change model, or cap Qwen's thinking) and **wider parallel decode** (hosted endpoints). Switching to hosted gpt-oss-120b does both at once.

One science bonus of the switch: with 0% cap-hits, the hard-zero measurement gets **cleaner** — under Qwen3-4B, some "hard-zero" problems and some loop1/loop2 "discoveries" may partly be truncation artifacts (a candidate that finally finished within the cap), a confound that disappears with a concise model.

---

## 2. Hosted gpt-oss-120b: provider landscape (2026-07)

All prices $/M tokens, on-demand tier; all providers below are OpenAI-compatible.

| Provider | Input | Output | Batch tier | Speed notes |
|---|---|---|---|---|
| **DeepInfra** | ~$0.04 | ~$0.19 | **50% off**, ≤24h window, ≤1,000 req/call | cheapest; moderate speed |
| **Groq** | $0.15 | $0.60 | **50% off** ($0.075/$0.30), 24h–7d window, **doesn't consume standard rate limits** | very fast; prompt caching discount (doesn't stack with batch) |
| **Cerebras** | ~$0.25–0.35 | ~$0.69–0.75 | — (not advertised) | fastest per-stream (~2,000 tok/s sustained) |
| **Fireworks** | mid | mid | **50% off** batch | ~675 tok/s |
| **Together** | mid | mid | **up to 50% off**, 24h best-effort, ≤50k req & ≤30B tokens/batch | also offers fine-tuning (relevant for the SFT step later) |
| OpenRouter | varies | varies | — | aggregator; useful for failover, prices vary up to ~7× across its providers |

Notes:
- SE generation is **throughput-, not latency-sensitive** → the batch tiers are the natural fit; effectively the whole run costs half.
- **Groq batch** is attractive operationally: batch jobs don't touch standard rate limits, so a 44k-scale run doesn't require a rate-limit negotiation.
- **Must-verify in the 1k calibration run:** (a) the endpoint returns the **reasoning/analysis channel** (`reasoning_content` or equivalent) if we want traces for process-FT/distillation — not all providers expose it, especially in batch mode; (b) code-fence compliance of the `final` channel under our prompts (locally measured: 100% at low/medium effort); (c) whether `seed` is honored (usually not → log everything, treat runs as non-reproducible-by-seed).

---

## 3. Real-price cost for a 5-total-loop run (loop0 + 4 evolution loops)

Token basis = measured means from `tables/extrapolated_generation_tokens.csv` (mean input assumption), extended from 3 to 5 loops:
per loop at 44k×16 = 704k calls: output 2.459B (medium) / 1.597B (low); input 0.368B (loop0) or ~1.76B (evolution loop).
**5-loop 44k×16 totals: input ≈ 7.4B; output ≈ 12.3B (medium) / 8.0B (low).**

| Scenario (5 loops, medium effort) | DeepInfra | DeepInfra batch | Groq | Groq batch | Cerebras |
|---|---|---|---|---|---|
| **44k × 16** | ~$2.6k | **~$1.3k** | ~$8.5k | **~$4.2k** | ~$11.8k |
| **44k × 8** | ~$1.3k | ~$0.7k | ~$4.2k | ~$2.1k | ~$5.9k |
| **8,124 (actual assembled cf+cc pool) × 16** | ~$490 | **~$250** | ~$1.6k | ~$780 | ~$2.2k |
| **5k pilot × 16** | ~$300 | **~$150** | ~$1.0k | ~$480 | ~$1.3k |
| **1k calibration × 16** | ~$60 | ~$30 | ~$190 | ~$100 | ~$270 |

(Low effort ≈ 0.65–0.7× of these; p75/p90 input assumptions add ~10–25%.)

Takeaways vs. the earlier parametric estimate:
- The **$3k–$15k band quoted to Sewon for 5-loop 44k×16 is safe** — at real prices it lands at **~$1.3k–$8.5k on-demand** and **~$0.7k–$4.2k with a batch tier**, i.e. at or below the bottom of the quoted band.
- The **actually-assembled pool is 8,124 problems**, not 44k — a full 5-loop 16-candidate pass over everything we currently have is only **a few hundred dollars** on the cheap providers. 44k is the aspirational scale and still fits comfortably in a monthly budget with room for 2–3 prompt-variant reruns (loop0 reused).
- Wall-clock: batch windows are 24h–7d; interactive tiers at high concurrency reach the ~1-day line from `runtime_throughput_estimate.md`. Either way the binding constraint is budget, not time — consistent with the "one-month budget window, ~days of runtime" message.

---

## 4. Acceleration options if we *stayed* on Qwen3-4B (and why they cap out)

| Lever | Expected gain | Cost/risk |
|---|---|---|
| **vLLM `reasoning_budget`** (now upstream: vllm PR #37112) — force-close `<think>` after N tokens (e.g. 8k) | ~3–4× less decode; kills the 33% cap-hit pathology | Changes the output distribution → correct-density may shift; needs a ~200-problem ablation (loop0 pass@16 at budgets ∞/16k/8k/4k) before trusting buckets |
| Newer checkpoint: **Qwen3-4B-Thinking-2507 / -Instruct-2507** | Instruct (non-thinking) is ~10× shorter; both are stronger than the original 4B | It's *also* a model switch — old loop0–2 artifacts stop being the same lineage anyway |
| Serving tweaks: FP8 KV/weights, data-parallel replicas, higher concurrency, n=16-per-request prefix sharing | ~1.5–2× | Engineering time on a shared, unreliable node ("silently restarts pods") |

Bottom line: the only Qwen-side lever comparable to the model switch is the thinking-budget cap, and it still leaves us on the weakest model with a distribution-shift caveat. If any model change is acceptable, switching beats tuning.

---

## 5. Alternative models (beyond gpt-oss-120b)

| Model | Rollout speed / cost | Migration effort | Fine-tunable by us? | Notes |
|---|---|---|---|---|
| **gpt-oss-120b** (plan of record) | 2.3–3.5k tok/cand; cheapest strong option hosted | Harmony channels, drop `top_k`, add `reasoning_effort` | Impractical at our compute | Strongest (LiveCodeBench ≈ 70; Codeforces Elo ≈ 2620 w/ tools per model card) |
| **gpt-oss-20b** | ~2× cheaper hosted (DeepInfra ~$0.04 in; Groq ~893 tok/s); self-hostable on **one** GPU | Same harmony migration as 120b — zero extra work | **Yes** — realistic SFT/RL target | Close to 120b on competitive programming (model card); the natural **"trainable self-model"** |
| **Qwen3-30B-A3B (-Instruct-2507 / -Thinking-2507)** | MoE, ~3.3B active → per-token speed ≈ 4B dense; hosted ~$0.12/$0.50 | **Near zero** — same family, same `<think>`/`strip_think`/`top_k` pipeline | Yes (30B, MoE FT is doable; Together offers FT) | Big quality jump over 4B; Thinking variant may share the verbosity issue → pair with reasoning-budget cap or use Instruct |
| Qwen3-4B + reasoning budget (§4) | ~3–4× faster than today | Minimal | Yes (easiest) | Keeps existing lineage most comparable; weakest model |

---

## 6. Science caveats of the switch (flag these before the run)

1. **Buckets are model-relative.** gpt-oss-120b is far stronger on competitive programming than Qwen3-4B; on the same pool, loop0 pass@16 shifts right, the 0-bucket shrinks, and 9–16 buckets inflate. The dynamic-bucket / densification story must be **re-established under the new model**, and the pool may need harder problems (or larger scale — one motivation for 44k) to keep a usable hard-zero frontier. The 1k calibration run should report the loop0 bucket histogram *first*, before committing to the pilot.
2. **The "same-model self-evolution" framing (Harman) constrains the choice.** If SE generation runs on gpt-oss-120b but the downstream SFT target is a small model, the project *becomes* strong-teacher distillation — exactly the framing we're trying to move past. Preserving the framing means the SE model and the trained model should coincide (or the teacher should be ~as weak as the student). Practical resolution: use **gpt-oss-120b for the scale/science run** (does repeated evolution densify?), and run **at least the 5k pilot on the intended training target as well** (gpt-oss-20b or Qwen3-30B-A3B) so the SFT/RL story stays same-model. Decide the training target before the pilot, not after.
3. **Old vs new lineage.** Loop0 reuse only holds *within* a model+prompt lineage. The existing Qwen loop0–2 artifacts stay valid for the dynamic-bucket analysis already shipped, but nothing carries over to the gpt-oss lineage; the new run pays a fresh loop0 (~$0.3–1.5k at 44k×16, then reusable across variants).
4. **Reasoning-effort setting.** Use **medium** as default: high emits 11.3k tok/cand with **29.7% cap-hit at 16,384** (reintroducing the truncation pathology at 3× the cost), and external evals repeatedly find medium ≈ or > high on accuracy. Low is fine for calibration sweeps. Set `max_tokens` ≈ 16k for low/medium.
5. **Reproducibility.** Hosted endpoints generally don't honor `seed`; mitigate by logging full request/response and pinning provider+model revision for a given run.

---

## 7. Recommended sequence

1. **Pick providers**: DeepInfra batch (cheapest) as primary; Groq batch as the fast/no-rate-limit alternative; Cerebras or Fireworks interactive for small calibration jobs. All OpenAI-compatible → one client, swappable base URL.
2. **Port the pipeline** (edits land in `mianwu01/tts-sft`, not this repo): read `reasoning_content`/final channel instead of `strip_think(<think>)`; drop `top_k`; add `reasoning_effort`; `max_tokens` 40,960→16,384; code extraction from the final channel; a batch-file submit/poll wrapper.
3. **1k calibration (~$30–100 batch)**: loop0 only, medium effort → loop0 bucket histogram (science go/no-go), reasoning-channel availability, code-fence rate, token stats vs. the local benchmark.
4. **5k × 16 × 5-loop pilot (~$150–500 batch)** on gpt-oss-120b; in parallel, same pilot on the chosen training target (gpt-oss-20b or Qwen3-30B-A3B) if the SFT story is same-model.
5. **Re-check the dynamic-bucket story at pilot scale** (0→1 discovery vs. densification; the n=18 strict-comparison gap is exactly what 5 loops + more problems fixes), then decide 8k-pool full pass vs. 44k scale and the SFT data build.

---

### Sources (external prices/claims, checked 2026-07)

- Groq gpt-oss-120b pricing & batch: [groq.com/pricing](https://groq.com/pricing), [Groq Batch API docs](https://console.groq.com/docs/batch), [GPT-OSS improvements blog](https://groq.com/blog/gpt-oss-improvements-prompt-caching-and-lower-pricing)
- Provider price spread: [pricepertoken.com gpt-oss-120b](https://pricepertoken.com/pricing-page/model/openai-gpt-oss-120b), [OpenRouter gpt-oss-120b](https://openrouter.ai/openai/gpt-oss-120b)
- Cerebras: [Cerebras gpt-oss blog](https://www.cerebras.ai/blog/openai-gpt-oss-120b-runs-fastest-on-cerebras), [pricing](https://www.cerebras.ai/pricing)
- DeepInfra: [deepinfra.com/pricing](https://deepinfra.com/pricing) (batch = 50% off, ≤24h)
- Together batch: [together.ai/batch-inference](https://www.together.ai/batch-inference)
- gpt-oss model card (Codeforces/LCB, effort levels): [arXiv:2508.10925](https://arxiv.org/abs/2508.10925)
- vLLM reasoning-budget: [vllm PR #37112](https://github.com/vllm-project/vllm/pull/37112), [feature issue #17887](https://github.com/vllm-project/vllm/issues/17887)
- Medium-vs-high effort accuracy: [NHS medication-safety eval, arXiv:2512.21127](https://arxiv.org/pdf/2512.21127)
- Qwen3-30B-A3B hosted pricing: [pricepertoken.com Qwen3-30B-A3B](https://pricepertoken.com/pricing-page/model/qwen-qwen3-30b-a3b)
