#!/usr/bin/env python3
"""Matérialise des extraits VERBATIM à partir de plages de lignes (mode fichiers) ou de
texte collé (mode dataprep), et les ajoute à un fichier parts/Q<n>.jsonl.

Le modèle ne recopie plus le texte : il désigne les lignes, le script copie
exactement ce qui est dans le fichier (aucune erreur de transcription, aucun
token de sortie dépensé pour le texte).

Usage :
  # mode fichiers : une ou plusieurs plages « fichier:debut-fin » (lignes 1-indexées, incluses)
  python3 scripts/extract.py --part 03-extraits/parts/Q2.jsonl --question Q2 --start-id 31 \
      --range Ketogenic_diet.md:120-126 --range Agents_1.md:40-44
  # rechercher d'abord des passages : --find "mot ou expression" [--file F] affiche fichier:lignes + contexte
  python3 scripts/extract.py --find "operating cash flow" --context 2
  # mode dataprep : texte collé tel que renvoyé par vector_search, avec son chunk_id
  python3 scripts/extract.py --part 03-extraits/parts/Q2.jsonl --question Q2 --start-id 31 \
      --chunk doc_x.md:12 --file x.md --text "…texte exact…"
Les identifiants sont attribués à partir de --start-id (ou du dernier id du fichier + 1).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def find(fonds: Path, needle: str, only: str | None, context: int) -> None:
    pat = re.compile(re.escape(needle), re.I)
    for f in sorted(fonds.iterdir()):
        if not f.is_file() or f.name.startswith(".") or (only and f.name != only):
            continue
        lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            if pat.search(line):
                a, b = max(1, i - context), min(len(lines), i + context)
                print(f"--- {f.name}:{a}-{b} (hit L{i})")
                for j in range(a, b + 1):
                    print(f"{j:5d}| {lines[j - 1][:200]}")


def next_id(part: Path) -> int:
    last = 0
    if part.is_file():
        for line in part.read_text(encoding="utf-8").splitlines():
            m = re.search(r'"id"\s*:\s*"E(\d+)"', line)
            if m:
                last = max(last, int(m.group(1)))
    return last + 1


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fonds", default="fonds")
    p.add_argument("--find")
    p.add_argument("--file", help="restreindre --find à ce fichier / nom de fichier pour --text")
    p.add_argument("--context", type=int, default=1)
    p.add_argument("--part")
    p.add_argument("--question", default="")
    p.add_argument("--start-id", type=int)
    p.add_argument("--range", action="append", default=[], help="fichier:debut-fin")
    p.add_argument("--chunk", help="mode dataprep : chunk_id")
    p.add_argument("--text", help="mode dataprep : texte exact du morceau (ou passage contigu)")
    p.add_argument("--localisation", default="")
    args = p.parse_args()
    fonds = Path(args.fonds)

    if args.find:
        find(fonds, args.find, args.file, args.context)
        return
    if not args.part:
        sys.exit("--part requis pour ajouter des extraits")
    part = Path(args.part)
    part.parent.mkdir(parents=True, exist_ok=True)
    eid = args.start_id or next_id(part)
    records = []
    for spec in args.range:
        m = re.fullmatch(r"(.+?):(\d+)-(\d+)", spec)
        if not m:
            sys.exit(f"plage invalide : {spec} (attendu fichier:debut-fin)")
        fname, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        path = fonds / fname
        if not path.is_file():
            sys.exit(f"fichier introuvable dans {fonds} : {fname}")
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if not (1 <= a <= b <= len(lines)):
            sys.exit(f"plage hors fichier : {spec} ({len(lines)} lignes)")
        text = "\n".join(lines[a - 1 : b]).strip("\n")
        records.append(
            {
                "id": f"E{eid}",
                "fichier": fname,
                "texte": text,
                "localisation": f"L{a}-{b}",
                "question": args.question,
            }
        )
        eid += 1
    if args.text:
        if not args.file:
            sys.exit("--file requis avec --text (nom du fichier source renvoyé par l'outil)")
        rec = {
            "id": f"E{eid}",
            "fichier": args.file,
            "texte": args.text,
            "localisation": args.localisation,
            "question": args.question,
        }
        if args.chunk:
            rec["chunk_id"] = args.chunk
        records.append(rec)
        eid += 1
    if not records:
        sys.exit("rien à ajouter (--range ou --text)")
    with part.open("a", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    for rec in records:
        print(
            f"{rec['id']} ← {rec['fichier']} {rec.get('localisation', '')} ({len(rec['texte'].split())} mots)"
        )


if __name__ == "__main__":
    main()
