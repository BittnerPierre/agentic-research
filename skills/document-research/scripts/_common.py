"""Fonctions partagées des scripts du skill document-research (stdlib uniquement)."""

from __future__ import annotations

import json
import re
from pathlib import Path

CITE_RE = re.compile(r"\[(E\d+(?:\s*[,;]\s*E?\d+)*)\]")
SOURCES_RE = re.compile(r"(?im)^##\s+Sources\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\((?:<[^>]*>|[^)\s]*)(?:\s+\"[^\"]*\")?\)")


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def cited_ids(text: str) -> list[str]:
    out: list[str] = []
    for m in CITE_RE.finditer(text):
        for part in re.split(r"[,;]", m.group(1)):
            digits = re.sub(r"\D", "", part)
            if digits:
                out.append(f"E{digits}")
    return out


def split_body(report: str) -> tuple[str, str]:
    """(corps, section Sources) — le corps exclut la dernière section « ## Sources »."""
    matches = list(SOURCES_RE.finditer(report))
    if not matches:
        return report.rstrip(), ""
    cut = matches[-1].start()
    return report[:cut].rstrip(), report[cut:]


def load_parts(workdir: Path) -> dict[str, dict]:
    """Tous les extraits : parts/*.jsonl font foi pour le texte ; extraits.jsonl (index
    facultatif) ne peut qu'ajouter des champs (ex. « retenu ») ou des extraits absents des parts."""
    root = workdir / "03-extraits"
    out: dict[str, dict] = {}
    errors: list[str] = []

    def ingest(path: Path, index: bool) -> None:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"{path.name}:{n} JSON invalide")
                continue
            if not isinstance(rec, dict) or not rec.get("id"):
                continue
            eid = str(rec["id"]).upper()
            if eid in out:
                if index:
                    for key, value in rec.items():
                        if key not in {"texte", "id"}:
                            out[eid][key] = value
                else:
                    errors.append(f"{eid} défini dans {out[eid]['_file']} et {path.name}")
                continue
            rec["_file"] = path.name
            out[eid] = rec

    for path in sorted((root / "parts").glob("*.jsonl")):
        ingest(path, index=False)
    if (root / "extraits.jsonl").is_file():
        ingest(root / "extraits.jsonl", index=True)
    if errors:
        out["_errors"] = {"lines": errors}
    return out


def load_contract(workdir: Path) -> dict:
    path = workdir / "01-cadrage" / "contrat.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": "contrat.json invalide"}


def load_registry(workdir: Path) -> dict[str, str]:
    """Mode dataprep : registre des morceaux renvoyés par vector_search (chunk_id → texte),
    s'il est fourni par le harnais sous retrieval/chunks.jsonl."""
    path = workdir / "retrieval" / "chunks.jsonl"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("chunk_id") and rec.get("text"):
            out[str(rec["chunk_id"])] = str(rec["text"])
    return out


def word_count(text: str) -> int:
    return len(text.split())
