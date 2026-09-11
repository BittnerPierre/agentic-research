#!/usr/bin/env python3
"""Assemble le rapport final : corps du manuscrit + section « ## Sources » générée
depuis les extraits cités (et la bibliographie si fournie). Aucun appel de modèle.

Usage : python3 scripts/build_report.py [--manuscrit 06-redaction/manuscrit.md]
        [--out 08-livraison/rapport.md] [--bibliographie 02-collecte/bibliographie.md] [--workdir .]
Affiche le nombre de mots du corps.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import cited_ids, load_parts, norm_ws, split_body, word_count


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", default=".")
    p.add_argument("--manuscrit", default="06-redaction/manuscrit.md")
    p.add_argument("--out", default="08-livraison/rapport.md")
    p.add_argument("--bibliographie", default="02-collecte/bibliographie.md")
    args = p.parse_args()
    w = Path(args.workdir)
    text = (w / args.manuscrit).read_text(encoding="utf-8")
    body, _ = split_body(text)
    extracts = load_parts(w)
    extracts.pop("_errors", None)
    cited = list(dict.fromkeys(cited_ids(body)))
    lines = ["## Sources", "", "### Extraits cités", ""]
    for eid in cited:
        rec = extracts.get(eid)
        if not rec:
            lines.append(f"- [{eid}] (extrait introuvable)")
            continue
        loc = rec.get("localisation") or rec.get("chunk_id") or ""
        snippet = norm_ws(str(rec.get("texte") or ""))[:90]
        lines.append(f"- [{eid}] {rec.get('fichier', '?')} — {loc} — « {snippet}… »")
    biblio = w / args.bibliographie
    if biblio.is_file():
        rows = [
            line for line in biblio.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]
        if len(rows) > 2:
            lines += ["", "### Bibliographie", "", *rows]
    out = w / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body.rstrip() + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"{out} écrit — corps : {word_count(body)} mots, {len(cited)} extraits cités")


if __name__ == "__main__":
    main()
