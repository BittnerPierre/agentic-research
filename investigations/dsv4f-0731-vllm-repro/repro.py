#!/usr/bin/env python3
"""Minimal reproduction — DeepSeek-V4-Flash-0731 on vLLM ignores a strict
"reply with the filename only" instruction in agentic tool-loop conversations.

Standalone: Python stdlib only, plain /v1/chat/completions calls, no agent SDK,
no API keys. Payloads are verbatim request bodies recorded from a real
multi-agent research run (temp paths genericized). The tool-loop conversations
instruct the model to end its turn by replying with EXACTLY the written
filename and nothing else. Observed on a DGX Spark serving stack: the final
assistant message instead contains 100-2700 chars of self-commentary
("Wait — I keep adding commentary...", filename corrections, task recaps),
while the SAME requests replayed in isolation come back clean — and per-call
latency degrades from tens of seconds to 480-810 s as the sequence progresses.

Usage:
    python3 repro.py --base-url http://HOST:8000/v1 --only 11          # MINIMAL: one request, one verdict
    python3 repro.py --base-url http://HOST:8000/v1 --mode solo        # each final turn alone
    python3 repro.py --base-url http://HOST:8000/v1 --mode sequence    # recorded order, one at a time
    python3 repro.py --base-url http://HOST:8000/v1 --mode concurrent  # recorded order + recorded overlap (like the agent harness)

Observed on the affected DGX Spark stack (2026-09-02): even --mode solo FAILS
11/11 — a single isolated request with a long tool-loop context is enough to
trigger the chatty final answer (plus one 300+ s timeout). Short single-turn
prompts with the same instruction are clean on the same server, and the same
requests through a cloud provider serving the same checkpoint are clean:
the trigger is (this serving stack) x (long tool-loop context), no
concurrency or request sequence required. Latency degradation to 480-810 s
per call was additionally observed as the recorded agent run progressed.

PASS/FAIL criterion per file_search final turn: the assistant content must
match ^[A-Za-z0-9_.\\-]+\\.txt$ (the instruction embedded in the recorded
system prompt). Everything else (notes, corrections, recaps) is a violation.
"""

import argparse
import concurrent.futures
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BARE_FILENAME = re.compile(r"[A-Za-z0-9_.\-]+\.txt")
DEFAULT_TIMEOUT = 1800  # the affected stack has produced 800+ s calls


def load_bundle(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def is_contract_turn(entry: dict) -> bool:
    """Final turns of file_search conversations (tools include vector_search)."""
    tools = entry["body"].get("tools") or []
    names = {t.get("function", {}).get("name") for t in tools}
    return bool(entry.get("final_turn")) and "vector_search" in names


def call(base_url: str, body: dict, timeout: float) -> tuple[float, dict | None, str]:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return time.time() - t0, json.load(r), ""
    except urllib.error.HTTPError as e:
        return time.time() - t0, None, f"HTTP {e.code}: {e.read()[:200]!r}"
    except Exception as e:  # timeout, connection reset...
        return time.time() - t0, None, f"{type(e).__name__}: {e}"


def verdict(entry: dict, resp: dict | None, err: str) -> tuple[str, str]:
    if resp is None:
        return "ERROR", err
    msg = resp["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not is_contract_turn(entry):
        return "-", f"{len(content)} chars (not a contract turn)"
    if BARE_FILENAME.fullmatch(content):
        return "PASS", content
    return "FAIL", f"{len(content)} chars: {content[:160]!r}"


def run_one(base_url: str, entry: dict, timeout: float, results: list):
    dt, resp, err = call(base_url, entry["body"], timeout)
    v, detail = verdict(entry, resp, err)
    slow = "  [PATHOLOGICAL LATENCY]" if dt > 300 else ""
    print(f"#{entry['n']:02d} {dt:7.1f}s (recorded {entry['recorded_duration_s']:7.1f}s) {v:5} {detail}{slow}", flush=True)
    results.append((entry["n"], v, dt))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", required=True, help="OpenAI-compatible endpoint, e.g. http://host:8000/v1")
    p.add_argument("--mode", choices=("solo", "sequence", "concurrent"), default="concurrent")
    p.add_argument("--payloads", default=str(Path(__file__).parent / "payloads.json.gz"))
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--time-scale", type=float, default=1.0,
                   help="concurrent mode: multiply recorded start offsets (0 = fire all at once)")
    p.add_argument("--only", type=int, default=None, metavar="N",
                   help="send only recorded request N (minimal repro; e.g. 11)")
    args = p.parse_args()

    bundle = load_bundle(Path(args.payloads))
    entries = bundle["requests"]
    if args.only is not None:
        entries = [e for e in entries if e["n"] == args.only]
        if not entries:
            print(f"no recorded request #{args.only}")
            return 2
        args.mode = "solo"
    print(f"model: {bundle['model']} | {len(entries)} recorded requests | "
          f"{sum(1 for e in entries if is_contract_turn(e))} contract turns | mode={args.mode}\n")

    results: list = []
    t0 = time.time()
    if args.mode == "solo":
        for e in entries:
            if is_contract_turn(e):
                run_one(args.base_url, e, args.timeout, results)
    elif args.mode == "sequence":
        for e in entries:
            run_one(args.base_url, e, args.timeout, results)
    else:  # concurrent: recorded start offsets
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futs = []
            for e in entries:
                delay = e["offset_s"] * args.time_scale - (time.time() - t0)
                if delay > 0:
                    time.sleep(delay)
                futs.append(pool.submit(run_one, args.base_url, e, args.timeout, results))
            concurrent.futures.wait(futs)

    contract = [(n, v, dt) for n, v, dt in results if v in ("PASS", "FAIL", "ERROR")]
    fails = [n for n, v, _ in contract if v != "PASS"]
    slow = [n for n, _, dt in results if dt > 300]
    print(f"\n=== SUMMARY ({args.mode}) ===")
    print(f"contract turns : {len(contract)} | violations/errors: {len(fails)} {fails}")
    print(f"calls over 300s: {len(slow)} {slow}")
    print("REPRODUCED" if fails or slow else "clean")
    return 1 if fails or slow else 0


if __name__ == "__main__":
    sys.exit(main())
