"""Shared helpers for the two reproduction scripts. Stdlib only."""

import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BARE_FILENAME = re.compile(r"[A-Za-z0-9_.\-]+\.txt")
EXIT_CLEAN, EXIT_REPRODUCED, EXIT_CANNOT_RUN = 0, 1, 2


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(EXIT_CANNOT_RUN)


def load_requests(path: Path | None = None) -> tuple[str, list[dict]]:
    """Return (model name, recorded requests). Each request: n, body, final_turn."""
    path = path or Path(__file__).parent / "payloads.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        bundle = json.load(f)
    return bundle["model"], bundle["requests"]


def final_answer_requests(requests: list[dict]) -> list[dict]:
    """The recorded requests whose reply must be exactly a filename."""
    out = []
    for e in requests:
        tools = {t.get("function", {}).get("name") for t in e["body"].get("tools") or []}
        if e.get("final_turn") and "vector_search" in tools:
            out.append(e)
    return out


def describe(entry: dict) -> str:
    body = entry["body"]
    n_msgs = len(body.get("messages", []))
    size_kb = len(json.dumps(body)) // 1024
    user = next((m["content"] for m in body["messages"] if m.get("role") == "user"), "")
    topic = user.replace("Terme de recherche:", "").strip()[:60]
    return f"#{entry['n']:02d}  {n_msgs} messages, {size_kb} KB  — search: {topic}"


def http_json(url: str, body: dict | None, timeout: float):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def preflight(base_url: str, model: str) -> None:
    """Abort (exit 2) unless the server answers and serves `model`."""
    try:
        served = [m["id"] for m in http_json(base_url.rstrip("/") + "/models", None, 15)["data"]]
    except Exception as e:
        die(
            f"CANNOT RUN: {base_url} is not reachable ({type(e).__name__}: {e}). "
            f"Point --base-url at a running vLLM server, e.g. http://spark1:8000/v1"
        )
    if model not in served:
        die(
            f"CANNOT RUN: the server serves {served}, not '{model}'. "
            f"Use --model to replay against one of them."
        )
    print(f"server OK: {base_url} serves {model}")


def chat(base_url: str, body: dict, timeout: float) -> tuple[float, dict | None, str]:
    """POST /chat/completions. Returns (seconds, response or None, error text)."""
    t0 = time.time()
    try:
        resp = http_json(base_url.rstrip("/") + "/chat/completions", body, timeout)
        return time.time() - t0, resp, ""
    except urllib.error.HTTPError as e:
        return time.time() - t0, None, f"HTTP {e.code}: {e.read()[:200]!r}"
    except Exception as e:
        return time.time() - t0, None, f"{type(e).__name__}: {e}"


def reply_text(resp: dict) -> str:
    return (resp["choices"][0]["message"].get("content") or "").strip()


def short_probes(base_url: str, model: str) -> bool:
    """Two tiny requests. They must work; if they fail the server is broken and
    the test cannot run. If they pass while the long requests fail, the failure
    is specific to the long tool-call context. Returns True if both pass."""
    probes = [
        ("short probe 'reply pong'", "Reply with exactly: pong", None),
        (
            "short probe 'filename only'",
            "You saved a file named probe.txt. Reply with exactly the filename and nothing else.",
            "probe.txt",
        ),
    ]
    ok = True
    for label, prompt, expect in probes:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 1.0,
            "top_p": 0.95,
        }
        dt, resp, err = chat(base_url, body, 60)
        if resp is None:
            print(f"  {label}: ERROR {err}")
            ok = False
            continue
        text = reply_text(resp)
        good = bool(text) if expect is None else text == expect
        ok &= good
        print(f"  {label}: {dt:4.1f}s {'ok' if good else 'WRONG'}  {text[:50]!r}")
    return ok
