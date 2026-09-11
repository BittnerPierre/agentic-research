#!/usr/bin/env python3
"""Inventaire du fonds (mode fichiers) sans le lire dans le contexte du modèle.

Pour chaque fichier de fonds/ : taille (lignes, mots), titres de sections avec
leur numéro de ligne, et, si des mots-clés sont donnés, le nombre d'occurrences
par fichier. Sert au cadrage (plan de délégation) et à la bibliographie.

Usage : python3 scripts/inventory.py [--fonds fonds] [--keywords mot1 mot2 ...] [--max-headings 12]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fonds", default="fonds")
    p.add_argument("--keywords", nargs="*", default=[])
    p.add_argument("--max-headings", type=int, default=12)
    args = p.parse_args()
    fonds = Path(args.fonds)
    files = sorted(
        f
        for f in fonds.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name != "catalogue.md"
    )
    print(f"# Inventaire de {fonds} — {len(files)} fichiers\n")
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        print(f"## {f.name} — {len(lines)} lignes, {len(text.split())} mots")
        heads = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.match(r"^#{1,4}\s+\S", l)]
        for i, h in heads[: args.max_headings]:
            print(f"  L{i}: {h[:90]}")
        if len(heads) > args.max_headings:
            print(f"  … {len(heads) - args.max_headings} autres titres")
        if args.keywords:
            low = text.lower()
            hits = {k: low.count(k.lower()) for k in args.keywords}
            print(
                "  mots-clés : " + ", ".join(f"{k}={v}" for k, v in hits.items() if v)
                or "  mots-clés : aucun"
            )
        print()


if __name__ == "__main__":
    main()
