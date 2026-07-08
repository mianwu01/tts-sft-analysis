# Slack reply draft — for Sewon

---

**Which API + ~1-month cost for gpt-oss-120B SE generation** (numbers from our actual loop0–loop2 data, tokenized with the gpt-oss tokenizer; full writeup in `analysis_outputs/data_verification/oss120b_generation_cost_estimate/`):

**Which API:** a hosted **gpt-oss-120B generation endpoint** — ideally **OpenAI-compatible + batch-friendly** (a cheap async batch tier helps a lot). This is for **full SE generation** (loop0 direct + loop1/2 recombination with full reasoning outputs), *not* short verifier judgments — output tokens dominate the bill. Confirm the endpoint returns reasoning traces if we want them for distillation.

**We have some GPU access, but hosted still wins for 44k:** one local 120B node (~1,800 tok/s) takes **~1 month** for a single 44k×16 run; a hosted endpoint parallelizes to ~a day, is reproducible, and frees our GPUs. (This box is also shared + restarts pods, so local isn't reliable at scale.)

**Cost (gpt-oss ≈ 3.5k output tok/candidate — ~10× more concise than our Qwen3-4B data; prices below are illustrative brackets, plug in the real quote):**

| run | calls | cost range (very-low → high price) |
|---|---|---|
| **current ~1k calibration** (16 cand) | 52k | **$40 – $210** |
| **5k pilot** | 240k | $190 – $970 |
| **10k pilot** | 480k | $380 – $1,940 |
| **full 44k × 16 cand** | 2.1M | **$1,700 – $8,500** |
| **full 44k × 8 cand** | 1.1M | **$850 – $4,300** |

**Two things that cut cost a lot:**
- **loop0 is a reusable one-time asset** (the independent base samples — reused by the reachability diagnostic, other SE variants, and SFT). So a **prompt-variant sweep re-pays only loop1+2**, not loop0: e.g. 3 variants at 44k×16 ≈ $4k–20k (not 3× the full run).
- **8 candidates ≈ half of 16** with little expected loss — good default for the big run.

**Staged plan I'd propose:** **1k (calibrate prompts, ~$40–210) → 5k/10k pilot (~$0.2–2k) → 44k** (8-cand first, ~$0.8–4.3k; go 16-cand only if the pilot shows it's worth it). loop0 from each stage carries forward.

**Bottom line for "about a month":** budget on the order of **$1–5k for one full 44k run** (endpoint-price dependent), plus ~half that per extra prompt-variant sweep. I'll firm up the exact number once we pick an endpoint and its price.

---

*(Ranges reflect endpoint pricing uncertainty, not measurement error — token counts are measured. Verifier/self-verification, if we add it, is a separate ~10–20% add-on, not included above.)*
