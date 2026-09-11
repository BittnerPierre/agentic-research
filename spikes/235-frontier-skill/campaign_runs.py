#!/usr/bin/env python3
"""Batterie de runs du skill pour un exercice et un bras (spike #235).

Lance N runs EN PARALLÈLE (mesure du débit), attend, applique l'adaptateur banc
à chacun, et écrit un résumé de batterie. Ne note rien : la correction se fait
ensuite avec le protocole du skill benchmark-campaign (deterministic_grade,
seconde lecture, compile_table).

Usage :
  uv run python spikes/235-frontier-skill/campaign_runs.py --exercise ai-capex-intensity \
      --arm A --tag camp-fable-skillA --n 5 [--parallel 5]
Noms des runs : <tag>-<capex|concept>-<i> (compatibles compile_table.py).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
KIND = {"ai-capex-intensity": "capex", "ai-engineering-syllabus": "concept"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--exercise", required=True, choices=sorted(KIND))
    p.add_argument("--arm", required=True, choices=["A", "B"])
    p.add_argument("--tag", required=True)
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--parallel", type=int, default=5)
    p.add_argument("--start", type=int, default=1, help="premier indice de run")
    p.add_argument("--model", default="claude-fable-5-1")
    p.add_argument("--max-budget-usd", type=float, default=5.0)
    p.add_argument("--effort", default=None)
    p.add_argument("--subagent-model", default=None)
    p.add_argument("--max-turns", type=int, default=150)
    p.add_argument(
        "--config", default=str(REPO / "configs/tests/config-qwen36-chroma-decomposed.yaml")
    )
    p.add_argument("--runs-root", default=os.environ.get("DR_RUNS_ROOT", ""))
    args = p.parse_args()

    exercise = REPO / "evaluations" / "exercises" / args.exercise
    syllabus = exercise / "syllabus.md"
    corpus = exercise / "corpus"
    kind = KIND[args.exercise]
    summaries = REPO / "benchmarks" / "summaries"
    summaries.mkdir(parents=True, exist_ok=True)
    catalogue = summaries / f"{args.tag}-{kind}.catalogue.md"
    if args.arm == "A":
        cmd = [
            sys.executable,
            str(HERE / "make_catalogue.py"),
            "--brief",
            str(syllabus),
            "--fonds",
            str(corpus),
            "--out",
            str(catalogue),
        ]
        if (exercise / "source_manifest.yaml").is_file():
            cmd += ["--manifest", str(exercise / "source_manifest.yaml")]
        subprocess.run(cmd, check=True)

    names = [f"{args.tag}-{kind}-{i}" for i in range(args.start, args.start + args.n)]
    batch_t0 = time.time()
    procs: list[tuple[str, subprocess.Popen]] = []
    results: dict[str, dict] = {}
    pending = list(names)
    while pending or procs:
        while pending and len(procs) < args.parallel:
            name = pending.pop(0)
            cmd = [
                sys.executable,
                str(HERE / "run_skill.py"),
                "--arm",
                args.arm,
                "--name",
                name,
                "--brief",
                str(syllabus),
                "--model",
                args.model,
                "--max-budget-usd",
                str(args.max_budget_usd),
                "--config",
                args.config,
                "--max-turns",
                str(args.max_turns),
            ]
            if args.effort:
                cmd += ["--effort", args.effort]
            if args.subagent_model:
                cmd += ["--subagent-model", args.subagent_model]
            if args.runs_root:
                cmd += ["--runs-root", args.runs_root]
            if args.arm == "A":
                cmd += ["--fonds", str(corpus), "--catalogue", str(catalogue)]
            log = (summaries / f"{name}.skill.log").open("w")
            procs.append(
                (name, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=REPO))
            )
            print(f"[batch] lancé {name} ({len(procs)} en cours)", flush=True)
            time.sleep(2)
        for name, proc in list(procs):
            if proc.poll() is not None:
                procs.remove((name, proc))
                results[name] = {"returncode": proc.returncode, "ended_at": time.time() - batch_t0}
                print(
                    f"[batch] fini {name} rc={proc.returncode} à t+{results[name]['ended_at']:.0f}s",
                    flush=True,
                )
        time.sleep(5)
    batch_wall = time.time() - batch_t0

    packs = {}
    for name in names:
        workdir = REPO / "output" / "spike235" / name
        if not workdir.is_dir():
            packs[name] = None
            continue
        cmd = [
            sys.executable,
            str(HERE / "pack_adapter.py"),
            "--workdir",
            str(workdir),
            "--request",
            str(syllabus),
            "--arm",
            args.arm,
            "--run-name",
            name,
        ]
        if args.arm == "B":
            cmd += ["--config", args.config]
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
        print(out.stdout, out.stderr[-500:] if out.returncode else "", flush=True)
        packs[name] = (
            out.stdout.splitlines()[0].replace("pack: ", "")
            if out.stdout.startswith("pack:")
            else None
        )
    summary = {
        "tag": args.tag,
        "exercise": args.exercise,
        "arm": args.arm,
        "n": args.n,
        "parallel": args.parallel,
        "model": args.model,
        "batch_wall_seconds": round(batch_wall, 1),
        "throughput_runs_per_hour": round(3600 * args.n / batch_wall, 2) if batch_wall else None,
        "runs": results,
        "packs": packs,
    }
    path = summaries / f"{args.tag}-{kind}_skill_batch.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[batch] terminé : {args.n} runs en {batch_wall:.0f}s (parallèle {args.parallel}) → {path}"
    )


if __name__ == "__main__":
    main()
