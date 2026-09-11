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
  # mode dataprep, ou lot d'extraits : un fichier de spécification JSON écrit par l'extracteur
  #   {"part": "03-extraits/parts/Q2.jsonl", "question": "Q2", "start_id": 31,
  #    "items": [{"range": "Ketogenic_diet.md:120-126"},
  #              {"file": "x.md", "chunk_id": "doc_x.md:12", "text": "…texte exact renvoyé par vector_search…",
  #               "localisation": "…"}]}
  python3 scripts/extract.py --spec 03-extraits/parts/Q2.spec.json
  (préférer --spec dès qu'un texte est collé : aucun problème de guillemets ni de longueur de commande ;
   la commande shell reste simple, sans cd ni pipe)
Les identifiants sont attribués à partir de start_id (ou du dernier id du fichier + 1).
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
    p.add_argument(
        "--spec", help="fichier JSON de spécification (part, question, start_id, items[])"
    )
    args = p.parse_args()
    fonds = Path(args.fonds)

    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        args.part = spec.get("part") or args.part
        args.question = spec.get("question") or args.question
        args.start_id = spec.get("start_id") or args.start_id
        spec_items = spec.get("items") or []
    else:
        spec_items = []

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
        spec_items.append(
            {
                "file": args.file,
                "text": args.text,
                "chunk_id": args.chunk,
                "localisation": args.localisation,
            }
        )
    for item in spec_items:
        if item.get("range"):
            m = re.fullmatch(r"(.+?):(\d+)-(\d+)", str(item["range"]))
            if not m:
                sys.exit(f"plage invalide : {item['range']}")
            fname, a, b = m.group(1), int(m.group(2)), int(m.group(3))
            path = fonds / fname
            if not path.is_file():
                sys.exit(f"fichier introuvable dans {fonds} : {fname}")
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if not (1 <= a <= b <= len(lines)):
                sys.exit(f"plage hors fichier : {item['range']} ({len(lines)} lignes)")
            records.append(
                {
                    "id": f"E{eid}",
                    "fichier": fname,
                    "texte": "\n".join(lines[a - 1 : b]).strip("\n"),
                    "localisation": f"L{a}-{b}",
                    "question": args.question,
                }
            )
            eid += 1
            continue
        text = str(item.get("text") or "")
        if not item.get("file") or not text.strip():
            sys.exit("chaque item doit avoir « range », ou « file » + « text »")
        rec = {
            "id": f"E{eid}",
            "fichier": item["file"],
            "texte": text,
            "localisation": item.get("localisation") or "",
            "question": args.question,
        }
        if item.get("chunk_id"):
            rec["chunk_id"] = item["chunk_id"]
        records.append(rec)
        eid += 1
    if not records:
        sys.exit("rien à ajouter (--range, --text ou --spec)")
    with part.open("a", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    for rec in records:
        print(
            f"{rec['id']} ← {rec['fichier']} {rec.get('localisation', '')} ({len(rec['texte'].split())} mots)"
        )


if __name__ == "__main__":
    main()
