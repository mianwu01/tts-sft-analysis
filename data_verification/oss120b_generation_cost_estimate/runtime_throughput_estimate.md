# Runtime / throughput estimate — gpt-oss-120B SE generation

All figures `RESULT-DEPENDENT` on measured token lengths (`token_stats_summary.json`) and the measured single-node
gpt-oss-120B decode rate (~1,800 output tok/s, TP4, from `oss_density_work/gen_speed_results.json`). No inference run here.

## Generation-call volume (full 44k)

| protocol | calls (44k × 3 loops × candidates) |
|---|---|
| 44k × 16 candidates | **2,112,000** |
| 44k × 8 candidates | **1,056,000** |

## Required rate to finish

Output tokens are the denominator that matters (decode-bound — see below). Using gpt-oss **medium** output (3,493 tok/cand):
44k×16 = **7.38B output tokens**; 44k×8 = 3.69B. (low-effort 2,268 tok/cand → 4.79B / 2.40B.)

| finish in | gens/sec (44k×16) | gens/sec (44k×8) | output tok/s (44k×16, medium) |
|---|---|---|---|
| 1 day | 24.4 | 12.2 | ~85,000 |
| 3 days | 8.2 | 4.1 | ~28,500 |
| 1 week | 3.5 | 1.8 | ~12,200 |
| 1 month | 0.8 | 0.4 | ~2,850 |

## Local GPU feasibility

One gpt-oss-120B node (TP4) sustains **~1,800 output tok/s** (measured, concurrency 64). Time for the **full 44k**:

| protocol / output | one node | 3 nodes |
|---|---|---|
| 44k×16, medium (7.38B out) | **~47 days** | ~16 days |
| 44k×16, low (4.79B out) | **~31 days (~1 month)** | ~10 days |
| 44k×8, medium (3.69B out) | ~24 days | ~8 days |
| 44k×8, low (2.40B out) | ~15 days | ~5 days |

**So a single local node needs roughly a month for one 44k×16 run** (and this box is a *shared* node — GPUs 4–7 are
other tenants, so sustained solo throughput is not guaranteed). 8-candidate or low-effort halves it; multiple nodes
divide it further.

## Why hosted inference still helps even with GPU access

- **Wall-clock:** a hosted endpoint parallelizes to hundreds–thousands of concurrent requests → it can hit the
  ~85k tok/s "1-day" line that one local node (~1,800 tok/s) reaches only in ~1 month. It turns a month into ~a day.
- **Reproducibility & no babysitting:** this box silently restarts pods (wipes the stack) and shares GPUs with other
  tenants; a hosted run isn't exposed to that.
- **Frees local GPUs** for training/eval while generation runs elsewhere.
- **Batch tiers** (if the provider offers ~50%-off asynchronous batch) roughly halve cost when latency-tolerant — SE
  generation is throughput-, not latency-sensitive.

## Batching implications
- **loop0 is embarrassingly parallel** (independent samples) — max batch width, and it is a **reusable one-time asset**
  (see cost report): generate once, reuse for other experiments.
- **loop1/loop2** need a problem's previous-loop population finished first, but across the 44k problems they are fully
  parallel, so high concurrency holds throughout.

## Expected bottleneck: output decode, not input prefill
- Output tokens (4.79–7.38B) exceed input (3.89B), and **decode is ~10–50× slower per token than prefill**, so the run
  is **decode-bound**. The lever is *output length* (reasoning effort) and *parallel decode width* (hosted wins).
- Input prefill is non-trivial only for loop1/2 (each call re-reads the problem + 4 parent solutions ≈ 2,300–2,700
  tok), but prefill batches cheaply. **Prompt-caching the shared problem statement across a problem's 16 candidates
  would cut input further** (not assumed in the cost table — conservative).
