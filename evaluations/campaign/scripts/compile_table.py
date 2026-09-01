#!/usr/bin/env python3
"""Compile le tableau de campagne à deux dimensions : confiance + couverture.

Usage:
    uv run python evaluations/campaign/scripts/compile_table.py \
        --models "gpt-5.6-sol=camp-56sol" "Mistral=camp-mistral" [...]
        [--flags]   # affiche aussi les items accusés de chaque run non-A (seconde lecture)

Lit les packs via le mapping AUTORITAIRE stats.json→output_dir, applique les
ajustements post-examen (evaluations/adjustments.yaml), et trie le podium par
gravité (F > D > C) puis couverture — sémantique arbitrée : A propre ; C ≥1
chiffre faux (à relire) ; D une invention (récupérable en relecture attentive) ;
F inventions multiples (rapport mort).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from glob import glob
from pathlib import Path

import yaml


def load_runs() -> dict[str, tuple[str, dict, dict]]:
    """name -> (run_dir, det_grade, stats) pour tout pack corrigé."""
    out: dict[str, tuple[float, str, dict, dict]] = {}
    for sp in glob("benchmarks/runs/*/stats.json"):
        run = str(Path(sp).parent)
        try:
            stats = json.load(open(sp))
            det = json.load(open(f"{run}/det_grade.json"))
        except Exception:
            continue
        name = Path((stats.get("output_dir") or "").rstrip("/")).name
        if not name:
            continue
        mtime = Path(sp).stat().st_mtime
        if name in out:
            # règle déterministe (revue Codex #4) : le pack le plus RÉCENT
            # gagne, et le doublon fait du bruit au lieu d'un écrasement
            # silencieux dans l'ordre de glob.
            print(f"!! doublon de tag « {name} » : pack le plus récent retenu")
            if mtime <= out[name][0]:
                continue
        out[name] = (mtime, run, det, stats)
    return {k: v[1:] for k, v in out.items()}


def load_adjustments() -> tuple[dict[str, dict], set[str]]:
    path = Path("evaluations/adjustments.yaml")
    if not path.is_file():
        return {}, set()
    payload = yaml.safe_load(path.read_text()) or {}
    adjustments = {a["campagne"]: a for a in payload.get("adjustments") or []}
    exclusions = {e["campagne"] for e in payload.get("exclusions") or []}
    return adjustments, exclusions


def letter(det: dict, stats: dict) -> str:
    # E = évaluation NON ABOUTIE uniquement (revue Codex #1 + arbitrage Pierre
    # 17/07) : run mort ou validation impossible. Un échec de provenance DU
    # CANDIDAT dont l'évaluation a abouti (ex. gpt-4.1 déclarant honnêtement
    # « non trouvé » ce qu'il aurait pu trouver) n'est PAS un E : il n'a ni
    # halluciné ni publié de faux chiffre — ses erreurs vs corpus comptent
    # par le chemin normal (C/D/F). E doit rester distinguable d'un vrai
    # échec de contenu.
    verdict = (det.get("root_cause") or {}).get("verdict") or ""
    if stats.get("success") is False or verdict == "evaluation_failed":
        return "E"
    fab = det.get("fabrication", {}).get("count", 0)
    wrong = det.get("accuracy", {}).get("wrong", 0)
    if fab >= 2:
        return "F"
    if fab == 1:
        return "D"
    if wrong >= 1:
        return "C"
    return "A"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--models", nargs="+", required=True, help="Label=prefix (ex: Mistral=camp-mistral)"
    )
    p.add_argument("--flags", action="store_true", help="lister les items accusés des runs non-A")
    args = p.parse_args()

    runs = load_runs()
    adjustments, exclusions = load_adjustments()

    for kind, title in (("concept", "CONCEPTUEL"), ("capex", "FINANCE")):
        rows = []
        for spec in args.models:
            label, prefix = spec.split("=", 1)
            # alternatives acceptées ; un tag qui contient déjà le type
            # d'exercice (schéma historique bench-capex-qwen-N) est utilisé
            # tel quel, sinon on suffixe -<kind> (schéma camp-<tag>-<kind>-N)
            prefixes = prefix.split("|")
            patterns = [
                pf if kind in pf else f"{pf}-{kind}"
                for pf in prefixes
                if kind in pf or not any(k in pf for k in ("capex", "concept"))
            ]
            names = sorted(
                n
                for n in runs
                if any(re.fullmatch(re.escape(pat) + r"-?\d+", n) for pat in patterns)
                and n not in exclusions
            )
            if not names:
                # un modèle demandé sans aucun run doit faire du BRUIT, pas
                # disparaître (Qwen a silencieusement manqué au podium).
                print(f"!! {label}: aucun run trouvé pour {prefix}-{kind}")
                continue
            letters, covs, durs, toks, flagged = [], [], [], [], []
            for n in names:
                _run, det, stats = runs[n]
                let = letter(det, stats)
                adj = adjustments.get(n)
                if (
                    adj
                    and let in ("D", "F")
                    and adj.get("score_ajuste", 0) > adj.get("score_evaluateur", 0)
                ):
                    # exception post-examen EXONÉRANTE (une rectification de
                    # compte sans changement de score ne blanchit pas la lettre)
                    let = "A*"
                letters.append(let)
                cov = det.get("coverage") or {}
                if cov.get("total"):
                    covs.append(cov["hit"] / cov["total"] * 100)
                t = (stats.get("timings") or {}).get("total")
                if t:
                    durs.append(t)
                u = stats.get("usage_by_phase") or {}
                tok = sum((ph or {}).get("total_tokens", 0) for ph in u.values())
                if tok:
                    toks.append(tok)
                # revue Codex #3 : « aucun score accepté sans lire ce qui l'a
                # causé » — --flags expose le verdict de CHAQUE run (A compris),
                # les accusations numériques ET les exigences échouées.
                items = [f"verdict: {(det.get('root_cause') or {}).get('verdict')}"]
                items += [
                    f"fab {it.get('value')} «{(it.get('context') or '')[:60]}»"
                    for it in det.get("fabrication", {}).get("items", [])[:3]
                ]
                items += [str(w)[:80] for w in det.get("accuracy", {}).get("wrong_details", [])[:3]]
                failed_reqs = (det.get("root_cause") or {}).get("failed_requirements") or []
                if failed_reqs:
                    items.append(f"exigences échouées: {', '.join(failed_reqs[:5])}")
                flagged.append((n, items))
            # tri : gravité E>F>D>C puis couverture en finance ; couverture
            # SEULE en conceptuel (lettres n/a par arbitrage — un E y reste
            # visible via --flags mais ne classe pas).
            if kind == "capex":
                key = (
                    sum(le == "E" for le in letters),
                    sum(le == "F" for le in letters),
                    sum(le == "D" for le in letters),
                    sum(le == "C" for le in letters),
                    -(statistics.median(covs) if covs else 0),
                )
            else:
                key = (-(statistics.median(covs) if covs else 0),)
            rows.append((key, label, letters, covs, durs, toks, flagged))

        print(f"\n===== {title} =====")
        # Revue Codex (exécution) #6 : en conceptuel la granularité du juge est
        # de 6.25 pts (16 exigences) — deux médianes à ≤ 6.25 d'écart sont un
        # ex æquo statistique, pas un classement. Le « ≈ » le rend visible.
        prev_median = None
        for i, (_k, label, letters, covs, durs, toks, flagged) in enumerate(sorted(rows), 1):
            cov_s = (
                f"{statistics.median(covs):5.1f}% ({min(covs):.0f}-{max(covs):.0f})"
                if covs
                else "?"
            )
            dur_s = f"{statistics.median(durs):5.0f}s" if durs else "?"
            tok_s = f"{statistics.median(toks) / 1000:5.0f}k" if toks else "?"
            # Arbitrage Pierre (2026-07-17) : pas de lettres en conceptuel
            # tant qu'elles ne sont pas dérivées du juge (les lettres actuelles
            # ne comptent que les fautes numériques -> vides de sens là-bas).
            let_s = " ".join(letters) if kind == "capex" else "(lettres: n/a)"
            median = statistics.median(covs) if covs else None
            tie = (
                "≈"
                if kind == "concept"
                and None not in (median, prev_median)
                and abs(prev_median - median) <= 6.25
                else " "
            )
            prev_median = median
            print(f"{i}.{tie}{label:16} {let_s:16} cov {cov_s}  {dur_s}  {tok_s}")
            if args.flags:
                for n, items in flagged:
                    print(f"     ⚠ {n} :")
                    for it in items:
                        print(f"        - {it}")


if __name__ == "__main__":
    main()
