#!/usr/bin/env python3
"""Vérifie le corpus gelé d'un exercice AVANT de dépenser un run modèle.

Pour chaque source du source_manifest.yaml (ou corpus/manifest.json), au moins
un fichier correspondant au file_pattern doit exister avec le sha256 attendu —
dans data/ (base de connaissances) ou dans le corpus de l'exercice. Sans ce
contrôle, un drift de corpus n'est découvert qu'APRÈS le run, par le refus
« raw chunk validation failed » de l'évaluateur (revue Codex #210, finding 3 :
un run conceptuel complet dépensé pour un hash divergent).

Usage:
    uv run python evaluations/campaign/scripts/verify_corpus.py \
        evaluations/exercises/ai-engineering-syllabus

Sort avec 0 si tout le corpus est conforme, 1 sinon (détail par fichier).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def load_manifest(exercise: Path) -> tuple[Path | None, list[dict]]:
    # Même sélection que evaluations.chunk_snapshot.load_source_manifest.
    yaml_path = exercise / "source_manifest.yaml"
    if yaml_path.is_file():
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        return yaml_path, list(data.get("sources") or [])
    json_path = exercise / "corpus" / "manifest.json"
    if json_path.is_file():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return json_path, [
            {"file_pattern": name, "sha256": sha}
            for name, sha in sorted((payload.get("generated_files") or {}).items())
        ]
    return None, []


def check_corpus(exercise: Path, roots: list[Path] | None = None) -> list[str]:
    """Retourne la liste des problèmes (vide = corpus conforme)."""
    manifest_path, sources = load_manifest(exercise)
    if manifest_path is None:
        return [f"aucun manifeste de corpus dans {exercise}"]
    if not sources:
        return [f"manifeste vide : {manifest_path}"]
    roots = roots if roots is not None else [ROOT / "data", exercise / "corpus"]
    problems: list[str] = []
    for source in sources:
        pattern = str(source.get("file_pattern") or "")
        expected = str(source.get("sha256") or "")
        if not pattern or not expected:
            problems.append(f"entrée de manifeste incomplète : {source}")
            continue
        # Les roots sont ordonnés par autorité : data/ est ce que dataprep indexe
        # réellement — s'il contient le fichier, c'est LUI qui doit être conforme
        # (une copie conforme dans corpus/ ne doit pas masquer un drift de data/).
        candidates: list[Path] = []
        for root in roots:
            candidates = [p for p in sorted(root.glob(pattern)) if p.is_file()]
            if candidates:
                break
        if not candidates:
            problems.append(
                f"{pattern} : aucun fichier trouvé (roots: {', '.join(map(str, roots))})"
            )
            continue
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in candidates}
        if expected not in hashes.values():
            found = "; ".join(f"{p.name}={h[:12]}…" for p, h in hashes.items())
            problems.append(f"{pattern} : sha256 attendu {expected[:12]}…, trouvé {found}")
    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    exercise = Path(sys.argv[1])
    problems = check_corpus(exercise)
    if problems:
        print(f"✗ corpus gelé NON conforme ({exercise.name}) — batterie à ne PAS lancer :")
        for problem in problems:
            print(f"    - {problem}")
        print("  remède : re-télécharger la source depuis l'URL du manifeste, ou re-geler le")
        print("  manifeste (décision utilisateur — le gel est le contrat de reproductibilité).")
        return 1
    print(f"✓ corpus gelé conforme ({exercise.name}, {len(load_manifest(exercise)[1])} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
