# DeepSeek-V4-Flash-0731 on the b12x vLLM build: the model stops following "answer with the filename only" — reproduction kit

## What this is

47 real HTTP requests to `/v1/chat/completions`, recorded from an agent that
searches documents and writes notes. Each request is a normal chat body:
a system prompt, a user message, two tool definitions (`vector_search`,
`write_file`), and — in later turns — the tool results. Nothing else.

11 of the 47 requests are **final-answer turns**: the agent has just written
its note with `write_file`, and the system prompt says the reply must be
**exactly the filename, nothing else** (e.g. `capex_trends.txt`).

`repro.py` sends those requests to a vLLM server and checks one thing per
final-answer turn: *is the reply just a filename?* It also times every call.

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
python3 repro.py --base-url http://HOST:8000/v1 --only 11
```
One request, one verdict, ~30 s. Output on the affected build:

```
#11    20.5s  FAIL  2096 chars: 'apple_microsoft_..._disclosures.txt.txt\n\nActually, let me correct that...'
```
On a healthy build:
```
#11     5.8s  PASS  apple_microsoft_rd_expenses_dividends_workforce_disclosures_fy2025_misc_disclosures.txt
```

More:
```
python3 repro.py --base-url http://HOST:8000/v1 --mode solo                    # all 11 final-answer turns, one at a time
python3 repro.py --base-url http://HOST:8000/v1 --mode degradation --only 11 --repeat 5   # same request 5 times, prints the latency series
python3 repro.py --base-url http://HOST:8000/v1 --mode concurrent              # all 47 with the original timing (how the agent sent them)
python3 repro.py --base-url http://HOST:8000/v1 --model OTHER/MODEL --mode solo  # same requests against another served model
```
Exit code 0 = clean, 1 = reproduced. Before and after each run the script
sends two short probes ("reply pong", "reply with this filename") so you can
see the server is answering normally while the long requests fail.

Python 3.10+, standard library only, no API key (`Authorization: Bearer dummy`).
`payloads.json.gz` contains the request bodies verbatim; temp paths were
replaced by `/tmp/agent-workdir`; the documents quoted in the tool results
are synthetic financial notes generated for a benchmark (freely shareable).

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
