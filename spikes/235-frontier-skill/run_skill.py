#!/usr/bin/env python3
"""Lanceur headless du skill document-research (spike #235).

Prépare un dossier de travail isolé, y copie le package du skill, lance
`claude -p "/document-research …"` avec un allowlist d'outils et des règles de
refus (dépôt entier, autres runs), enregistre le flux d'événements et le
résultat (coût, tokens, tours, sous-agents), puis archive le dossier de travail
dans output/spike235/<name>/.

Deux bras :
  A  fichiers : le fonds est copié dans <workdir>/fonds/ (+ catalogue.md)
  B  dataprep : MCP dataprep (SSE :8001) + serveur compagnon vector_search (stdio)

Usage :
  uv run python spikes/235-frontier-skill/run_skill.py --arm A --name dev-keto-A \
      --brief spikes/235-frontier-skill/open-eval/keto/brief.md --fonds <dir> [--catalogue <file>]
  uv run python spikes/235-frontier-skill/run_skill.py --arm B --name dev-keto-B --brief <brief.md>
Plusieurs runs en parallèle : lancer plusieurs processus (les dossiers sont créés
avant le lancement pour que chacun refuse la lecture des autres).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_SRC = REPO / "skills" / "document-research"
DEFAULT_CONFIG = REPO / "configs" / "tests" / "config-qwen36-chroma-decomposed.yaml"
ARCHIVE_ROOT = REPO / "output" / "spike235"


def deny_rules(workdir: Path, runs_root: Path) -> list[str]:
    rules = [
        "WebFetch",
        "WebSearch",
        "NotebookEdit",
    ]  # Bash : seul « wc » est dans l'allowlist, le reste est refusé par défaut en -p
    targets = [str(REPO)]
    for sibling in runs_root.iterdir() if runs_root.is_dir() else []:
        if sibling.is_dir() and sibling.resolve() != workdir.resolve():
            targets.append(str(sibling))
    for target in targets:
        for tool in ("Read", "Glob", "Grep", "Edit", "Write"):
            rules.append(f"{tool}(/{target}/**)")
    return rules


def prepare_workdir(args, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.brief, workdir / "brief.md")
    skill_dst = workdir / ".claude" / "skills" / "document-research"
    shutil.copytree(SKILL_SRC, skill_dst, ignore=shutil.ignore_patterns("__pycache__"))
    (workdir / "retrieval").mkdir()
    if args.process_notes:
        shutil.copy2(args.process_notes, workdir / "process-notes.md")
    if args.arm == "A":
        fonds = workdir / "fonds"
        fonds.mkdir()
        src = Path(args.fonds)
        for path in sorted(src.iterdir()):
            if (
                path.is_file()
                and not path.name.startswith(".")
                and path.name not in {"manifest.json", "README.md"}
            ):
                shutil.copy2(path, fonds / path.name)
        if args.catalogue:
            shutil.copy2(args.catalogue, fonds / "catalogue.md")


def launch_prompt(args, workdir: Path) -> str:
    if args.arm == "A":
        mode = (
            "Mode : fichiers. Le fonds documentaire fermé est le dossier fonds/ ; "
            "fonds/catalogue.md relie les références du brief aux fichiers locaux."
        )
    else:
        mode = (
            "Mode : dataprep (MCP). Acquiers les références nommées par le brief avec "
            "download_and_store_url_tool, indexe-les dans la collection "
            f"« {args.collection} » avec upload_files_to_vectorstore_tool, puis interroge cette "
            "collection avec vector_search (serveur dataprep_search). Aucun accès direct aux fichiers "
            "de la base : le fonds n'est accessible que par ces outils."
        )
    budget = (
        f"Budget DUR : {args.max_budget_usd:.2f} $ au prix liste (le harnais coupe le run au-delà : "
        f"tout ce qui n'est pas livré est perdu), {args.max_turns} tours maximum du responsable "
        "(vise 12), cible de durée < 4 minutes : sous-agents en parallèle, sorties compactes, "
        "aucune lecture intégrale du fonds par le responsable."
    )
    if args.subagent_model:
        budget += f" Modèle autorisé pour les extracteurs : {args.subagent_model} (relecteur et responsable : modèle principal)."
    return (
        f"/document-research {mode} Dossier de travail : {workdir} (répertoire courant). "
        "Brief : brief.md. Exécute les 8 étapes jusqu'à la livraison (08-livraison/rapport.md) "
        "sans demander de confirmation : aucun humain ne lit la conversation, seulement les "
        f"livrables. {budget} Livrables intermédiaires et journal en français ; le rapport final "
        "suit le brief (langue, sections, longueur, ton)."
    )


def mcp_config(args, workdir: Path) -> str:
    return json.dumps(
        {
            "mcpServers": {
                "dataprep": {"type": "sse", "url": f"http://{args.dataprep_host}:8001/sse"},
                "dataprep_search": {
                    "type": "stdio",
                    "command": "uv",
                    "args": [
                        "run",
                        "--directory",
                        str(REPO),
                        "python",
                        str(SKILL_SRC / "mcp" / "dataprep_search_server.py"),
                        "--config",
                        str(args.config),
                    ],
                    "env": {"DR_CHUNK_REGISTRY": str(workdir / "retrieval" / "chunks.jsonl")},
                },
            }
        }
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--name", required=True, help="nom du run (= output_dir du pack)")
    p.add_argument("--brief", required=True)
    p.add_argument("--fonds", help="bras A : dossier des fichiers du fonds")
    p.add_argument("--catalogue", help="bras A : catalogue.md (référence du brief → fichier)")
    p.add_argument("--collection", help="bras B : nom de la collection (défaut : nom du run)")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="bras B : config dataprep")
    p.add_argument("--dataprep-host", default="localhost")
    p.add_argument("--model", default="claude-fable-5-1")
    p.add_argument(
        "--max-budget-usd", type=float, default=5.0, help="plafond DUR (campagne 5 $, essai 1 $)"
    )
    p.add_argument(
        "--max-turns", type=int, default=40, help="tours du responsable (le skill vise ≤ 12)"
    )
    p.add_argument(
        "--effort", default=None, help="niveau d'effort du harnais (low|medium|high|xhigh|max)"
    )
    p.add_argument(
        "--subagent-model",
        default=None,
        help="modèle autorisé pour les extracteurs (défaut : même modèle)",
    )
    p.add_argument("--process-notes", help="retex de processus d'un run précédent (optionnel)")
    p.add_argument("--runs-root", default=os.environ.get("DR_RUNS_ROOT", ""))
    p.add_argument(
        "--dry-run", action="store_true", help="prépare et affiche la commande sans lancer"
    )
    args = p.parse_args()
    if args.arm == "A" and not args.fonds:
        p.error("--fonds est requis pour le bras A")
    args.collection = args.collection or args.name
    runs_root = Path(
        args.runs_root or (REPO / "output" / "spike235-work")
    ).resolve()  # hors dépôt git (output/ ignoré)
    runs_root.mkdir(parents=True, exist_ok=True)
    workdir = runs_root / args.name
    if workdir.exists():
        sys.exit(f"le dossier de travail existe déjà : {workdir}")
    if not args.dry_run:
        prepare_workdir(args, workdir)

    allowed = [
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "Agent",
        "Skill",
        "TodoWrite",
        "Task",
        "Bash(wc *)",
    ]
    if args.arm == "B":
        allowed += ["mcp__dataprep", "mcp__dataprep_search"]
    settings = {"permissions": {"deny": deny_rules(workdir, runs_root)}}
    cmd = [
        "claude",
        "-p",
        launch_prompt(args, workdir),
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        args.model,
        "--max-budget-usd",
        str(args.max_budget_usd),
        "--max-turns",
        str(args.max_turns),
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        *allowed,
        "--settings",
        json.dumps(settings),
        "--setting-sources",
        "project",
    ]
    if args.arm == "B":
        cmd += ["--mcp-config", mcp_config(args, workdir), "--strict-mcp-config"]
    if args.effort:
        cmd += ["--effort", args.effort]
    if args.dry_run:
        print(json.dumps(cmd, ensure_ascii=False, indent=1))
        return
    (workdir / "launch.json").write_text(
        json.dumps(
            {"cmd": cmd, "arm": args.arm, "name": args.name, "model": args.model},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    env = {
        k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"
    }  # abonnement, pas la clé
    env.pop("CLAUDECODE", None)  # autorise le lancement depuis une session Claude Code
    t0 = time.time()
    with (
        (workdir / "events.jsonl").open("w", encoding="utf-8") as events,
        (workdir / "stderr.txt").open("w", encoding="utf-8") as err,
    ):
        proc = subprocess.run(cmd, cwd=workdir, stdout=events, stderr=err, env=env)
    wall = time.time() - t0

    result = None
    for line in (workdir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "result":
            result = evt
    meta = {
        "name": args.name,
        "arm": args.arm,
        "model": args.model,
        "wall_seconds": round(wall, 1),
        "returncode": proc.returncode,
        "result": result,
        "collection": args.collection if args.arm == "B" else None,
        "effort": args.effort,
        "subagent_model": args.subagent_model,
        "max_budget_usd": args.max_budget_usd,
        "max_turns": args.max_turns,
    }
    (workdir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    archive = ARCHIVE_ROOT / args.name
    if archive.exists():
        shutil.rmtree(archive)
    shutil.copytree(workdir, archive, symlinks=True)
    cost = (result or {}).get("total_cost_usd")
    turns = (result or {}).get("num_turns")
    print(f"[{args.name}] rc={proc.returncode} wall={wall:.0f}s cost_usd_list={cost} turns={turns}")
    print(f"[{args.name}] workdir={workdir} archive={archive}")
    if not (workdir / "08-livraison" / "rapport.md").is_file():
        print(f"[{args.name}] ATTENTION : pas de 08-livraison/rapport.md")
    if (workdir / "ARBITRAGE-REQUIS.md").is_file():
        print(f"[{args.name}] ARBITRAGE-REQUIS.md présent")


if __name__ == "__main__":
    main()
