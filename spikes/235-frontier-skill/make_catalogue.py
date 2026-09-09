#!/usr/bin/env python3
"""Catalogue du fonds (bras A) : relie chaque référence (URL) du brief à un fichier local.

C'est la ressource « Référencement et organisation » du processus, fournie par
le harnais et non par le skill : le skill ne doit pas accéder aux URL. Stratégies
de correspondance, dans l'ordre : manifeste de sources (url → file_pattern),
nom de base de l'URL, frontmatter `source:` du fichier, sinon « non résolu ».

Usage :
  uv run python spikes/235-frontier-skill/make_catalogue.py --brief <brief.md> --fonds <dir> \
      [--manifest <source_manifest.yaml>] --out <catalogue.md>
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

URL_RE = re.compile(r"https?://[^\s)>\]]+")
FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def title_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = FRONT_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"')
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def source_of(path: Path) -> str | None:
    m = FRONT_RE.match(path.read_text(encoding="utf-8", errors="ignore"))
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith("source:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--brief", required=True)
    p.add_argument("--fonds", required=True)
    p.add_argument("--manifest")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    fonds = Path(args.fonds)
    files = [
        f
        for f in sorted(fonds.iterdir())
        if f.is_file()
        and not f.name.startswith(".")
        and f.name not in {"manifest.json", "README.md", "catalogue.md"}
    ]
    urls = list(dict.fromkeys(URL_RE.findall(Path(args.brief).read_text(encoding="utf-8"))))
    patterns: dict[str, str] = {}
    if args.manifest:
        payload = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8")) or {}
        for src in payload.get("sources") or []:
            patterns[src["url"]] = src["file_pattern"]
    by_source = {source_of(f): f for f in files}
    rows = []
    used: set[str] = set()
    for url in urls:
        match = None
        if url in patterns:
            match = next((f for f in files if f.match(patterns[url])), None)
        if match is None:
            base = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
            match = next((f for f in files if f.name == base or f.name == f"{base}.md"), None)
        if match is None:
            match = by_source.get(url)
        if match is not None:
            used.add(match.name)
            rows.append((url, match.name, title_of(match)))
        else:
            rows.append((url, "NON RÉSOLU", ""))
    lines = [
        "# Catalogue du fonds",
        "",
        "Correspondance entre les références du brief et les fichiers du dossier `fonds/`.",
        "Le fonds est fermé : seuls ces fichiers sont accessibles ; les URL ne sont pas à consulter.",
        "",
        "| Référence du brief | Fichier local | Titre |",
        "|---|---|---|",
    ]
    lines += [f"| {u} | `{f}` | {t} |" for u, f, t in rows]
    extra = [f for f in files if f.name not in used]
    if extra:
        lines += ["", "## Autres fichiers du fonds (non référencés par le brief)", ""]
        lines += [f"- `{f.name}` — {title_of(f)}" for f in extra]
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"catalogue: {args.out} ({sum(1 for r in rows if r[1] != 'NON RÉSOLU')}/{len(rows)} références résolues, {len(extra)} fichiers hors brief)"
    )


if __name__ == "__main__":
    main()
