#!/usr/bin/env python3
"""Re-notation autoritaire des packs archivés + garde-fous d'évaluateur.

À lancer APRÈS toute modification de l'évaluateur (deterministic_grade,
semantic_judge, answer keys). Ne relance JAMAIS les candidats : les packs de
preuves sont re-corrigeables à jamais — c'est la propriété clé du dispositif.

Usage:
    uv run python evaluations/campaign/scripts/regrade.py \
        --prefixes camp-mistral camp-56sol [--skip-judge] [--control-only]

Garde-fous exécutés systématiquement AVANT la re-notation :
1. Suite de tests complète (uv run pytest) — rouge = on s'arrête.
2. CONTRÔLE FALSIFIÉ (evaluations/controls/fabricated_report.md) : le rapport
   piégé doit rester bloqué à EXACTEMENT 2 fabrications. S'il passe à 1, le
   dernier « fix » vient de blanchir un chiffre inventé (déjà arrivé deux
   fois : un 137 via ratio de marges, un 210.5 via paire fortuite).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from glob import glob
from pathlib import Path

CONTROL_REPORT = "evaluations/controls/fabricated_report.md"
CONTROL_EXPECTED_FABS = 3  # 88.7, 137, 210.5 — les trois chiffres plantés


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def check_suite() -> bool:
    r = run(["uv", "run", "pytest", "-q"])
    ok = " failed" not in r.stdout and "error" not in r.stdout.lower()
    print(("✓" if ok else "✗") + " suite de tests :", r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    return ok


def check_control() -> bool:
    # Hôte ÉPINGLÉ dans le repo : le résultat du contrôle dépend des sources
    # de l'hôte (résolution des citations [Sx]) — un hôte flottant rendait le
    # verdict non déterministe (2 vs 3 selon le run choisi).
    host_run = "evaluations/controls/host_run"
    if not Path(host_run, "sources.json").is_file() or not Path(CONTROL_REPORT).is_file():
        print("✗ contrôle falsifié : rapport ou hôte épinglé introuvable")
        return False
    r = run([
        "uv", "run", "python", "-m", "evaluations.deterministic_grade", host_run,
        "--exercise", "evaluations/exercises/ai-capex-intensity",
        "--report", CONTROL_REPORT, "--skip-semantic-judge",
    ])
    m = re.search(r"ZERO TOL\): (\d+)", r.stdout)
    fabs = int(m.group(1)) if m else -1
    ok = fabs == CONTROL_EXPECTED_FABS
    print(("✓" if ok else "✗") + f" contrôle falsifié : {fabs} fabrications attrapées (attendu {CONTROL_EXPECTED_FABS})")
    if not ok:
        print("  → un garde vient probablement de blanchir un chiffre inventé. NE PAS re-noter avant d'avoir compris.")
    return ok


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prefixes", nargs="*", default=[], help="préfixes output_dir à re-noter (ex: camp-mistral)")
    p.add_argument("--skip-judge", action="store_true")
    p.add_argument("--control-only", action="store_true")
    args = p.parse_args()

    if not check_suite() or not check_control():
        sys.exit(1)
    if args.control_only:
        return

    for sp in sorted(glob("benchmarks/runs/*/stats.json")):
        try:
            stats = json.load(open(sp))
        except Exception:
            continue
        name = Path((stats.get("output_dir") or "").rstrip("/")).name
        if not any(name.startswith(pref) for pref in args.prefixes):
            continue
        run_dir = str(Path(sp).parent)
        ex = "ai-engineering-syllabus" if "concept" in name else "ai-capex-intensity"
        cmd = ["uv", "run", "python", "-m", "evaluations.deterministic_grade", run_dir,
               "--exercise", f"evaluations/exercises/{ex}"]
        if args.skip_judge:
            cmd.append("--skip-semantic-judge")
        r = run(cmd)
        d = json.load(open(f"{run_dir}/det_grade.json"))
        fab = d["fabrication"]["count"]
        wrong = d["accuracy"]["wrong"]
        cov = d["coverage"]
        print(f"{name:30} score={d['score']:5} cov={cov['hit']}/{cov['total']} fab={fab} wrong={wrong}")


if __name__ == "__main__":
    main()
