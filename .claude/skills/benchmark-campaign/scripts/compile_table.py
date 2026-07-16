#!/usr/bin/env python3
"""Compile le tableau de campagne à deux dimensions : confiance + couverture.

Usage:
    uv run python .claude/skills/benchmark-campaign/scripts/compile_table.py \
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
import statistics
from glob import glob
from pathlib import Path

import yaml


def load_runs() -> dict[str, tuple[str, dict, dict]]:
    """name -> (run_dir, det_grade, stats) pour tout pack corrigé."""
    out = {}
    for sp in glob("benchmarks/runs/*/stats.json"):
        run = str(Path(sp).parent)
        try:
            stats = json.load(open(sp))
            det = json.load(open(f"{run}/det_grade.json"))
        except Exception:
            continue
        name = Path((stats.get("output_dir") or "").rstrip("/")).name
        if name:
            out[name] = (run, det, stats)
    return out


def load_adjustments() -> tuple[dict[str, dict], set[str]]:
    path = Path("evaluations/adjustments.yaml")
    if not path.is_file():
        return {}, set()
    payload = yaml.safe_load(path.read_text()) or {}
    adjustments = {a["campagne"]: a for a in payload.get("adjustments") or []}
    exclusions = {e["campagne"] for e in payload.get("exclusions") or []}
    return adjustments, exclusions


def letter(det: dict) -> str:
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
                if any(n.startswith(pat) for pat in patterns) and n not in exclusions
            )
            if not names:
                # un modèle demandé sans aucun run doit faire du BRUIT, pas
                # disparaître (Qwen a silencieusement manqué au podium).
                print(f"!! {label}: aucun run trouvé pour {prefix}-{kind}")
                continue
            letters, covs, durs, toks, flagged = [], [], [], [], []
            for n in names:
                run, det, stats = runs[n]
                let = letter(det)
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
                if let not in ("A", "A*"):
                    items = [
                        f"fab {it.get('value')} «{(it.get('context') or '')[:60]}»"
                        for it in det.get("fabrication", {}).get("items", [])[:3]
                    ] + [str(w)[:80] for w in det.get("accuracy", {}).get("wrong_details", [])[:3]]
                    flagged.append((n, items))
            key = (
                sum(le == "F" for le in letters),
                sum(le == "D" for le in letters),
                sum(le == "C" for le in letters),
                -(statistics.median(covs) if covs else 0),
            )
            rows.append((key, label, letters, covs, durs, toks, flagged))

        print(f"\n===== {title} =====")
        for i, (_k, label, letters, covs, durs, toks, flagged) in enumerate(sorted(rows), 1):
            cov_s = (
                f"{statistics.median(covs):5.1f}% ({min(covs):.0f}-{max(covs):.0f})"
                if covs
                else "?"
            )
            dur_s = f"{statistics.median(durs):5.0f}s" if durs else "?"
            tok_s = f"{statistics.median(toks) / 1000:5.0f}k" if toks else "?"
            print(f"{i}. {label:16} {' '.join(letters):16} cov {cov_s}  {dur_s}  {tok_s}")
            if args.flags:
                for n, items in flagged:
                    print(f"     ⚠ {n} :")
                    for it in items:
                        print(f"        - {it}")


if __name__ == "__main__":
    main()
