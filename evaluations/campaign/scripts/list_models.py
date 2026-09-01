#!/usr/bin/env python3
"""Liste les modèles supportés par la campagne = les configs présentes dans configs/tests/.

Pour chaque config de campagne : modèle(s) servi(s), endpoint (Spark/cloud),
embeddings, et avertissement si le modèle partage la famille d'un juge
sémantique épinglé (un tel candidat est refusé au conceptuel par le garde
anti-auto-notation — « semantic judge is also a candidate model »).

Usage:
    uv run python evaluations/campaign/scripts/list_models.py [--services] [--spark]

    --services : enchaîne le pré-vol check_services.sh après la liste
    --spark    : passé au pré-vol (exige vLLM spark1:8000)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIGS = ROOT / "configs" / "tests"
EXERCISES = ROOT / "evaluations" / "exercises"
CHECK_SERVICES = Path(__file__).resolve().parent / "check_services.sh"


def model_family(model: str) -> str:
    # Réplique de evaluations.semantic_judge._model_family (garder synchronisé).
    normalized = model.strip().lower().split("@", 1)[0]
    if normalized.startswith("openai/"):
        normalized = normalized.removeprefix("openai/")
    return re.sub(r"-\d{4}-\d{2}-\d{2}$", "", normalized)


def judge_families() -> dict[str, str]:
    """famille -> exercice, pour chaque juge épinglé dans un answer_key."""
    families: dict[str, str] = {}
    for key_file in sorted(EXERCISES.glob("*/answer_key.yaml")):
        try:
            data = yaml.safe_load(key_file.read_text()) or {}
        except yaml.YAMLError:
            continue
        judge_model = str((data.get("semantic_judge") or {}).get("model") or "")
        if judge_model:
            families[model_family(judge_model)] = key_file.parent.name
    return families


def endpoint_label(spec: dict) -> str:
    base_url = str(spec.get("base_url") or "")
    if not base_url or "api.openai.com" in base_url:
        return "cloud (OpenAI)"
    return base_url


def main() -> int:
    judges = judge_families()
    rows = []
    for cfg_file in sorted(CONFIGS.glob("config-*.yaml")):
        try:
            data = yaml.safe_load(cfg_file.read_text()) or {}
        except yaml.YAMLError:
            continue
        models_cfg = data.get("models")
        if not isinstance(models_cfg, dict) or not models_cfg:
            continue  # pas une config de campagne
        specs = [s for s in models_cfg.values() if isinstance(s, dict)]
        plain = [s for s in models_cfg.values() if isinstance(s, str)]
        names = sorted({str(s.get("name") or "") for s in specs if s.get("name")} | set(plain))
        endpoints = sorted({endpoint_label(s) for s in specs}) or ["cloud (OpenAI)"]
        embeddings = str((data.get("vector_search") or {}).get("chroma_embedding_model") or "-")
        warnings = sorted(
            {
                f"famille du juge de {exo} : candidat REFUSÉ au conceptuel"
                for name in names
                for family, exo in judges.items()
                if model_family(name) == family
            }
        )
        rows.append((cfg_file.name, names, endpoints, embeddings, warnings))

    if not rows:
        print(f"aucune config de campagne trouvée dans {CONFIGS}")
        return 1

    print(f"Modèles supportés ({len(rows)} configs dans configs/tests/) :\n")
    for name, models, endpoints, embeddings, warnings in rows:
        print(f"• {name}")
        print(f"    modèle(s)  : {', '.join(models) or '-'}")
        print(f"    endpoint   : {', '.join(endpoints)}")
        print(f"    embeddings : {embeddings}")
        for warning in warnings:
            print(f"    ⚠ {warning}")
    print(
        "\nNouveau modèle : uv run python evaluations/campaign/scripts/new_model_config.py --help"
    )

    if "--services" in sys.argv:
        print("\nPré-vol des services :")
        args = [str(CHECK_SERVICES)] + (["--spark"] if "--spark" in sys.argv else [])
        return subprocess.call(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
