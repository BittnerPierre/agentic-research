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
    print(
        f"#{entry['n']:02d} {dt:7.1f}s (recorded {entry['recorded_duration_s']:7.1f}s) {v:5} {detail}{slow}",
        flush=True,
    )
    results.append((entry["n"], v, dt))


def canary(base_url: str, model: str, timeout: float = 60) -> None:
    """Functional control: SHORT requests must stay fast and compliant even
    when the long tool-loop replays fail — proving the server is not simply
    broken, but discriminates by request shape."""
    probes = [
        ("canary/ping", [{"role": "user", "content": "Reply with exactly: pong"}], None),
        (
            "canary/contract",
            [
                {
                    "role": "user",
                    "content": "You saved a file named canary_probe.txt. Reply with exactly the "
                    "filename and nothing else. Do not include any other text.",
                }
            ],
            "canary_probe.txt",
        ),
    ]
    for name, msgs, expect in probes:
        body = {
            "model": model,
            "messages": msgs,
            "max_tokens": 512,  # les hybrides (Qwen3.x) consomment du thinking avant le content
            "temperature": 1.0,
            "top_p": 0.95,
        }
        dt, resp, err = call(base_url, body, timeout)
        if resp is None:
            print(f"{name}: ERROR {err}")
            continue
        content = (resp["choices"][0]["message"].get("content") or "").strip()
        ok = "PASS" if (expect is None and content) or content == expect else "FAIL"
        print(f"{name}: {dt:5.1f}s {ok}  {content[:60]!r}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--base-url", required=True, help="OpenAI-compatible endpoint, e.g. http://host:8000/v1"
    )
    p.add_argument(
        "--mode",
        choices=("solo", "sequence", "concurrent", "degradation", "template"),
        default="concurrent",
    )
    p.add_argument("--payloads", default=str(Path(__file__).parent / "payloads.json.gz"))
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument(
        "--time-scale",
        type=float,
        default=1.0,
        help="concurrent mode: multiply recorded start offsets (0 = fire all at once)",
    )
    p.add_argument(
        "--only",
        type=int,
        default=None,
        metavar="N",
        help="send only recorded request N (minimal repro; e.g. 11)",
    )
    p.add_argument(
        "--model",
        default=None,
        metavar="NAME",
        help="override the model field of every request (cross-model control, "
        "e.g. another checkpoint served by the same stack)",
    )
    p.add_argument(
        "--repeat",
        type=int,
        default=5,
        help="degradation mode: how many times to resend the same request",
    )
    p.add_argument(
        "--chat-template",
        default=None,
        metavar="FILE",
        help="template mode: Jinja file (the checkpoint's official chat template) "
        "sent per-request; the server must run with --trust-request-chat-template",
    )
    p.add_argument("--no-canary", action="store_true", help="skip the short functional probes")
    args = p.parse_args()

    bundle = load_bundle(Path(args.payloads))
    entries = bundle["requests"]
    model = args.model or bundle["model"]
    if args.model:
        for e in entries:
            e["body"]["model"] = args.model
    if args.only is not None:
        entries = [e for e in entries if e["n"] == args.only]
        if not entries:
            print(f"no recorded request #{args.only}")
            return 2
        if args.mode not in ("degradation", "template"):
            args.mode = "solo"
    print(
        f"model: {model} | {len(entries)} recorded requests | "
        f"{sum(1 for e in entries if is_contract_turn(e))} contract turns | mode={args.mode}\n"
    )

    if not args.no_canary:
        canary(args.base_url, model)
        print()

    results: list = []
    t0 = time.time()
    if args.mode == "degradation":
        # Test B: the SAME request over and over — on the affected stack its
        # latency grows across repetitions (observed 3 s -> 20 s -> timeout)
        # while the interleaved canaries stay fast.
        target = (
            entries[0] if args.only else next(e for e in bundle["requests"] if is_contract_turn(e))
        )
        print(f"degradation probe: request #{target['n']} x{args.repeat}")
        for i in range(args.repeat):
            run_one(args.base_url, target, args.timeout, results)
            if not args.no_canary:
                canary(args.base_url, model)
        series = [f"{dt:.1f}s" for _, _, dt in results]
        print(f"latency series: {' -> '.join(series)}")
    elif args.mode == "template":
        # Test A variant: bypass the server's own template rendering.
        if not args.chat_template:
            print(
                "template mode requires --chat-template FILE (the checkpoint's official Jinja template)"
            )
            return 2
        template = Path(args.chat_template).read_text()
        for e in entries:
            if is_contract_turn(e):
                e = {**e, "body": {**e["body"], "chat_template": template}}
                run_one(args.base_url, e, args.timeout, results)
    elif args.mode == "solo":
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

    if not args.no_canary:
        print()
        canary(args.base_url, model)

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
