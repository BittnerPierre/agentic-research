#!/usr/bin/env python3
"""Agrège l'usage de tokens d'un run headless à partir de events.jsonl (agent principal + sous-agents).

Le résultat final de `claude -p` (`usage`, `modelUsage`) ne compte que l'agent principal ;
`total_cost_usd` inclut les sous-agents. On reconstitue donc l'usage complet à partir des
messages assistant du flux (un enregistrement par message id, dernier état retenu), en
distinguant l'agent principal (sans parent_tool_use_id) des sous-agents.

Usage : python usage_from_events.py <workdir> [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PRICE = {
    "input": 10.0,
    "cache_create_1h": 20.0,
    "cache_create_5m": 12.5,
    "cache_read": 0.25,
    "output": 50.0,
}


STEP_MARKERS = [
    ("01_cadrage", "01-cadrage/"),
    ("02_collecte", "02-collecte/"),
    ("03_extraits", "03-extraits/"),
    ("04_analyse", "04-analyse/"),
    ("05_conception", "05-conception/"),
    ("06_redaction", "06-redaction/"),
    ("07_revision", "07-revision/"),
    ("08_livraison", "08-livraison/"),
]


def step_timeline(workdir: Path) -> dict:
    """Horodatage (relatif au premier événement) de la première écriture de chaque livrable,
    des lancements de sous-agents et de la fin — mesure où naissent durée et tours."""
    t0 = None
    first_write: dict[str, float] = {}
    turns_at: dict[str, int] = {}
    subagent_launches: list[float] = []
    turn = 0
    end = None
    for line in (workdir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = e.get("timestamp")
        if isinstance(ts, str):
            from datetime import datetime

            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = None
        if ts is None:
            continue
        t0 = ts if t0 is None else t0
        rel = ts - t0
        end = rel
        if e.get("type") == "assistant" and not e.get("parent_tool_use_id"):
            turn += 1
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") != "tool_use":
                    continue
                name = c.get("name")
                inp = c.get("input") or {}
                if name in {"Write", "Edit"}:
                    path = str(inp.get("file_path") or "")
                    for step, marker in STEP_MARKERS:
                        if marker in path and step not in first_write:
                            first_write[step] = round(rel, 1)
                            turns_at[step] = turn
                if name in {"Agent", "Task"}:
                    subagent_launches.append(round(rel, 1))
    return {
        "first_write_seconds": first_write,
        "main_turn_at_first_write": turns_at,
        "subagent_launch_seconds": subagent_launches,
        "end_seconds": round(end, 1) if end is not None else None,
        "main_turns": turn,
    }


def aggregate(workdir: Path) -> dict:
    per_msg: dict[str, tuple[bool, dict]] = {}
    rate_limits: list[dict] = []
    subagent_totals: dict[str, int] = {}  # task_progress.usage.total_tokens (cumulé par sous-agent)
    for line in (workdir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "system" and e.get("subtype") in {"task_progress", "task_notification"}:
            tid = e.get("task_id")
            tot = (e.get("usage") or {}).get("total_tokens")
            if tid and tot is not None:
                subagent_totals[tid] = max(int(tot), subagent_totals.get(tid, 0))
        if e.get("type") == "rate_limit_event":
            rate_limits.append(
                {k: v for k, v in e.items() if k not in {"type", "uuid", "session_id"}}
            )
        if e.get("type") != "assistant":
            continue
        msg = e.get("message") or {}
        usage = msg.get("usage") or {}
        mid = msg.get("id") or e.get("uuid")
        if not usage or not mid:
            continue
        per_msg[mid] = (bool(e.get("parent_tool_use_id")), usage)

    def tally(items: list[dict]) -> dict:
        out = {
            "messages": len(items),
            "input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_1h": 0,
            "cache_creation_5m": 0,
        }
        for u in items:
            out["input_tokens"] += int(u.get("input_tokens") or 0)
            out["cache_creation_input_tokens"] += int(u.get("cache_creation_input_tokens") or 0)
            out["cache_read_input_tokens"] += int(u.get("cache_read_input_tokens") or 0)
            out["output_tokens"] += int(u.get("output_tokens") or 0)
            cc = u.get("cache_creation") or {}
            out["cache_creation_1h"] += int(cc.get("ephemeral_1h_input_tokens") or 0)
            out["cache_creation_5m"] += int(cc.get("ephemeral_5m_input_tokens") or 0)
        out["total_input_side"] = (
            out["input_tokens"]
            + out["cache_creation_input_tokens"]
            + out["cache_read_input_tokens"]
        )
        out["total_tokens"] = out["total_input_side"] + out["output_tokens"]
        out["cost_usd_list_estimate"] = round(
            (
                out["input_tokens"] * PRICE["input"]
                + out["cache_creation_1h"] * PRICE["cache_create_1h"]
                + out["cache_creation_5m"] * PRICE["cache_create_5m"]
                + out["cache_read_input_tokens"] * PRICE["cache_read"]
                + out["output_tokens"] * PRICE["output"]
            )
            / 1e6,
            3,
        )
        return out

    main = tally([u for sub, u in per_msg.values() if not sub])
    subs = tally([u for sub, u in per_msg.values() if sub])
    total = tally([u for _, u in per_msg.values()])
    return {
        "main_agent": main,
        "subagents": subs,
        "subagents_total_tokens_reported": sum(subagent_totals.values()),
        "subagents_count": len(subagent_totals),
        "all_agents": total,
        "rate_limit_events": rate_limits,
        "timeline": step_timeline(workdir),
    }


if __name__ == "__main__":
    print(json.dumps(aggregate(Path(sys.argv[1])), ensure_ascii=False, indent=2))
