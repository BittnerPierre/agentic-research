#!/usr/bin/env python3
"""Liste les modèles supportés par la campagne = les configs présentes dans configs/tests/.

Pour chaque config de campagne : modèle(s) servi(s), endpoint (Spark/cloud),
embeddings, et avertissement si le modèle partage la famille d'un juge
sémantique épinglé (un tel candidat est refusé au conceptuel par le garde
anti-auto-notation — « semantic judge is also a candidate model »).

Usage:
    uv run python evaluations/campaign/scripts/list_models.py [--services] [--spark] [--config <cfg>]

    --services : enchaîne le pré-vol check_services.sh après la liste
    --spark    : passé au pré-vol (exige vLLM spark1:8000)
    --config   : config de campagne visée, transmise au pré-vol (contrôle de conformité)
"""

from __future__ import annotations

import argparse
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


def is_campaign_config(data: dict) -> bool:
    """Invariants du contrat de campagne (revue #210, finding 4) : les configs
    historiques (dgx-remote, essais divers) ont un bloc models mais ne satisfont
    pas le protocole — deep_manager, writer décomposé, retrieval chroma."""
    return (
        isinstance(data.get("models"), dict)
        and bool(data.get("models"))
        and str((data.get("manager") or {}).get("default_manager") or "") == "deep_manager"
        and str((data.get("agents") or {}).get("writer_strategy") or "") == "decomposed"
        and str((data.get("vector_search") or {}).get("provider") or "") == "chroma"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--services", action="store_true", help="enchaîne le pré-vol check_services.sh"
    )
    parser.add_argument(
        "--spark", action="store_true", help="pré-vol : exige aussi vLLM spark1:8000"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="config de campagne visée : transmise au pré-vol pour le contrôle de conformité",
    )
    args = parser.parse_args()

    judges = judge_families()
    rows = []
    skipped: list[str] = []
    for cfg_file in sorted(CONFIGS.glob("config-*.yaml")):
        try:
            data = yaml.safe_load(cfg_file.read_text()) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data.get("models"), dict) or not data.get("models"):
            continue  # pas une config de modèles du tout
        if not is_campaign_config(data):
            skipped.append(cfg_file.name)
            continue
        models_cfg = data["models"]
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
    if skipped:
        print(
            f"\n({len(skipped)} configs ignorées, hors contrat campagne — deep_manager + "
            f"writer decomposed + chroma requis : {', '.join(skipped)})"
        )
    print(
        "\nNouveau modèle : uv run python evaluations/campaign/scripts/new_model_config.py --help"
    )

    if args.services:
        print("\nPré-vol des services :")
        cmd = [str(CHECK_SERVICES)]
        if args.spark:
            cmd.append("--spark")
        if args.config:
            cmd += ["--config", args.config]
        return subprocess.call(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
