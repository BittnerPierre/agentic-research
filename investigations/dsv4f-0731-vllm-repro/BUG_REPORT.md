# DeepSeek-V4-Flash-0731 on vllm-node-b12x: generation ignores "reply with the filename only" in tool-call conversations, and per-request latency degrades with uptime. Same weights on standard vllm-node are fine.

## Environment

- 2x DGX Spark (GB10 / SM121), tensor-parallel 2
- Affected: image `vllm-node-b12x` (built with `--exp-b12x`), recipe `recipes/deepseek-v4-flash-0731.yaml`
  (b12x MoE/linear backends, `B12X_MLA_SPARSE`, `VLLM_USE_V2_MODEL_RUNNER=1`, `VLLM_USE_FLASHINFER_SAMPLER=1`,
  `--load-format instanttensor`, DSpark spec-decode 5 tokens probabilistic). Image tag/digest: ___ , vLLM version: ___
- Working: image `vllm-node` (standard), recipe `recipes/deepseek-v4-flash.yaml` with the model changed to
  `deepseek-ai/DeepSeek-V4-Flash-0731` and `--speculative-config` removed. Image tag/digest: ___ , vLLM version: ___
- Model: `deepseek-ai/DeepSeek-V4-Flash-0731`, `--tokenizer-mode deepseek_v4`, `--tool-call-parser deepseek_v4`,
  `--reasoning-parser deepseek_v4`, `--kv-cache-dtype fp8`, prefix caching on, `max-num-seqs 8`

## What happens

Chat-completions requests from a tool-using agent (system prompt + 2 tools + a few tool results, 10-30k tokens).
The system prompt requires the final reply to be exactly the written filename. Two things go wrong on the b12x build:

1. **The reply is never just the filename.** Every final-answer turn (11/11 in isolation, 0 accepted in live agent
   runs) comes back as 100-2700 chars of self-commentary, e.g.
   `capex_reference_data.txt.txt` — "Wait, I need to reconsider... I keep adding commentary. The rule says 'Do not include any other text.'"
   `reasoning_effort: "none"` is set; the same happens in thinking mode and at temperature 0.3 or 1.0.
2. **Latency grows with uptime.** The same byte-identical request: 3.0 s shortly after start, 20.5 s after ~50 more
   large requests, timeout (>240 s) after ~60 more. Live agent calls reach 480-810 s. Short prompts stay at
   0.5-3 s throughout, so the server is not stuck — it degrades specifically on these long tool-call contexts.

Both reproduce with speculative decoding removed and with `--max-num-seqs 1`.

**Expected** (and observed on the standard `vllm-node` image with the same weights): reply = filename only,
5-37 s per call, repeating a request stays at ~1.7 s. The previous checkpoint (`DeepSeek-V4-Flash`) and
Qwen3.6-35B-A3B on the standard image, and this checkpoint via a cloud provider, all behave.

## Reproduce

Kit (stdlib Python, no keys, 47 recorded request bodies):
https://github.com/BittnerPierre/agentic-research/tree/config/207-deepseek-0731-minimal/investigations/dsv4f-0731-vllm-repro

```
python3 repro.py --base-url http://HOST:8000/v1 --only 11                              # one request, one verdict
python3 repro.py --base-url http://HOST:8000/v1 --mode degradation --only 11 --repeat 5  # latency series
```
Affected build: `#11 20.5s FAIL 2096 chars: '...txt.txt\n\nActually, let me correct that...'`; series `9.1s -> 240.0s (timeout)`.
Standard image: `#11 5.8s PASS apple_microsoft_..._disclosures.txt`; series `1.7s -> 1.7s -> 1.8s`.

## Notes

- Symptom 2 looks like #358 (draft acceptance collapsing under sustained load, same model/recipe/image era, "stale
  draft ring buffer under request condensing") — but here it also happens with DSpark disabled, so the draft
  buffer alone does not explain it.
- #349 reports the 2026-08-15 b12x image crashing at CUDA-graph profiling for this model; the rollback image may
  behave differently — not tested here.
- Cheap bisection with the kit (2 min per run): prefix caching off; `VLLM_USE_V2_MODEL_RUNNER=0`; attention backend
  fallback instead of `B12X_MLA_SPARSE`; `VLLM_USE_FLASHINFER_SAMPLER=0`; b12x MoE/linear backends off.
