# Repro — DeepSeek-V4-Flash-0731 on vLLM (DGX Spark): tool-loop final answers ignore a strict output instruction; per-request latency degrades over server lifetime

Self-contained reproduction for maintainers (vLLM / spark-vllm-docker recipe /
model). Python stdlib only, plain `/v1/chat/completions`, no agent framework,
no API keys.

## Symptom

In agentic tool-loop conversations (system prompt + tools + a few
`vector_search`/`write_file` tool results, 10-30k tokens), the model is
instructed to end its final turn by replying with EXACTLY the written filename
and nothing else. On the affected stack the final assistant message instead
contains 100-2700 chars of self-commentary — literally narrating its own
non-compliance:

> `...capex_reference_data.txt.txt` — *"Wait, I need to reconsider... I keep
> adding commentary. The rule says 'Do not include any other text.'"*

Secondary symptom: per-request latency degrades dramatically over the server's
lifetime. The SAME byte-identical request measured on one server instance:
**3.0 s** (first pass) → **20.5 s** (after ~50 more large requests) →
**timeout > 240 s** (after ~60 more). During live agent runs, calls reach
480-810 s.

## What rules the model itself out

- Short single-turn prompts with the same "reply with the filename only"
  instruction are clean on the SAME server (thinking and non-thinking modes).
- The SAME agentic workflow (same prompts, same parallel calls, same
  checkpoint `deepseek-v4-flash-0731`) through a cloud provider is clean:
  7/7 compliant final answers, twice.
- The trigger is: (this serving stack) x (long tool-loop context). No
  concurrency and no request sequence is required — an isolated request
  reproduces (`--mode solo`: 11/11 violations observed).

## Files

- `repro.py` — replayer with PASS/FAIL verdicts and latency flags.
- `payloads.json.gz` — 47 verbatim request bodies recorded from one real
  agent run (finance research over a self-generated corpus; temp paths
  genericized; no secrets). 11 of them are "contract turns" whose response
  must be a bare filename.

## Two isolated tests

**Test A — instruction-following collapse (chattiness).** Contract verdicts on
long tool-loop requests, in isolation. Every run is bracketed by a functional
CANARY (two short requests: ping + a mini filename contract): on the affected
stack the canaries stay fast and compliant while the long requests fail —
the server is not broken, it discriminates by request shape.

**Test B — cumulative latency degradation.** `--mode degradation` resends the
SAME request over and over, canaries interleaved. Observed on the affected
stack: 9.1 s -> timeout 240 s on the second repetition of a request that took
4.3 s when recorded, canaries at 0.7-1.7 s throughout.

## Usage

```
# minimal Test A: one request, one verdict (canaries included)
python3 repro.py --base-url http://HOST:8000/v1 --only 11

# Test A: each contract turn in isolation
python3 repro.py --base-url http://HOST:8000/v1 --mode solo

# Test B: same request repeated, latency series
python3 repro.py --base-url http://HOST:8000/v1 --mode degradation --only 11 --repeat 5

# recorded order / recorded concurrency (like the agent harness)
python3 repro.py --base-url http://HOST:8000/v1 --mode sequence
python3 repro.py --base-url http://HOST:8000/v1 --mode concurrent
```

Exit code 0 = clean, 1 = reproduced.

## Discriminating variants (Test A)

- **Cross-model control**: `--model OTHER/CHECKPOINT` replays the same
  conversations against another served checkpoint. CAUTION: serving recipes
  often change the vLLM image and backends along with the model — a clean
  sibling then exonerates neither the model nor the build individually.
  State which image/backends each cell used (see Evidence matrix).
- **Template bypass**: `--mode template --chat-template FILE` sends the
  checkpoint's official Jinja chat template with each request, bypassing the
  template the serving recipe applies. Requires the server flag
  `--trust-request-chat-template` (the affected build supports the field and
  refuses it without the flag). Chattiness gone => the served template/tool
  rendering is the culprit; chattiness persists => deeper (kernels /
  quantization).

