# DeepSeek-V4-Flash-0731 on vllm-node-b12x: latency of long tool-call requests grows with uptime (3 s -> 20 s -> timeout for the same request) while short requests stay fast. Standard vllm-node: flat.

Companion issue: the same build also ignores "reply with the filename only" in these requests (separate ticket).

## Environment

- 2x DGX Spark (GB10 / SM121), tensor-parallel 2
- Affected: image `vllm-node-b12x` (built with `--exp-b12x`), recipe `recipes/deepseek-v4-flash-0731.yaml`
  (b12x MoE/linear backends, `B12X_MLA_SPARSE`, `VLLM_USE_V2_MODEL_RUNNER=1`, `VLLM_USE_FLASHINFER_SAMPLER=1`,
  `--load-format instanttensor`, prefix caching on, DSpark spec-decode 5 tokens probabilistic).
  Built from the 2026-08-15 recipe: `EXP_B12X_VLLM_REF=dev/infernal-invocation`, b12x master. Image digest: ___
  Not yet tested: the 2026-09-03 recipe (`dev/jovian-judgement`, `--attention-backend B12X` instead of
  `B12X_MLA_SPARSE`) — see Notes.
- Working: image `vllm-node` (standard), same recipe shape with `--speculative-config` removed. Image tag/digest: ___ , vLLM version: ___
- Model: `deepseek-ai/DeepSeek-V4-Flash-0731`, `--kv-cache-dtype fp8`, `max-num-seqs 8`

## What happens

Chat-completions requests from a tool-using agent (system prompt + 2 tools + tool results, 10-30k tokens).
The same byte-identical request, sent repeatedly to one b12x server instance:

| When | Latency |
|---|---|
| shortly after start | 3.0 s |
| after ~50 more large requests | 20.5 s |
| after ~60 more | timeout (> 240 s) |

During live agent runs (~8 concurrent requests) individual calls reach 480-810 s. Short requests sent in between
stay at 0.5-3 s throughout, and the server never crashes or returns errors — it degrades specifically on these
long tool-call contexts. Reproduces with DSpark disabled and with `--max-num-seqs 1`.

**Expected** (observed on standard `vllm-node`, same weights): the same request repeated 3 times takes
1.7 s / 1.7 s / 1.8 s; a full replay of the 47 requests stays under 40 s per call; Qwen3.6-35B-A3B on the standard
image shows no drift after 60+ large requests.

## Reproduce

Kit (stdlib Python, no keys, 47 recorded request bodies):
https://github.com/BittnerPierre/agentic-research/tree/config/207-deepseek-0731-minimal/investigations/dsv4f-0731-vllm-repro

```
python3 repro_b_latency_growth.py --base-url http://HOST:8000/v1                # same recorded request 5x, latency series
python3 repro_b_latency_growth.py --base-url http://HOST:8000/v1 --replay-all   # all 47 requests with the recorded timing
```
Affected build: `latency series: 9.1s -> 240.0s` (timeout on the second repetition already) — REPRODUCED.
Standard image: `latency series: 1.7s -> 1.7s -> 1.8s` — clean.

## Notes

- The 2026-09-03 recipe update switches to `dev/jovian-judgement`, whose same-day commits rework exactly this path:
  `83cb22a0` (B12X sparse MLA per-token cache lengths were recomputed as a fresh tensor each build, so FULL CUDA-graph
  replays read stale lengths), `341f198b` (DSpark decode/prefill split mismatch in the sparse MLA builder),
  `b60c5e39` (DSpark decode metadata sizing), `d662a1b0` (new B12X sparse MLA/DSA backends). Those commits report
  warmup crashes; the behavior here is silent (wrong output, slowdown) on the older ref. Rerunning the kit on an image
  built from the new recipe is the direct test — 2 minutes.

- Looks like engine state accumulating across requests (prefix cache / KV bookkeeping) rather than compute:
  short requests are unaffected and the same request gets slower without any change on the client side.
- Cheap bisection with the kit (rerun `repro_b_latency_growth.py`): prefix caching off first; then `VLLM_USE_V2_MODEL_RUNNER=0`;
  attention backend fallback instead of `B12X_MLA_SPARSE`.
- Related, same image era: #358 (DSpark acceptance collapsing under sustained load, ending with empty outputs /
  the server going down) — different outcome here: the server stays up and correct on short requests, and the
  slowdown persists with DSpark disabled. #349: profiling crash on the 2026-08-15 image.
