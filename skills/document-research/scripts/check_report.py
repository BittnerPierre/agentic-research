#!/usr/bin/env python3
"""Vérification mécanique d'un manuscrit contre les extraits et le contrat de cadrage.

Remplace la partie non sémantique de la relecture : citations qui existent,
chiffres présents dans les extraits cités par la phrase, paragraphes factuels
sans citation, sections imposées présentes et dans l'ordre, colonnes du tableau
imposé, longueur du corps (hors « ## Sources »), URL dans le corps.

Le contrat vient de 01-cadrage/contrat.json (écrit au cadrage) :
  {"sections": ["…", …], "min_words": 1200, "max_words": 1800,
   "table_columns": ["…", …], "language": "fr"}
ou des options de ligne de commande (qui priment).

Usage : python3 scripts/check_report.py [--manuscrit 06-redaction/manuscrit.md] [--workdir .]
        [--sections … --min-words N --max-words N --columns …] [--json]
Code de sortie 1 s'il reste une anomalie bloquante (citation inconnue, chiffre sans appui, hors longueur, section manquante).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    CITE_RE,
    cited_ids,
    load_contract,
    load_parts,
    norm_ws,
    split_body,
    word_count,
)

NUM_RE = re.compile(r"\d(?:[\s\u00a0]?\d|[.,·]\d)*")


def numbers(text: str) -> set[str]:
    out = set()
    for m in NUM_RE.finditer(text):
        tok = re.sub(r"[\s\u00a0]", "", m.group(0)).replace(",", ".").replace("·", ".").strip(".")
        if tok and (len(tok) >= 2 or tok.isdigit()):
            out.add(tok)
    return out


def same_number(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return False


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", default=".")
    p.add_argument("--manuscrit", default="06-redaction/manuscrit.md")
    p.add_argument("--sections", nargs="*")
    p.add_argument("--min-words", type=int)
    p.add_argument("--max-words", type=int)
    p.add_argument("--columns", nargs="*")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    w = Path(args.workdir)
    contract = load_contract(w)
    sections = args.sections if args.sections is not None else contract.get("sections") or []
    min_w = args.min_words if args.min_words is not None else contract.get("min_words")
    max_w = args.max_words if args.max_words is not None else contract.get("max_words")
    columns = args.columns if args.columns is not None else contract.get("table_columns") or []

    text = (w / args.manuscrit).read_text(encoding="utf-8")
    body, _sources = split_body(text)
    extracts = load_parts(w)
    extracts.pop("_errors", None)
    out: dict = {"manuscrit": args.manuscrit, "words_body": word_count(body)}
    blocking: list[str] = []

    if min_w is not None and out["words_body"] < min_w:
        blocking.append(f"trop court : {out['words_body']} mots < {min_w}")
    if max_w is not None and out["words_body"] > max_w:
        blocking.append(f"trop long : {out['words_body']} mots > {max_w}")
    out["length_target"] = [min_w, max_w]

    headings = [re.sub(r"[*_`]", "", h).strip() for h in re.findall(r"(?m)^#{1,3}\s+(.+)$", body)]
    out["headings"] = headings
    if sections:
        idx = []
        for s in sections:
            i = next(
                (k for k, h in enumerate(headings) if norm_ws(s).lower() in norm_ws(h).lower()),
                None,
            )
            idx.append(i)
            if i is None:
                blocking.append(f"section manquante : {s}")
        found = [i for i in idx if i is not None]
        out["sections_in_order"] = found == sorted(found)
        if found != sorted(found):
            blocking.append("sections dans le désordre")
    if columns:
        rows = re.findall(r"(?m)^\|.*\|\s*$", body)
        want = [norm_ws(c).lower() for c in columns]
        out["table_with_columns"] = any(
            [norm_ws(c).lower() for c in r.strip("|").split("|")] == want for r in rows
        )
        if not out["table_with_columns"]:
            blocking.append("tableau imposé absent ou colonnes différentes")

    urls = re.findall(r"https?://\S+", body)
    out["urls_in_body"] = urls
    if urls:
        blocking.append(f"{len(urls)} URL dans le corps")

    cited = list(dict.fromkeys(cited_ids(body)))
    unknown = [c for c in cited if c not in extracts]
    out["n_citations"] = len(cited_ids(body))
    out["n_cited_unique"] = len(cited)
    out["unknown_citations"] = unknown
    if unknown:
        blocking.append(f"citations inconnues : {', '.join(unknown[:10])}")

    paragraphs = [
        pp
        for pp in re.split(r"\n\s*\n", body)
        if word_count(pp) >= 25 and not pp.lstrip().startswith(("#", "|"))
    ]
    out["paragraphs_without_citation"] = [
        pp.strip()[:100] for pp in paragraphs if not CITE_RE.search(pp)
    ]

    unsupported = []
    checked = 0
    for pp in re.split(r"\n\s*\n", body):
        if pp.lstrip().startswith("#"):
            continue
        units = (
            [pp] if pp.lstrip().startswith("|") else re.split(r"(?<=[.;!?])\s+(?=[A-ZÀ-Ü«(\d])", pp)
        )
        for unit in units:
            eids = list(dict.fromkeys(cited_ids(unit)))
            if not eids:
                continue
            nums = {n for n in numbers(CITE_RE.sub("", unit)) if len(n) >= 2}
            if not nums:
                continue
            hay = numbers(" ".join(str(extracts.get(e, {}).get("texte") or "") for e in eids))
            missing = sorted(n for n in nums if not any(same_number(n, h) for h in hay))
            checked += len(nums)
            if missing:
                unsupported.append(
                    {
                        "missing": missing,
                        "cites": eids,
                        "unit": norm_ws(CITE_RE.sub("", unit))[:140],
                    }
                )
    out["numbers_checked"] = checked
    out["numbers_unsupported"] = unsupported
    if unsupported:
        blocking.append(f"{len(unsupported)} phrase(s) avec chiffre absent des extraits cités")

    out["blocking"] = blocking
    out["ok"] = not blocking
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(
            f"corps : {out['words_body']} mots (cible {min_w}-{max_w}) | citations : {out['n_citations']} ({len(cited)} extraits) "
            f"| chiffres vérifiés : {checked} | paragraphes ≥25 mots sans citation : {len(out['paragraphs_without_citation'])}"
        )
        for b in blocking:
            print(f"BLOQUANT : {b}")
        for u in unsupported[:15]:
            print(f"  chiffre(s) {u['missing']} absents de {u['cites']} : « {u['unit'][:110]} »")
        for pp in out["paragraphs_without_citation"][:8]:
            print(f"  sans citation : « {pp} »")
        print("OK" if not blocking else "À CORRIGER")
    sys.exit(0 if not blocking else 1)


if __name__ == "__main__":
    main()
