#!/usr/bin/env python3
"""Contrôle déterministe des extraits (remplace un sous-agent de vérification).

Pour chaque extrait des fichiers parts/*.jsonl : identifiant unique, texte non
vide, présence VERBATIM dans la source (mode fichiers : fichier de fonds/ ;
mode dataprep : registre retrieval/chunks.jsonl si présent, sinon « non
vérifiable »), doublons de texte entre extraits, plages d'identifiants.

Usage : python3 scripts/verify_extracts.py [--workdir .] [--fonds fonds] [--json]
Code de sortie 1 si au moins un extrait n'est pas verbatim ou si des ids sont dupliqués.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import LINK_RE, load_parts, load_registry, norm_ws


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", default=".")
    p.add_argument("--fonds", default="fonds")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    w = Path(args.workdir)
    fonds = w / args.fonds
    extracts = load_parts(w)
    errors = extracts.pop("_errors", {}).get("lines", [])
    registry = load_registry(w)
    cache: dict[str, tuple[str, str]] = {}
    report = {
        "n_extracts": len(extracts),
        "verbatim": 0,
        "normalized": 0,
        "not_verbatim": [],
        "unverifiable": [],
        "empty": [],
        "duplicates_text": [],
        "id_errors": errors,
        "by_question": {},
    }
    seen_text: dict[str, str] = {}
    for eid, rec in sorted(extracts.items(), key=lambda kv: int(kv[0][1:])):
        text = str(rec.get("texte") or "")
        q = str(rec.get("question") or "?")
        report["by_question"][q] = report["by_question"].get(q, 0) + 1
        if not text.strip():
            report["empty"].append(eid)
            continue
        key = norm_ws(text)
        if key in seen_text:
            report["duplicates_text"].append(f"{eid}={seen_text[key]}")
        else:
            seen_text[key] = eid
        cid = rec.get("chunk_id")
        if cid:
            hay = registry.get(str(cid))
            if hay is None:
                report["unverifiable"].append(f"{eid} (chunk {cid} absent du registre)")
                continue
            if text in hay:
                report["verbatim"] += 1
            elif norm_ws(text) in norm_ws(hay):
                report["normalized"] += 1
            else:
                report["not_verbatim"].append(f"{eid} (chunk {cid})")
            continue
        fname = Path(str(rec.get("fichier") or "")).name
        path = fonds / fname
        if not fname or not path.is_file():
            report["unverifiable"].append(f"{eid} (fichier {fname!r} introuvable)")
            continue
        if fname not in cache:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            cache[fname] = (raw, norm_ws(LINK_RE.sub(lambda m: m.group(1), raw)))
        raw, raw_nolinks = cache[fname]
        if text in raw:
            report["verbatim"] += 1
        elif (
            norm_ws(text) in norm_ws(raw)
            or norm_ws(LINK_RE.sub(lambda m: m.group(1), text)) in raw_nolinks
        ):
            report["normalized"] += 1
        else:
            report["not_verbatim"].append(f"{eid} ({fname})")
    ok = not report["not_verbatim"] and not report["id_errors"] and not report["empty"]
    report["ok"] = ok
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(
            f"extraits : {report['n_extracts']} | verbatim : {report['verbatim']} | normalisés (espaces/liens) : {report['normalized']} "
            f"| NON verbatim : {len(report['not_verbatim'])} | non vérifiables : {len(report['unverifiable'])} | vides : {len(report['empty'])}"
        )
        print(
            "par question : "
            + ", ".join(f"{q}={n}" for q, n in sorted(report["by_question"].items()))
        )
        for k in ("not_verbatim", "empty", "id_errors", "duplicates_text", "unverifiable"):
            if report[k]:
                print(f"{k} : " + "; ".join(report[k][:30]))
        print("OK" if ok else "À CORRIGER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
