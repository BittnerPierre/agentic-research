#!/usr/bin/env python3
"""Ask one model for the dashboard: brief + its own quant report + six 10-K extracts -> one HTML.

usage: run_dashboard.py <label> <provider:model> <quant_report.md>
  provider: litellm | claude-cli
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

SPIKE = Path(__file__).resolve().parents[2]  # spikes/262-benchmark-v2-visual
REPO = SPIKE.parents[1]
BRIEF = SPIKE / "dashboard" / "brief_dashboard_v1.md"
EXTRACTS = sorted((SPIKE / "extracts_10k_fy2025").glob("*_fy2025_datacenter_extracts.md"))
OUT = SPIKE / "dashboard" / "outputs"
ENV_FILE = REPO / ".env"


def load_env():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_prompt(report_path: Path) -> str:
    brief = BRIEF.read_text(encoding="utf-8")
    brief = brief.split("---", 2)[1].strip()  # the frozen brief between the two rules
    parts = [
        brief,
        "\nReturn the complete HTML document and nothing else: no preamble, no explanation, "
        "no Markdown fences. Start with <!doctype html>.\n",
        "\n\n===== INPUT 1: QUANTITATIVE RESEARCH REPORT (Markdown) =====\n\n",
        report_path.read_text(encoding="utf-8"),
        "\n\n===== INPUT 2: QUALITATIVE 10-K EXTRACTS (six files) =====\n",
    ]
    for p in EXTRACTS:
        parts.append(f"\n\n----- FILE: {p.name} -----\n\n{p.read_text(encoding='utf-8')}")
    return "".join(parts)


def extract_html(text: str) -> str:
    m = re.search(r"<!doctype html.*?</html>", text, re.S | re.I)
    if m:
        return m.group(0)
    m = re.search(r"<html.*?</html>", text, re.S | re.I)
    return m.group(0) if m else text


def via_litellm(model: str, prompt: str) -> tuple[str, dict]:
    import litellm

    kwargs = dict(model=model, messages=[{"role": "user", "content": prompt}], timeout=1800)
    if model.startswith("openai/"):
        kwargs["max_completion_tokens"] = 60000
    else:
        kwargs["max_tokens"] = int(os.environ.get("DASH_MAX_TOKENS", "60000"))
    r = litellm.completion(**kwargs)
    u = getattr(r, "usage", None)
    usage = {
        "prompt": getattr(u, "prompt_tokens", None),
        "completion": getattr(u, "completion_tokens", None),
    }
    return r.choices[0].message.content or "", usage


def via_claude_cli(model: str, prompt: str) -> tuple[str, dict]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not (k == "CLAUDECODE" or k.startswith("CLAUDE_CODE"))
    }
    cmd = ["claude", "-p", "--model", model, "--tools", "", "--output-format", "text"]
    r = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, env=env, cwd=str(OUT), timeout=1800
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude -p exit {r.returncode}: {r.stderr[-2000:]}")
    return r.stdout, {"stderr_tail": r.stderr[-500:]}


def via_litellm_fix(model: str, prompt: str, previous: str, error: str) -> tuple[str, dict]:
    """Second turn: hand the model its own output and the exact error, ask for the full corrected file."""
    import litellm

    msgs = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": previous},
        {
            "role": "user",
            "content": "Your file does not work as delivered. Loading it in a browser gives this "
            f"JavaScript error:\n\n{error}\n\nFix the file so that it parses and runs without errors, "
            "every chart renders from the embedded data, and no table or panel overflows the viewport. "
            "Keep the content and structure. Return the complete corrected HTML document and nothing "
            "else: no preamble, no Markdown fences. Start with <!doctype html>.",
        },
    ]
    r = litellm.completion(
        model=model,
        messages=msgs,
        timeout=1800,
        max_tokens=int(os.environ.get("DASH_MAX_TOKENS", "60000")),
    )
    u = getattr(r, "usage", None)
    return r.choices[0].message.content or "", {
        "prompt": getattr(u, "prompt_tokens", None),
        "completion": getattr(u, "completion_tokens", None),
    }


def main():
    label, spec, report = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    provider, model = spec.split(":", 1)
    OUT.mkdir(exist_ok=True)
    load_env()
    if (
        provider == "fix"
    ):  # usage: run_dashboard.py <label> fix:<model> <previous.raw.txt> <prompt.txt> <error.txt>
        previous = report.read_text(encoding="utf-8")
        prompt = Path(sys.argv[4]).read_text(encoding="utf-8")
        error = Path(sys.argv[5]).read_text(encoding="utf-8")
        t0 = time.time()
        text, usage = via_litellm_fix(model, prompt, previous, error)
        dt = time.time() - t0
        (OUT / f"{label}.raw.txt").write_text(text, encoding="utf-8")
        html = extract_html(text)
        (OUT / f"{label}.html").write_text(html, encoding="utf-8")
        print(f"{label}: {dt:.0f}s, raw {len(text)} chars, html {len(html)} chars, usage {usage}")
        return
    prompt = build_prompt(report)
    (OUT / f"{label}.prompt.txt").write_text(prompt, encoding="utf-8")
    t0 = time.time()
    text, usage = (
        via_claude_cli(model, prompt) if provider == "claude-cli" else via_litellm(model, prompt)
    )
    dt = time.time() - t0
    (OUT / f"{label}.raw.txt").write_text(text, encoding="utf-8")
    html = extract_html(text)
    (OUT / f"{label}.html").write_text(html, encoding="utf-8")
    ext = sum(1 for _ in re.finditer(r"(src|href)=[\"']https?://", html))
    print(
        f"{label}: {dt:.0f}s, raw {len(text)} chars, html {len(html)} chars, external refs {ext}, usage {usage}"
    )


if __name__ == "__main__":
    main()
