# DeepSeek-V4-Flash-0731 on vllm-node-b12x: in tool-call conversations the model never obeys "reply with the filename only" (100-2700 chars of self-commentary instead). Same weights on standard vllm-node: fine.

Companion issue: latency degradation with uptime on the same build (separate ticket — different failure, may have a different cause).

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

Chat-completions requests from a tool-using agent: system prompt + 2 tools (`vector_search`, `write_file`) + a few
tool results, 10-30k tokens. After the agent has written its note, the system prompt requires the final reply to be
exactly the written filename and nothing else.

On the b12x build the reply is never just the filename. Every one of 11 such requests comes back as 100-2700 chars
of self-commentary — the model narrates its own violation:

> `capex_reference_data.txt.txt` — "Wait, I need to reconsider... I keep adding commentary. The rule says 'Do not include any other text.'"

This happens from the first request on a freshly started server (no warm-up or load needed), with
`reasoning_effort: "none"` and in thinking mode, at temperature 0.3 and 1.0, with DSpark disabled, and with
`--max-num-seqs 1`. Short prompts carrying the same instruction ("reply with exactly the filename") are answered
correctly on the same server in 0.5-3 s — the failure is specific to the long tool-call context.

**Expected** (observed on standard `vllm-node`, same weights): reply = filename only, 11/11, 5-37 s per call.
Also fine: the previous checkpoint `DeepSeek-V4-Flash` and Qwen3.6-35B-A3B on the standard image (same requests
replayed), and this checkpoint through a cloud provider inside the full agent workflow (7/7, twice).

## Reproduce

Kit (stdlib Python, no keys, 47 recorded request bodies):
https://github.com/BittnerPierre/agentic-research/tree/config/207-deepseek-0731-minimal/investigations/dsv4f-0731-vllm-repro

```
python3 repro.py --base-url http://HOST:8000/v1 --only 11        # one request, one verdict, ~30 s
python3 repro.py --base-url http://HOST:8000/v1 --mode solo      # all 11 final-answer requests
```
Affected build: `#11 20.5s FAIL 2096 chars: '...txt.txt\n\nActually, let me correct that...'` (11/11 FAIL).
Standard image: `#11 5.8s PASS apple_microsoft_..._disclosures.txt` (11/11 PASS).

## Notes

- Ruled out: the weights (fine elsewhere), the `deepseek_v4` parsers as shipped in the standard image, speculative
  decoding by itself, concurrency, sampling, thinking mode.
- Cheap bisection with the kit (one flag at a time, `--only 11`): `VLLM_USE_V2_MODEL_RUNNER=0`; attention backend
  fallback instead of `B12X_MLA_SPARSE`; `VLLM_USE_FLASHINFER_SAMPLER=0`; b12x MoE/linear backends off.
  `repro.py --mode template --chat-template FILE` (needs `--trust-request-chat-template`) replays with the
  checkpoint's own chat template to test the template-rendering path.
- Related, same image era: #349 (CUDA-graph profiling crash on the 2026-08-15 image). Not #358 (that one ends with
  empty outputs / the server going down; here the server stays up and correct on short requests).
