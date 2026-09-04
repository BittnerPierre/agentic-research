#!/usr/bin/env python3
"""Symptom A — the model does not obey "reply with the filename only".

Sends one recorded request (a real agent turn: system prompt, two tools, a few
tool results; the reply must be exactly the filename just written) and checks
the reply. Stdlib only, no API key.

    python3 repro_a_filename_only.py --base-url http://spark1:8000/v1            # request #11 (default)
    python3 repro_a_filename_only.py --base-url http://spark1:8000/v1 --all      # all 11 such requests
    python3 repro_a_filename_only.py --list                                      # what the numbers mean

Exit 0 = the reply was just a filename (clean). Exit 1 = it was not (reproduced).
Exit 2 = could not run (server unreachable, wrong model, short probes failing).
"""

import argparse
import sys
from pathlib import Path

from common import (
    BARE_FILENAME,
    EXIT_CANNOT_RUN,
    EXIT_CLEAN,
    EXIT_REPRODUCED,
    chat,
    describe,
    die,
    final_answer_requests,
    load_requests,
    preflight,
    reply_text,
    short_probes,
)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--base-url", help="vLLM OpenAI-compatible endpoint, e.g. http://spark1:8000/v1")
    p.add_argument(
        "--request",
        type=int,
        default=11,
        metavar="N",
        help="which recorded request to send (see --list); default 11",
    )
    p.add_argument(
        "--all", action="store_true", help="send all 11 final-answer requests, one at a time"
    )
    p.add_argument("--list", action="store_true", help="list the final-answer requests and exit")
    p.add_argument("--model", default=None, help="replay against another served model name")
    p.add_argument(
        "--chat-template",
        default=None,
        metavar="FILE",
        help="send this Jinja template with each request (server needs --trust-request-chat-template)",
    )
    p.add_argument("--timeout", type=float, default=600)
    args = p.parse_args()

    model, requests = load_requests()
    finals = final_answer_requests(requests)
    if args.list:
        print("Recorded requests whose reply must be exactly a filename:")
        for e in finals:
            print(" ", describe(e))
        return EXIT_CLEAN
    if not args.base_url:
        p.error("--base-url is required (or use --list)")
    if args.model:
        model = args.model
        for e in requests:
            e["body"]["model"] = model
    targets = finals if args.all else [e for e in finals if e["n"] == args.request]
    if not targets:
        die(f"CANNOT RUN: no final-answer request #{args.request}; see --list")

    preflight(args.base_url, model)
    print("short probes (must pass, otherwise the server itself is broken):")
    if not short_probes(args.base_url, model):
        sys.exit(EXIT_CANNOT_RUN)

    print("\nlong recorded request(s) — the reply must be exactly the filename:")
    failed = []
    for e in targets:
        body = (
            dict(e["body"], chat_template=Path(args.chat_template).read_text())
            if args.chat_template
            else e["body"]
        )
        dt, resp, err = chat(args.base_url, body, args.timeout)
        if resp is None:
            print(f"  #{e['n']:02d} {dt:6.1f}s  ERROR {err}")
            failed.append(e["n"])
            continue
        text = reply_text(resp)
        if BARE_FILENAME.fullmatch(text):
            print(f"  #{e['n']:02d} {dt:6.1f}s  ok    {text}")
        else:
            print(f"  #{e['n']:02d} {dt:6.1f}s  WRONG {len(text)} chars: {text[:140]!r}")
            failed.append(e["n"])

    print()
    if failed:
        print(
            f"REPRODUCED: {len(failed)}/{len(targets)} replies were not just the filename {failed}"
        )
        return EXIT_REPRODUCED
    print(f"clean: {len(targets)}/{len(targets)} replies were exactly the filename")
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
