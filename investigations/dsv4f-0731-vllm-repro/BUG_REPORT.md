# Bug report — DeepSeek-V4-Flash-0731 on the `vllm-node-b12x` build (DGX Spark): tool-loop final answers ignore strict output instructions, and per-request latency degrades over server lifetime. Clean on standard `vllm-node` with the same weights.

Target audiences: spark-vllm-docker (eugr), local-inference-lab/b12x, DGX Spark community, vLLM (if the b12x integration path is upstream-relevant).

Reproduction package (stdlib Python, no agent SDK, no keys):
https://github.com/BittnerPierre/agentic-research/tree/config/207-deepseek-0731-minimal/investigations/dsv4f-0731-vllm-repro

## TL;DR

Same host (2x DGX Spark, TP=2), same weights (`deepseek-ai/DeepSeek-V4-Flash-0731`), same 47 recorded request bodies:

| Serving build | Instruction following (11 contract turns) | Latency |
|---|---|---|
| `vllm-node-b12x` (recipe `deepseek-v4-flash-0731.yaml`) | **0/11** compliant — model narrates its own non-compliance | degrades 3 s -> 20 s -> timeout > 240 s on the SAME request; 480-810 s per call in live agent runs |
| `vllm-node` standard (same recipe shape as `deepseek-v4-flash.yaml`, speculative removed) | **11/11** compliant | flat, 5-37 s per call, 1.7 s x3 on repetition |

The defect reproduces on the b12x build **with and without** DSpark speculative decoding, with serialized decoding (`--max-num-seqs 1`), at temperature 0.3 and 1.0, in thinking and non-thinking modes. It does not reproduce on the standard image, on a cloud provider serving the same checkpoint, or with the previous V4-Flash checkpoint on the standard image.

## Symptom A — instruction-following collapse in long tool-loop contexts

Agentic conversations (system prompt + 2 tools + a few `vector_search` / `write_file` tool results, 10-30k tokens) instruct the model to end its turn by replying with EXACTLY the written filename. On the b12x build the final message instead contains 100-2700 chars of self-commentary, literally narrating the violation:

> `...capex_reference_data.txt.txt` — "Wait, I need to reconsider... I keep adding commentary. The rule says 'Do not include any other text.'"

Short single-turn prompts with the same instruction are clean on the SAME server (canary probes, 0.4-3 s), so the server is not globally broken: it discriminates by request shape.

## Symptom B — cumulative latency degradation

The same byte-identical request on one b12x server instance: 3.0 s (first pass) -> 20.5 s (after ~50 more large requests) -> timeout > 240 s (after ~60 more). Canaries stay at 0.7-1.7 s throughout. In live agent runs, individual calls reach 480-810 s. On the standard image the same request repeats at 1.7 s / 1.7 s / 1.8 s.

## Evidence matrix

| Cell | Build / backends | Verdict |
|---|---|---|
| 0731 x b12x, DSpark-5 on | vllm-node-b12x, b12x MoE/linear, B12X_MLA_SPARSE, V2 model runner, FLASHINFER_SAMPLER, instanttensor + hybrid draft loader | DIRTY (A + B) |
| 0731 x b12x, speculative removed | same build, only DSpark removed | DIRTY (7/7 chatty) |
| 0731 x b12x, `--max-num-seqs 1` | same build, serialized decoding | DIRTY |
| 0731 x standard vllm-node, no speculative | default backends, same deepseek_v4 parsers | CLEAN — 11/11, flat latency, full 47-request sequence clean, live agent run 7/7 |
| V4-Flash (previous checkpoint) x standard vllm-node | same recipe shape | CLEAN — 11/11 on the exact same replays |
| Qwen3.6-35B-A3B x standard vllm-node | flashinfer/marlin, qwen3 parsers | CLEAN — 10/11 (one mild comment on a foreign history), no degradation after 60+ large calls |
| 0731 x cloud provider (same checkpoint, unknown precision) | — | CLEAN — 7/7, twice, in a full agent workflow |

Ruled out: the model and checkpoint (clean elsewhere), the `deepseek_v4` tokenizer/tool/reasoning parsers as shipped in the standard image, speculative decoding as a feature, concurrency/batching, sampling parameters, thinking mode.
Remaining suspects, all inside the b12x build: b12x MoE/linear backends, `B12X_MLA_SPARSE` attention, `VLLM_USE_V2_MODEL_RUNNER`, `VLLM_USE_FLASHINFER_SAMPLER`, the instanttensor + hybrid-draft loader path, or that build's version of the deepseek_v4 tool/template rendering.

## Environment (to complete before posting)

- Hardware: 2x NVIDIA DGX Spark (GB10, SM121), tensor-parallel 2
- Dirty build: image `vllm-node-b12x` built with `--exp-b12x` — vLLM version: ___, b12x commit: ___, image digest: ___
- Clean build: image `vllm-node` — vLLM version: ___, image digest: ___
- Driver / CUDA: ___
- Weights: `deepseek-ai/DeepSeek-V4-Flash-0731` as published (precision as shipped: ___)
- Recipes: `recipes/deepseek-v4-flash-0731.yaml` (dirty), `recipes/deepseek-v4-flash.yaml` shape with model swapped to 0731 and `--speculative-config` removed (clean)

## How to reproduce (2 minutes per cell)

```
git clone https://github.com/BittnerPierre/agentic-research -b config/207-deepseek-0731-minimal
cd agentic-research/investigations/dsv4f-0731-vllm-repro
python3 repro.py --base-url http://HOST:8000/v1 --only 11                      # minimal: one request, one verdict
python3 repro.py --base-url http://HOST:8000/v1 --mode solo                    # 11 contract turns in isolation
python3 repro.py --base-url http://HOST:8000/v1 --mode degradation --only 11 --repeat 5   # latency series
python3 repro.py --base-url http://HOST:8000/v1 --mode concurrent              # recorded harness concurrency
```
Exit code 1 = reproduced. Every run is bracketed by short canary probes. `--model NAME` replays against another served checkpoint; `--mode template --chat-template FILE` bypasses the served template (needs `--trust-request-chat-template` on the server).

## Suggested bisection on the b12x build

One flag at a time on `deepseek-v4-flash-0731.yaml`, verdict via `repro.py --only 11` then `--mode degradation`: disable prefix caching; `VLLM_USE_V2_MODEL_RUNNER=0`; attention backend fallback instead of `B12X_MLA_SPARSE`; `VLLM_USE_FLASHINFER_SAMPLER=0`; b12x MoE/linear backends off. Symptom B (degradation) suggests engine-state accumulation (prefix cache / KV bookkeeping) as the first place to look; symptom A may or may not share the cause.

## Impact

With the b12x build, every multi-step agent workflow on this checkpoint fails (all tool-loop deliveries rejected, runs die without usable results, calls of 8-13 minutes). With the standard image the same workflow completes correctly at roughly 12% lower throughput than the previous checkpoint with MTP-2 — the b12x build's speed advantage is currently unusable for this checkpoint.
