# DeepSeek-V4-Flash-0731 on the b12x vLLM build: the model stops following "answer with the filename only" — reproduction kit

> Canonical, standalone copy of this kit (MIT): https://github.com/BittnerPierre/dsv4f-0731-vllm-b12x-repro — this directory is the working copy inside the research project.

## What this is

47 real HTTP requests to `/v1/chat/completions`, recorded from an agent that
searches documents and writes notes. Each request is a normal chat body:
a system prompt, a user message, two tool definitions (`vector_search`,
`write_file`), and — in later turns — the tool results. Nothing else.

11 of the 47 requests are **final-answer turns**: the agent has just written
its note with `write_file`, and the system prompt says the reply must be
**exactly the filename, nothing else** (e.g. `capex_trends.txt`).

Two scripts, one per symptom:
- `repro_a_filename_only.py` sends one of those final-answer requests and checks: *is the reply just a filename?*
- `repro_b_latency_growth.py` sends the same request several times and prints how long each one took.

Both start by checking that the server is reachable and serves the model, then send two short
probes ("reply pong", "reply with this filename") that must pass — if they fail, the server is
simply down and the scripts stop with exit code 2 instead of claiming anything.

## What we see

On the `vllm-node-b12x` build serving `deepseek-ai/DeepSeek-V4-Flash-0731`,
the reply is never just the filename. It is 100-2700 characters like:

```
apple_microsoft_rd_expenses_..._disclosures.txt.txt

Actually, let me correct that. The filename should be exactly as written...
Wait, I need to reconsider... I keep adding commentary. The rule says
"Do not include any other text."
```

and the same request gets slower each time it is sent: 3 s, then 20 s, then
timeout after 240 s. Short prompts sent in between stay fast and correct.

On the standard `vllm-node` image, same weights, same requests: 11/11 replies
are exactly the filename, every call takes 5-37 s, and repeating a request
takes 1.7 s each time.

## Run it

```
python3 repro_a_filename_only.py --list                                  # the 11 final-answer requests, numbered
python3 repro_a_filename_only.py --base-url http://HOST:8000/v1          # send request #11, check the reply (~30 s)
python3 repro_a_filename_only.py --base-url http://HOST:8000/v1 --all    # all 11, one at a time
python3 repro_b_latency_growth.py --base-url http://HOST:8000/v1         # request #11 five times, latency series
python3 repro_b_latency_growth.py --base-url http://HOST:8000/v1 --replay-all   # all 47 with the recorded timing
```
`--request N` picks another recorded request (numbers from `--list`); `--model NAME` replays against another
served model. Exit code: 0 clean, 1 reproduced, 2 could not run.

Output of `repro_a` on the affected build:
```
  #11   20.5s  WRONG 2096 chars: 'apple_microsoft_..._disclosures.txt.txt\n\nActually, let me correct that...'
REPRODUCED: 1/1 replies were not just the filename [11]
```
On a healthy build:
```
  #11    5.8s  ok    apple_microsoft_rd_expenses_dividends_workforce_disclosures_fy2025_misc_disclosures.txt
clean: 1/1 replies were exactly the filename
```
Output of `repro_b` on the affected build: `latency series: 9.1s -> 240.0s` (timeout) — on a healthy build:
`latency series: 1.7s -> 1.7s -> 1.8s`.

Python 3.10+, standard library only, no API key (`Authorization: Bearer dummy`).
`requests/` holds the 47 request bodies as readable JSON, one file per request
(`requests/11.json` is the default one), plus `requests/SYSTEM_PROMPT.txt` — the
system message they share, where the "return only the name of the file ...
Do not include any other text" rule lives — and `requests/index.json` /
`requests/README.md` listing them. Temp paths were replaced by
`/tmp/agent-workdir`; the documents quoted in the tool results are synthetic
financial notes generated for a benchmark (freely shareable).

## What was tested

| Weights | Build | Filename-only replies | Latency |
|---|---|---|---|
| V4-Flash-0731 | `vllm-node-b12x`, DSpark speculative on | 0 / 11 | degrades to 480-810 s, timeouts |
| V4-Flash-0731 | `vllm-node-b12x`, speculative off | 0 / 7 | — |
| V4-Flash-0731 | `vllm-node-b12x`, `--max-num-seqs 1` | fails | — |
| V4-Flash-0731 | standard `vllm-node`, speculative off | **11 / 11** | flat, 5-37 s |
| V4-Flash (previous checkpoint) | standard `vllm-node` | 11 / 11 | flat |
| Qwen3.6-35B-A3B | standard `vllm-node` | 10 / 11 | flat |
| V4-Flash-0731 | cloud provider | 7 / 7 (live agent run, twice) | — |

So: not the weights, not the prompts, not speculative decoding by itself, not
concurrency. Something in the b12x build path for this model.

Issue texts: `ISSUE-A-instruction-following.md` (wrong replies) and `ISSUE-B-latency-degradation.md` (slowdown with uptime).