## Suggested protocol on a fresh server

1. Restart vLLM. Run `--only 11` → note verdict + latency (baseline).
2. Run `--mode degradation --only 11 --repeat 5` → latency series (Test B).
3. Run `--mode solo` → full Test A.
4. Run `--mode concurrent` → live-harness conditions.
5. Optional: cross-model and template variants above.

## Observed results (2026-09-02, DGX Spark)

| Run | Result |
|---|---|
| Recording run (live agent, ~8 concurrent) | 5 rejected deliveries, all 11 final answers non-compliant, latencies degrading 3-166 s → 480-810 s, run dies with no usable search results |
| `--mode solo` (same server, later) | **11/11 violations** + 1 timeout > 300 s |
| `--only 11` (same server, later still) | timeout > 240 s (was 3.0 s when recorded) |
| Canaries during ALL of the above | fast and compliant (0.7-1.7 s) — server discriminates by request shape |
| `--mode degradation --only 47 --repeat 2` | 9.1 s -> timeout 240 s (recorded 4.3 s), canaries clean throughout |
| Same checkpoint via cloud provider, same workflow | clean, twice (finance 7/7, concept 7/7) |
| Serialized decoding (`--max-num-seqs 1`) | still reproduces → not a concurrency/batching issue |

## Evidence matrix (2026-09-03)

| Cell | Image / backends | Verdict |
|---|---|---|
| 0731 x b12x build, DSpark on | vllm-node-b12x, b12x MoE/linear, B12X_MLA_SPARSE, V2 runner | DIRTY (chattiness + degradation) |
| 0731 x b12x build, DSpark OFF | same b12x build, speculative removed only | DIRTY (7/7 chatty, 2026-08) |
| V4-Flash preview x standard image | vllm-node, default backends, SAME deepseek_v4 parsers, MTP-2 | clean (full July campaign) |
| Qwen3.6 x standard image | vllm-node, flashinfer/marlin, qwen3 parsers | clean (replays 10/11 PASS, no degradation after 60+ large calls) |
| 0731 x cloud provider | unknown precision/stack | clean (7/7, twice) |
| V4-Flash preview x standard image, replays | vllm-node, deepseek_v4 parsers | clean (**11/11 PASS on the exact replays**, 4-30 s) |
| **0731 x standard image, no speculative** | vllm-node, deepseek_v4 parsers, spec removed | **clean — 11/11 PASS (5-37 s), degradation series flat (1.7 s x3)** |

## Verdict (2026-09-03)

The SAME 0731 NVFP4 weights that violate the contract 11/11 on the
`vllm-node-b12x` build produce 11/11 bare filenames on the standard
`vllm-node` image (same host, same GPUs, speculative removed). Latency stays
flat where the b12x build degraded to 480-810 s and timeouts.

**Convicted: the experimental b12x build** (one or more of: b12x MoE/linear
backends, B12X_MLA_SPARSE attention, V2 model runner, FLASHINFER_SAMPLER,
instanttensor+DSpark loader path, or that build's deepseek_v4 tool/template
code). **Exonerated: the model, the 0731 NVFP4 weight artifact, the
deepseek_v4 parsers as shipped in the standard image, concurrency/batching,
sampling parameters, and speculative decoding as a feature** (dirty with AND
without DSpark on the b12x build).

Note: the Qwen3.6 control ran on the standard image (its recipe changes the
image along with the model); its single FAIL (#19, 265 chars) is mild
commentary on a genuinely confusing foreign history, not the systematic
self-correction spiral. Flag-level bisection inside the b12x build (e.g.
disable prefix caching, V2 runner, MLA_SPARSE one at a time) is left to the
build maintainers — each cell costs ~2 minutes with this repro.

Environment (fill in when reporting): vLLM version/image, serving recipe and
flags, GPU/driver, quantization of the served weights.
