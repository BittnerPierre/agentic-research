#!/usr/bin/env python3
"""Symptom B — the same long request gets slower every time it is sent.

Sends one recorded request (a real agent turn, 10-30k tokens) several times in
a row, with two short probes between repetitions, and prints the latency of
each repetition. Stdlib only, no API key.

    python3 repro_b_latency_growth.py --base-url http://spark1:8000/v1                  # request #11, 5 times
    python3 repro_b_latency_growth.py --base-url http://spark1:8000/v1 --repeat 8
    python3 repro_b_latency_growth.py --base-url http://spark1:8000/v1 --replay-all     # all 47 recorded requests, recorded timing

Exit 0 = latency stayed flat (clean). Exit 1 = a repetition timed out, errored,
took over 300 s, or was 3x slower than the first (reproduced).
Exit 2 = could not run (server unreachable, wrong model, short probes failing).
"""

import argparse
import concurrent.futures
import sys
import time

from common import (
    EXIT_CANNOT_RUN,
    EXIT_CLEAN,
    EXIT_REPRODUCED,
    chat,
    die,
    final_answer_requests,
    load_requests,
    preflight,
    short_probes,
)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--base-url",
        required=True,
        help="vLLM OpenAI-compatible endpoint, e.g. http://spark1:8000/v1",
    )
    p.add_argument(
        "--request",
        type=int,
        default=11,
        metavar="N",
        help="which recorded request to repeat (see repro_a_filename_only.py --list); default 11",
    )
    p.add_argument("--repeat", type=int, default=5, help="how many times to send it (default 5)")
    p.add_argument(
        "--replay-all",
        action="store_true",
        help="instead: send all 47 recorded requests with their recorded start times (agent-like load)",
    )
    p.add_argument("--model", default=None, help="replay against another served model name")
    p.add_argument("--timeout", type=float, default=600)
    args = p.parse_args()

    model, requests = load_requests()
    if args.model:
        model = args.model
        for e in requests:
            e["body"]["model"] = model

    preflight(args.base_url, model)
    print("short probes (must pass, otherwise the server itself is broken):")
    if not short_probes(args.base_url, model):
        sys.exit(EXIT_CANNOT_RUN)

    times: list[float] = []
    bad = False
    if args.replay_all:
        print(f"\nreplaying all {len(requests)} recorded requests with their recorded timing:")
        t0 = time.time()

        def one(e):
            dt, resp, err = chat(args.base_url, e["body"], args.timeout)
            flag = "  <-- over 300 s" if dt > 300 else ""
            print(
                f"  #{e['n']:02d} {dt:6.1f}s {'ERROR ' + err if resp is None else 'ok'}{flag}",
                flush=True,
            )
            return dt, resp is None

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futs = []
            for e in requests:
                delay = e["offset_s"] - (time.time() - t0)
                if delay > 0:
                    time.sleep(delay)
                futs.append(pool.submit(one, e))
            for f in concurrent.futures.as_completed(futs):
                dt, err = f.result()
                times.append(dt)
                bad |= err or dt > 300
    else:
        target = next((e for e in final_answer_requests(requests) if e["n"] == args.request), None)
        if target is None:
            die(f"CANNOT RUN: no final-answer request #{args.request}")
        print(f"\nsending recorded request #{target['n']} {args.repeat} times:")
        for i in range(args.repeat):
            dt, resp, err = chat(args.base_url, target["body"], args.timeout)
            times.append(dt)
            print(
                f"  repetition {i + 1}: {dt:6.1f}s {'ERROR ' + err if resp is None else ''}",
                flush=True,
            )
            bad |= resp is None or dt > 300
            if i < args.repeat - 1:
                short_probes(args.base_url, model)
        if len(times) > 1 and times[-1] > 3 * times[0]:
            bad = True

    print(f"\nlatency series: {' -> '.join(f'{t:.1f}s' for t in times)}")
    if bad:
        print("REPRODUCED: latency grew, exceeded 300 s, or a request errored/timed out")
        return EXIT_REPRODUCED
    print("clean: latency stayed flat")
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
