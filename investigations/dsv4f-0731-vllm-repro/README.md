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

## Usage

```
# minimal: one request, one verdict
python3 repro.py --base-url http://HOST:8000/v1 --only 11

# each contract turn in isolation
python3 repro.py --base-url http://HOST:8000/v1 --mode solo

# recorded order / recorded concurrency (like the agent harness)
python3 repro.py --base-url http://HOST:8000/v1 --mode sequence
python3 repro.py --base-url http://HOST:8000/v1 --mode concurrent
```

Exit code 0 = clean, 1 = reproduced.

## Suggested protocol on a fresh server

1. Restart vLLM. Run `--only 11` → note verdict + latency (baseline).
2. Run `--mode solo` twice back-to-back → compare latencies pass 1 vs pass 2
   (degradation shows within/across passes on the affected stack).
3. Run `--mode concurrent` → live-harness conditions.

## Observed results (2026-09-02, DGX Spark)

| Run | Result |
|---|---|
| Recording run (live agent, ~8 concurrent) | 5 rejected deliveries, all 11 final answers non-compliant, latencies degrading 3-166 s → 480-810 s, run dies with no usable search results |
| `--mode solo` (same server, later) | **11/11 violations** + 1 timeout > 300 s |
| `--only 11` (same server, later still) | timeout > 240 s (was 3.0 s when recorded) |
| Same checkpoint via cloud provider, same workflow | clean, twice (finance 7/7, concept 7/7) |
| Serialized decoding (`--max-num-seqs 1`) | still reproduces → not a concurrency/batching issue |

Environment (fill in when reporting): vLLM version/image, serving recipe and
flags, GPU/driver, quantization of the served weights.
