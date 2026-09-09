#!/usr/bin/env python3
"""Contrôles mécaniques génériques d'un dossier de travail du skill (évaluation ouverte).

Indépendant du thème et du banc : citations résolues, extraits verbatim,
longueur, sections et tableau imposés (passés en arguments), URL dans le corps,
livrables présents. Ne note rien ; imprime un compte rendu.

Usage :
  uv run python spikes/235-frontier-skill/check_open_eval.py --workdir output/spike235/<run> --arm A|B \
     [--min-words 1200 --max-words 1800] [--sections "Définition et mécanisme" ...] \
     [--columns "Indication" "Effet rapporté" ...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.dataprep.vector_backends import clean_for_rag  # noqa: E402

CITE_RE = re.compile(r"\[(E\d+(?:\s*[,;]\s*E?\d+)*)\]")
SOURCES_RE = re.compile(r"(?im)^##\s+Sources\s*$")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", required=True)
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--min-words", type=int)
    p.add_argument("--max-words", type=int)
    p.add_argument("--sections", nargs="*", default=[])
    p.add_argument("--columns", nargs="*", default=[])
    p.add_argument("--data-dir", default=str(REPO / "data"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    w = Path(args.workdir)
    out: dict = {"run": w.name}

    deliverables = [
        "01-cadrage/cadrage.md",
        "02-collecte/bibliographie.md",
        "03-extraits/extraits.jsonl",
        "04-analyse/fiches.md",
        "04-analyse/synthese.md",
        "05-conception/plan.md",
        "06-redaction/manuscrit.md",
        "07-revision/verification.md",
        "07-revision/revision-1.md",
        "08-livraison/rapport.md",
        "journal.md",
        "retex.md",
    ]
    out["deliverables_missing"] = [d for d in deliverables if not (w / d).is_file()]
    out["arbitrage_required"] = (w / "ARBITRAGE-REQUIS.md").is_file()

    rapport = w / "08-livraison" / "rapport.md"
    if not rapport.is_file():
        out["report"] = "absent"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    text = rapport.read_text(encoding="utf-8")
    m = list(SOURCES_RE.finditer(text))
    body = text[: m[-1].start()] if m else text
    out["has_sources_section"] = bool(m)
    out["words_body"] = len(body.split())
    if args.min_words or args.max_words:
        out["length_ok"] = (args.min_words is None or out["words_body"] >= args.min_words) and (
            args.max_words is None or out["words_body"] <= args.max_words
        )
    out["urls_in_body"] = re.findall(r"https?://\S+", body)
    headings = [re.sub(r"[*_`]", "", h).strip() for h in re.findall(r"(?m)^#{1,3}\s+(.+)$", body)]
    out["headings"] = headings
    if args.sections:
        present = []
        for s in args.sections:
            present.append(any(norm(s).lower() in norm(h).lower() for h in headings))
        out["sections_present"] = dict(zip(args.sections, present))
        idx = [
            next((i for i, h in enumerate(headings) if norm(s).lower() in norm(h).lower()), None)
            for s in args.sections
        ]
        found = [i for i in idx if i is not None]
        out["sections_in_order"] = found == sorted(found)
    if args.columns:
        tables = re.findall(r"(?m)^\|.*\|\s*$", body)
        want = [norm(c).lower() for c in args.columns]
        out["table_with_columns"] = any(
            [norm(c).lower() for c in row.strip("|").split("|")] == want for row in tables
        )

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pack_adapter import load_extracts  # même chargement que l'adaptateur

    extracts = load_extracts(w)
    cited = []
    for mm in CITE_RE.finditer(body):
        cited += [f"E{re.sub(r'\D', '', part)}" for part in re.split(r"[,;]", mm.group(1))]
    cited_unique = list(dict.fromkeys(cited))
    out["n_extracts"] = len(extracts)
    out["n_citations"] = len(cited)
    out["n_cited_unique"] = len(cited_unique)
    out["citations_unresolved"] = [c for c in cited_unique if c not in extracts]
    paragraphs = [
        pp
        for pp in re.split(r"\n\s*\n", body)
        if len(pp.split()) >= 25
        and not pp.lstrip().startswith("#")
        and not pp.lstrip().startswith("|")
    ]
    out["paragraphs_25w_without_citation"] = sum(1 for pp in paragraphs if not CITE_RE.search(pp))
    out["paragraphs_25w"] = len(paragraphs)

    # verbatim
    verbatim_ok, verbatim_ko, verbatim_unknown = [], [], []
    registry = {}
    if args.arm == "B" and (w / "retrieval" / "chunks.jsonl").is_file():
        for line in (w / "retrieval" / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("chunk_id"):
                    registry[r["chunk_id"]] = r["text"]
            except json.JSONDecodeError:
                continue
    cache: dict[str, tuple[str, str, str]] = {}
    for eid in cited_unique:
        rec = extracts.get(eid)
        if not rec:
            continue
        t = str(rec.get("texte") or "")
        if args.arm == "A":
            f = w / "fonds" / Path(str(rec.get("fichier") or "")).name
        else:
            f = Path(args.data_dir) / Path(str(rec.get("fichier") or "")).name
        if args.arm == "B" and rec.get("chunk_id") in registry:
            hay = registry[rec["chunk_id"]]
            (verbatim_ok if (t in hay or norm(t) in norm(hay)) else verbatim_ko).append(eid)
            continue
        if not f.is_file():
            verbatim_unknown.append(eid)
            continue
        if f.name not in cache:
            raw = f.read_text(encoding="utf-8", errors="ignore")
            cache[f.name] = (raw, clean_for_rag(raw), norm(raw))
        raw, cleaned, nraw = cache[f.name]
        (verbatim_ok if (t in raw or t in cleaned or norm(t) in nraw) else verbatim_ko).append(eid)
    out["verbatim"] = {"ok": len(verbatim_ok), "ko": verbatim_ko, "unknown_file": verbatim_unknown}

    # Chiffres : chaque nombre d'une phrase citée doit figurer dans l'un des extraits cités par la phrase
    # (comparaison sur les chiffres normalisés : « 3.16 » ≈ « 3,16 », « 1 200 » ≈ « 1200 »).
    def digits(txt: str) -> set[str]:
        found = set()
        for m in re.finditer(r"\d(?:[\s\u00a0]?\d|[.,·]\d)*", txt):
            tok = re.sub(r"[\s\u00a0]", "", m.group(0)).replace(",", ".").replace("·", ".")
            if len(tok.strip(".")) >= 2 or tok.isdigit():
                found.add(tok.strip("."))
        return found

    unsupported = []
    checked = 0
    for pp in re.split(r"\n\s*\n", body):
        if pp.lstrip().startswith("#"):
            continue
        sentences = re.split(r"(?<=[.;!?])\s+(?=[A-ZÀ-Ü«(])", pp)
        for sent in sentences:
            eids = list(
                dict.fromkeys(
                    f"E{re.sub(r'\D', '', part)}"
                    for mm in CITE_RE.finditer(sent)
                    for part in re.split(r"[,;]", mm.group(1))
                )
            )
            if not eids:
                continue
            sent_wo = CITE_RE.sub("", sent)
            nums = {n for n in digits(sent_wo) if not re.fullmatch(r"\d", n)}
            if not nums:
                continue
            hay = " ".join(str(extracts.get(e, {}).get("texte") or "") for e in eids)
            hay_digits = digits(hay)
            missing = sorted(
                n
                for n in nums
                if n not in hay_digits
                and n.rstrip("0").rstrip(".") not in {h.rstrip("0").rstrip(".") for h in hay_digits}
            )
            checked += len(nums)
            if missing:
                unsupported.append(
                    {"missing": missing, "cites": eids, "sentence": sent_wo.strip()[:160]}
                )
    out["numbers"] = {
        "checked": checked,
        "unsupported_in_cited_extracts": len(unsupported),
        "examples": unsupported[:12],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
