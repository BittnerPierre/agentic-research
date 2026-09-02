#!/usr/bin/env python3
"""Crée la config de campagne d'un NOUVEAU modèle à partir d'un gabarit existant.

Le fichier produit est fonctionnel mais générique : la température, top_p et
le reasoning_effort doivent ensuite être alignés sur la model card du modèle
(c'est signalé en tête du fichier généré). Refuse d'écraser une config
existante et avertit si le modèle partage la famille d'un juge sémantique
épinglé (candidat refusé au conceptuel).

Usage:
    uv run python evaluations/campaign/scripts/new_model_config.py \
        --slug mon-modele \
        --model "openai/org/Mon-Modele-7B" \
        [--base-url http://spark1:8000/v1]   # omis = cloud OpenAI
        [--from configs/tests/config-qwen36-chroma-decomposed.yaml]

Produit : configs/tests/config-<slug>-chroma-decomposed.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIGS = ROOT / "configs" / "tests"
SPARK_TEMPLATE = CONFIGS / "config-qwen36-chroma-decomposed.yaml"
CLOUD_TEMPLATE = CONFIGS / "config-gpt54-chroma-decomposed.yaml"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_models import judge_families, model_family  # noqa: E402


def create_config(
    slug: str,
    model: str,
    base_url: str | None = None,
    template: Path | None = None,
    configs_dir: Path | None = None,
) -> Path:
    """Écrit la config du nouveau modèle et retourne son chemin.

    Lève FileExistsError si la cible existe (jamais d'écrasement) et
    FileNotFoundError si le gabarit manque.
    """
    configs_dir = configs_dir or CONFIGS
    target = configs_dir / f"config-{slug}-chroma-decomposed.yaml"
    if target.exists():
        raise FileExistsError(f"{target} existe déjà (choisir un autre --slug)")
    if template is None:
        template = SPARK_TEMPLATE if base_url else CLOUD_TEMPLATE
    if not template.is_file():
        raise FileNotFoundError(f"gabarit introuvable : {template}")

    data = yaml.safe_load(template.read_text())
    data["config_name"] = f"{slug}-decomposed"
    for role, spec in list((data.get("models") or {}).items()):
        if not isinstance(spec, dict):
            data["models"][role] = spec = {"name": spec}
        spec["name"] = model
        if base_url:
            spec["base_url"] = base_url
            spec.setdefault("api_key", "dummy")
        else:
            spec.pop("base_url", None)
            spec.pop("api_key", None)

    header = (
        f"# Config de campagne générée par new_model_config.py depuis {template.name}.\n"
        f"# À FAIRE avant la première batterie : aligner temperature/top_p/reasoning_effort\n"
        f"# sur la model card du modèle (le gabarit porte les réglages d'un AUTRE modèle).\n"
    )
    target.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help="slug du fichier/tag (ex: qwen4)")
    parser.add_argument("--model", required=True, help="nom du modèle servi (ex: openai/org/Model)")
    parser.add_argument(
        "--base-url", default=None, help="endpoint OpenAI-compatible ; omis = cloud"
    )
    parser.add_argument("--from", dest="template", default=None, help="config gabarit à copier")
    args = parser.parse_args()

    try:
        target = create_config(
            args.slug,
            args.model,
            base_url=args.base_url,
            template=Path(args.template) if args.template else None,
        )
    except (FileExistsError, FileNotFoundError) as exc:
        print(f"refus : {exc}")
        return 1
    print(f"créé : {target.relative_to(ROOT)}")

    for family, exo in judge_families().items():
        if model_family(args.model) == family:
            print(
                f"⚠ {args.model} partage la famille du juge de {exo} : candidat REFUSÉ au conceptuel"
            )
    print("Rappel : vérifier les services avec check_services.sh avant la batterie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
