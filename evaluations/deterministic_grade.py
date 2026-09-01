"""Deterministic grader for agentic-research exercises.

Goal (issue: deterministic benchmark): score a run WITHOUT relying solely on an
LLM judge. The ground truth is the exercise CORPUS (the numbers the report was
allowed to use), not a model's opinion. The grader:

- knows the exact figures to find (coverage / recall),
- verifies every figure the report states against the corpus (accuracy),
- flags any specific number NOT traceable to the corpus (fabrication) with
  ZERO TOLERANCE — a polished report with invented figures FAILS,
- checks agenda discipline (off-theme distractors), tone, and format,
- attributes failures to a workflow STAGE via the intermediate artifacts
  (sources.json = what retrieval returned) so we get a root cause.

Everything above is mechanical. A closed, evidence-required LLM entailment is used
ONLY for qualitative must-cover claims (trends), never for open grading, and is
optional (skipped if no OPENAI_API_KEY).

    uv run deterministic-grade benchmarks/runs/<run> --exercise evaluations/exercises/ai-capex-intensity
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from itertools import pairwise
from pathlib import Path

import yaml


def _deaccent(s: str) -> str:
    normalized = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return normalized.replace("\u2019", "'")


# ---------------------------------------------------------------------------
# Number parsing / normalization
# ---------------------------------------------------------------------------

_NUMBER_BODY = r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d[\d.,]*\d|\d"
_NUMBER_UNIT = (
    r"%|bps?\b|basis\s+points?\b|\u00d7|x\b|Md\$|Mds?\b|milliards?\b|"
    r"B\b|billions?\b|M\b|millions?\b|k\b|thousands?\b"
)

# A number token, optionally signed/approximate/currency-prefixed, with an optional
# unit suffix. Opening parentheses only mean an accounting negative when the token
# itself is closed immediately, e.g. ``($14.7B)`` rather than ``($14.7B in FY2021)``.
_NUM = re.compile(
    rf"(?<!\d)(?P<paren>\()?\s*(?P<sign>[-+~≈\u2212]?)\s*(?P<currency>\$)?\s*"
    rf"(?P<body>{_NUMBER_BODY})\s*(?P<unit>{_NUMBER_UNIT})?\s*(?P<close>\))?",
    re.IGNORECASE,
)

# The first endpoint of a range commonly inherits the second endpoint's unit:
# ``$72-75B``, ``56-94%`` and ``1,000-1,500 million`` must yield two claims.
_RANGE = re.compile(
    rf"(?<!\d)(?P<first_currency>\$)?\s*(?P<first>{_NUMBER_BODY})\s*"
    rf"(?P<first_unit>{_NUMBER_UNIT})?\s*[-\u2013\u2014]\s*"
    rf"(?P<second_currency>\$)?\s*(?P<second>{_NUMBER_BODY})\s*"
    rf"(?P<second_unit>{_NUMBER_UNIT})?",
    re.IGNORECASE,
)


def to_float(body: str) -> float | None:
    """Parse a numeric body, handling thousands separators and French decimals."""
    s = re.sub(r"[ \u00a0\u202f]", "", body.strip())
    if "," in s and "." in s:
        # The rightmost separator is decimal; the other one groups thousands.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # comma only: decimal if 1-2 trailing digits (French), else thousands
        frac = s.rsplit(",", 1)[1]
        s = s.replace(",", "." if (s.count(",") == 1 and len(frac) <= 2) else "")
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_number(
    body: str,
    *,
    sign: str = "",
    unit: str = "",
    currency: bool = False,
    accounting_negative: bool = False,
) -> tuple[float, str] | None:
    value = to_float(body)
    if value is None:
        return None

    normalized_unit = _deaccent(unit.lower().strip())
    if normalized_unit in {"m", "million", "millions"}:
        value /= 1_000.0
        normalized_unit = "b"
    elif normalized_unit in {"k", "thousand", "thousands"}:
        value /= 1_000_000.0
        normalized_unit = "b"
    elif normalized_unit in {
        "md$",
        "md",
        "mds",
        "milliard",
        "milliards",
        "b",
        "billion",
        "billions",
    }:
        normalized_unit = "b"
    elif normalized_unit in {"bp", "bps", "basis point", "basis points"}:
        value /= 100.0
        normalized_unit = "%"
    elif normalized_unit in {"x", "\u00d7"}:
        normalized_unit = "x"

    if sign in {"-", "\u2212"} or accounting_negative:
        value = -abs(value)
    elif sign == "+":
        value = abs(value)

    if not normalized_unit and currency:
        normalized_unit = "$"
    return value, normalized_unit


def extract_numbers(text: str) -> list[tuple[float, str, int]]:
    """Return (value, unit, position) for every specific number in the text.

    Keeps numbers that carry financial semantics (a unit, a decimal, or magnitude);
    drops bare small integers that are almost always structural (counts, list items)."""
    out: list[tuple[float, str, int]] = []
    range_spans: list[tuple[int, int]] = []

    for match in _RANGE.finditer(text):
        first_unit = match.group("first_unit") or match.group("second_unit") or ""
        second_unit = match.group("second_unit") or match.group("first_unit") or ""
        first = _normalize_number(
            match.group("first"),
            unit=first_unit,
            currency=bool(match.group("first_currency") or match.group("second_currency")),
        )
        second = _normalize_number(
            match.group("second"),
            unit=second_unit,
            currency=bool(match.group("second_currency") or match.group("first_currency")),
        )
        if first is None or second is None:
            continue
        has_semantics = bool(first_unit or second_unit or match.group("first_currency"))
        has_semantics = has_semantics or max(abs(first[0]), abs(second[0])) >= 100
        if not has_semantics:
            continue
        out.extend(
            [
                (first[0], first[1], match.start("first")),
                (second[0], second[1], match.start("second")),
            ]
        )
        range_spans.append(match.span())

    for m in _NUM.finditer(text):
        if any(start <= m.start("body") < end for start, end in range_spans):
            continue
        parsed = _normalize_number(
            m.group("body"),
            sign=m.group("sign") or "",
            unit=m.group("unit") or "",
            currency=bool(m.group("currency")),
            accounting_negative=False,
        )
        if parsed is None:
            continue
        val, unit = parsed
        has_decimal = "." in m.group("body") or ("," in m.group("body"))
        # keep if: has a unit, or a decimal, or is a 4-digit year, or magnitude >= 100
        is_year = 1990 <= val <= 2100 and float(val).is_integer()
        if unit or has_decimal or is_year or abs(val) >= 100:
            out.append((val, unit, m.start("body")))
    return sorted(out, key=lambda item: item[2])


def close(a: float, b: float, tol_abs: float = 0.15, tol_rel: float = 0.01) -> bool:
    return abs(a - b) <= max(tol_abs, tol_rel * max(abs(a), abs(b)))


_AMBIGUOUS_COMMA = re.compile(r"\d{1,3},\d{3}(?![\d.,])")


def alternate_comma_value(text: str, pos: int) -> float | None:
    """French-decimal reinterpretation of an ambiguous comma number at ``pos``.

    "72,215 milliards" is 72.215 (FR 3-decimal) but parses as 72215 (EN thousands).
    Only consulted as a FALLBACK when the primary parse fails the corpus whitelist,
    so English thousands-grouped values ("85,002") keep their primary reading.
    """
    m = _AMBIGUOUS_COMMA.match(text, pos)
    if not m:
        return None
    return to_float(m.group(0).replace(",", "."))


# ---------------------------------------------------------------------------
# Corpus ground truth
# ---------------------------------------------------------------------------

# Keys are space-stripped + de-accented, ordered most-specific-first (EN + FR), so
# "capex/ocf"/"intensite" wins over "capex", "disponible"(FCF) over generic "flux".
METRIC_ORDER = [
    ("capexintensity", "Capex/OCF"),
    ("intensitecapex", "Capex/OCF"),
    ("intensite", "Capex/OCF"),
    ("capex/ocf", "Capex/OCF"),
    ("%ocf", "Capex/OCF"),  # "Capex as % OCF" -> intensity, not OCF
    ("aspercentocf", "Capex/OCF"),
    ("intensity", "Capex/OCF"),
    ("fluxdetresoreriedisponible", "FCF"),
    ("freecashflow", "FCF"),
    ("disponible", "FCF"),
    ("fcf", "FCF"),
    ("fluxdetresoreriedexploitation", "Operating cash flow"),
    ("operatingcashflow", "Operating cash flow"),
    ("exploitation", "Operating cash flow"),
    ("margeoperationnelle", "Operating margin"),
    ("operatingmargin", "Operating margin"),
    ("margeop", "Operating margin"),
    ("marge", "Operating margin"),
    ("resultatoperationnel", "Operating income"),
    ("operatingincome", "Operating income"),
    ("resultatop", "Operating income"),
    ("chiffredaffaires", "Revenue"),
    ("revenue", "Revenue"),
    ("revenus", "Revenue"),
    ("ocf", "Operating cash flow"),
    ("depensesdinvestissement", "Capex"),
    ("capex", "Capex"),
]


def _is_year(v: float) -> bool:
    return 1990 <= v <= 2100 and float(v).is_integer()


METRIC_ALIASES = {
    "Revenue": ("revenue", "revenu", "revenus", "chiffre d'affaires"),
    "Operating income": (
        "operating income",
        "operating profit",
        "op. income",
        "resultat d'exploitation",
        "resultat operationnel",
        "benefice d'exploitation",
    ),
    "Operating margin": (
        "operating margin",
        "op. margin",
        "margin",
        "marge operationnelle",
        "marge d'exploitation",
    ),
    "Operating cash flow": (
        "operating cash flow",
        "cash flow from operations",
        "flux de tresorerie d'exploitation",
        "ocf",
    ),
    "Capex": (
        "capex",
        "capital expenditure",
        "capital expenditures",
        "capital investments",
        "spending",
        "depenses d'investissement",
    ),
    "FCF": ("free cash flow", "fcf", "flux de tresorerie disponible"),
    "Capex/OCF": (
        "capex/ocf",
        "capex intensity",
        "capex intensity ratio",
        "capex as % ocf",
        "capex as a percentage of ocf",
        "intensite capex",
        "intensity",
        "part d'ocf",
        "part de l'ocf",
        "ocf absorbee",
        "of operating cash flow",
        "of its operating cash flow",
        "of ocf",
    ),
}
METRIC_PRIORITY = {
    metric: index
    for index, metric in enumerate(
        [
            "Capex/OCF",
            "FCF",
            "Operating margin",
            "Operating income",
            "Operating cash flow",
            "Revenue",
            "Capex",
        ]
    )
}


def load_corpus(exercise: Path) -> dict:
    """Whitelist of every corpus number + a fact index from key_metrics.csv."""
    corpus_dir = exercise / "corpus"
    whitelist: list[float] = []
    for f in corpus_dir.glob("*"):
        if f.is_file() and f.suffix.lower() != ".csv":
            for val, _u, _p in extract_numbers(f.read_text(encoding="utf-8", errors="ignore")):
                whitelist.append(val)

    facts: dict[tuple[str, str, str], float] = {}
    latest_fy: dict[str, str] = {}
    csv_path = corpus_dir / "key_metrics.csv"
    if csv_path.is_file():
        import csv as _csv

        for row in _csv.DictReader(csv_path.open(encoding="utf-8")):
            co = row["Company"].strip()
            metric = row["Metric"].strip()
            fy = row["FiscalYear"].strip()
            val = to_float(row["Value"])
            if val is None:
                continue
            whitelist.append(val)
            facts[(co.lower(), metric.lower(), fy.lower())] = val
            if co not in latest_fy or fy > latest_fy[co]:
                latest_fy[co] = fy
    return {"whitelist": whitelist, "facts": facts, "latest_fy": latest_fy}


def in_whitelist(val: float, whitelist: list[float]) -> bool:
    # Tight tolerance: with a dense corpus (~180 numbers) a loose match lets a
    # fabricated figure slip by coinciding with an unrelated real value.
    return any(close(val, w, tol_abs=0.15, tol_rel=0.002) for w in whitelist)


# ---------------------------------------------------------------------------
# Markdown table parsing (for accuracy: cells -> (company, metric, value))
# ---------------------------------------------------------------------------


def parse_tables(md: str) -> list[list[list[str]]]:
    tables, cur = [], []
    for line in md.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            cur.append(cells)
        else:
            if len(cur) >= 2:
                tables.append(cur)
            cur = []
    if len(cur) >= 2:
        tables.append(cur)
    return tables


def _canonical_metric(text: str) -> str | None:
    normalized = _deaccent(text.lower().replace(" ", ""))
    return next((canon for key, canon in METRIC_ORDER if key in normalized), None)


_CITATION_BLOCK_RE = re.compile(r"\[[^\]]*\bS\d+(?::\d+)?[^\]]*\]", re.I)
_UNAVAILABLE_RE = re.compile(
    r"\b(?:n/?a|none|null|unavailable|not available|not disclosed|missing|"
    r"non disponibles?|indisponibles?|non divulgue(?:e)?s?|manquantes?|n\.?d\.?)\b",
    re.I,
)


def _cell_numbers(cell: str) -> list[float]:
    """Parse all values in a table cell, including bare small integers."""
    clean_cell = _CITATION_BLOCK_RE.sub("", cell)
    numbers = extract_numbers(clean_cell)
    seen_positions = {position for _value, _unit, position in numbers}
    for match in _NUM.finditer(clean_cell):
        if match.start("body") in seen_positions:
            continue
        parsed = _normalize_number(
            match.group("body"),
            sign=match.group("sign") or "",
            unit=match.group("unit") or "",
            currency=bool(match.group("currency")),
            accounting_negative=bool(match.group("paren") and match.group("close")),
        )
        if parsed is None or _is_year(parsed[0]):
            continue
        numbers.append((parsed[0], parsed[1], match.start("body")))
    numbers = sorted(numbers, key=lambda item: item[2])
    if len(numbers) == 1 and re.match(r"^\s*\(.*\)\s*$", clean_cell):
        value, unit, position = numbers[0]
        numbers = [(-abs(value), unit, position)]
    elif len(numbers) > 1:
        # In combined cells such as ``80.0B (11.2%)``, parentheses separate a
        # secondary metric; they are not accounting-negative notation.
        numbers = [
            (
                abs(value) if "(" in clean_cell[max(0, position - 4) : position] else value,
                unit,
                position,
            )
            for value, unit, position in numbers
        ]
    return [value for value, _unit, _position in numbers]


def _single_cell_number(cell: str) -> float | None:
    values = _cell_numbers(cell)
    return values[0] if len(values) == 1 else None


def _period(cell: str) -> str | None:
    match = re.search(r"\bFY\s*(20\d{2})\b|\b(20\d{2})\b", cell, re.I)
    if not match:
        return None
    return f"FY{match.group(1) or match.group(2)}"


def _canonical_metrics(text: str) -> list[str]:
    normalized = _deaccent(text.lower())
    compact = normalized.replace(" ", "")
    metrics = []
    for metric, aliases in METRIC_ALIASES.items():
        if any(_deaccent(alias.lower()).replace(" ", "") in compact for alias in aliases):
            metrics.append(metric)
    if re.search(r"\bmargin|\bmarge\b", normalized) and "Operating margin" not in metrics:
        metrics.append("Operating margin")
    if "Capex/OCF" in metrics:
        metrics = [metric for metric in metrics if metric not in {"Capex", "Operating cash flow"}]
    if "FCF" in metrics:
        metrics = [metric for metric in metrics if metric not in {"Capex", "Operating cash flow"}]
    return metrics


def _table_claims(
    tables, companies: list[str], default_period: str | None = None
) -> list[tuple[str, str, str | None, float | None, str]]:
    """Yield numeric and explicit-unavailability claims from Markdown tables."""
    cmap = {c.lower(): c for c in companies}
    out = []
    for tbl in tables:
        header = [_deaccent(h.lower().replace(" ", "")) for h in tbl[0]]
        company_col = next(
            (i for i, h in enumerate(header) if h in {"company", "societe", "entreprise"}), 0
        )
        metric_col = next(
            (i for i, h in enumerate(header) if h in {"metric", "metrique", "indicateur"}), None
        )
        period_col = next(
            (
                i
                for i, h in enumerate(header)
                if h in {"period", "periode", "fiscalyear", "exercice", "anneefiscale"}
                or "exercicefiscal" in h
                or "periodefiscale" in h
                or h.startswith("fiscalyear")
            ),
            None,
        )
        value_col = next(
            (i for i, h in enumerate(header) if h in {"value", "valeur", "montant"}), None
        )
        # map each column index to a metric key
        col_metrics = {}
        for i, h in enumerate(header):
            metrics = _canonical_metrics(h)
            if metrics:
                col_metrics[i] = metrics
        current_company = None
        for row in tbl[1:]:
            if not row or company_col >= len(row):
                continue
            co = next((cmap[c] for c in cmap if c in row[company_col].lower()), None)
            if co:
                current_company = co
            elif not row[company_col].strip():
                co = current_company
            if not co:
                continue
            period = (
                _period(row[period_col])
                if period_col is not None and period_col < len(row)
                else default_period
            )
            if (
                metric_col is not None
                and value_col is not None
                and max(metric_col, value_col) < len(row)
            ):
                metric = _canonical_metric(row[metric_col])
                value = _single_cell_number(row[value_col])
                if metric and value is not None:
                    out.append((co, metric, period, value, "numeric"))
                elif metric and _UNAVAILABLE_RE.search(row[value_col]):
                    out.append((co, metric, period, None, "unavailable"))
                continue
            for i, cell in enumerate(row):
                if i not in col_metrics:
                    continue
                metrics = col_metrics[i]
                values = _cell_numbers(cell)
                claim_period = period or _period(cell) or default_period
                if len(metrics) == len(values):
                    out.extend(
                        (co, metric, claim_period, value, "numeric")
                        for metric, value in zip(metrics, values, strict=True)
                    )
                elif len(metrics) == 1 and len(values) == 1:
                    out.append((co, metrics[0], claim_period, values[0], "numeric"))
                elif not values and _UNAVAILABLE_RE.search(cell):
                    out.extend(
                        (co, metric, claim_period, None, "unavailable") for metric in metrics
                    )
    return out


def table_cells(tables, companies: list[str]) -> list[tuple[str, str, str | None, float]]:
    """Yield company/metric/period/value facts from wide and canonical long tables."""
    return [
        (company, metric, period, value)
        for company, metric, period, value, status in _table_claims(tables, companies)
        if status == "numeric" and value is not None
    ]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_tree(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.is_dir():
        return digest.hexdigest()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _knowledge_document_names(run_dir: Path) -> dict[str, str]:
    """Map vector document IDs to original files when a run exposes its KB manifest."""
    candidates = [
        run_dir / "knowledge_db.json",
        run_dir / "data" / "knowledge_db.json",
    ]
    if len(run_dir.parents) >= 3:
        candidates.append(run_dir.parents[2] / "data" / "knowledge_db.json")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            entries = payload["entries"]
        else:
            entries = payload.values() if isinstance(payload, dict) else payload
        mapping = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            document_id = str(entry.get("vector_doc_id") or entry.get("document_id") or "")
            file_name = str(entry.get("file_name") or entry.get("filename") or "")
            if document_id and file_name:
                mapping[document_id] = file_name
        if mapping:
            return mapping
    return {}


def _source_origins(source: dict, document_names: dict[str, str]) -> set[str]:
    origins = set()
    for doc_id in source.get("doc_ids") or []:
        base = str(doc_id).split(":", 1)[0]
        origins.add(document_names.get(base, base))
    return origins


def _matches_any(text: str, alternatives: list[str]) -> bool:
    normalized = _deaccent(text.lower())
    return any(_deaccent(str(value).lower()) in normalized for value in alternatives)


def _contains_anchor(text: str, anchor: str) -> bool:
    escaped = re.escape(_deaccent(anchor.lower()))
    if anchor and anchor[0].isalnum() and anchor[-1].isalnum():
        escaped = rf"(?<!\w){escaped}(?!\w)"
    return bool(re.search(escaped, _deaccent(text.lower())))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def grade(run_dir: Path, exercise: Path, report_md: str, sources: list[dict]) -> dict:
    ak = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    spec = yaml.safe_load((exercise / "spec.yaml").read_text(encoding="utf-8"))
    corpus = load_corpus(exercise)
    companies = ak.get("companies_in_scope", [])
    facts, whitelist, latest_fy = corpus["facts"], corpus["whitelist"], corpus["latest_fy"]

    mode = ak.get("mode", "numeric")
    sources_heading = re.search(r"(?im)^##\s+Sources\s*$", report_md)
    report_body = report_md[: sources_heading.start()] if sources_heading else report_md

    def _citation_ids(text: str) -> list[str]:
        return list(
            dict.fromkeys(
                f"S{number}"
                for block in re.findall(r"\[([^\]]+)\]", text)
                for number in re.findall(r"\bS(\d+)(?::\d+)?\b", block, re.I)
            )
        )

    source_by_id = {
        str(source.get("source_id") or "").upper(): source
        for source in sources
        if source.get("source_id")
    }
    valid_source_ids = set(source_by_id)
    document_names = _knowledge_document_names(run_dir)
    enforce_source_provenance = bool(ak.get("require_source_provenance", False))
    requirement_results = []

    if mode == "conceptual":
        # Each concept must be explained locally, contain the declared semantic
        # atoms, and cite a retrieved chunk from the expected raw document.
        must = ak.get("must_cover", [])
        min_explanation_words = int(ak.get("min_explanation_words", 20))
        require_citation = bool(ak.get("require_citation", True))
        paragraphs = re.split(r"\n\s*\n", report_body)

        def _citation_has_expected_origin(citation: str, concept: dict) -> bool:
            expected_files = concept.get("source_files") or []
            if not expected_files:
                return citation in valid_source_ids
            source = source_by_id.get(citation)
            if not source:
                return False
            origins = _source_origins(source, document_names)
            if not origins and not enforce_source_provenance:
                origins = {str(source.get("file_name") or "")}
            return any(
                _matches_any(origin, [expected])
                for origin in origins
                for expected in expected_files
            )

        def _concept_evidence(concept: dict) -> tuple[bool, str | None]:
            anchors = concept.get("anchors_any") or []
            for paragraph in paragraphs:
                normalized_paragraph = re.sub(r"[`*_]", "", paragraph)
                if len(normalized_paragraph.split()) < min_explanation_words:
                    continue
                if not any(_contains_anchor(normalized_paragraph, anchor) for anchor in anchors):
                    continue
                citations = _citation_ids(paragraph)
                if require_citation and not any(
                    _citation_has_expected_origin(citation, concept) for citation in citations
                ):
                    continue
                cited_origins = {
                    origin
                    for citation in citations
                    for origin in _source_origins(source_by_id.get(citation, {}), document_names)
                }
                if len(cited_origins) < int(concept.get("min_cited_origins", 0)):
                    continue
                groups = concept.get("semantic_groups") or []
                if any(not _matches_any(normalized_paragraph, group) for group in groups):
                    continue
                gap_language = concept.get("gap_language_any") or [
                    "not covered",
                    "not documented",
                    "not supported",
                    "absent",
                    "non documente",
                    "non couvert",
                    "pas dans les sources",
                    "source gap",
                ]
                states_gap = _matches_any(normalized_paragraph, gap_language)
                expected_status = concept.get("expected_status", "supported")
                if expected_status == "source_gap" and not states_gap:
                    continue
                if expected_status == "supported" and states_gap:
                    continue
                return True, paragraph.strip()[:240]
            return False, None

        evidence_by_id = {concept["id"]: _concept_evidence(concept) for concept in must}
        covered = [concept for concept in must if evidence_by_id[concept["id"]][0]]
        for concept in must:
            passed, evidence = evidence_by_id[concept["id"]]
            requirement_results.append(
                {
                    "id": concept["id"],
                    "label": concept.get("concept", concept["id"]),
                    "critical": bool(concept.get("critical", True)),
                    "status": "pass" if passed else "missing_or_unsupported",
                    "evidence": evidence,
                }
            )
        coverage = len(covered) / len(must) if must else 0.0
        claims, cells, matches, wrongs = [], [], [], []
    else:
        numeric_contract = ak.get("numeric_requirements") or {}
        contract_declared = bool(ak.get("numeric_requirements"))
        required_metrics = numeric_contract.get("metrics") or [
            "Revenue",
            "Operating margin",
            "Capex",
            "Capex/OCF",
        ]
        expected_periods = numeric_contract.get("periods") or latest_fy
        must = []
        contract_errors = []
        for co in companies:
            fy = expected_periods.get(co) or latest_fy.get(co)
            if numeric_contract.get("require_latest") and fy != latest_fy.get(co):
                contract_errors.append(
                    f"{co}: contract period {fy!r} differs from corpus latest {latest_fy.get(co)!r}"
                )
            for metric in required_metrics:
                v = facts.get((co.lower(), metric.lower(), (fy or "").lower()))
                if v is None:
                    if contract_declared:
                        contract_errors.append(
                            f"{co} {metric} {fy}: missing from accuracy universe"
                        )
                else:
                    must.append((co, metric, fy, v))
        if contract_errors:
            raise ValueError("Invalid numeric benchmark contract: " + "; ".join(contract_errors))

        declared_periods = {period for period in expected_periods.values() if period}
        default_period = None
        if len(declared_periods) == 1:
            candidate_period = next(iter(declared_periods))
            if re.search(rf"\b{re.escape(candidate_period)}\b", report_body, re.I):
                default_period = candidate_period
        claims = _table_claims(parse_tables(report_body), companies, default_period)
        cells = [
            (company, metric, period, value)
            for company, metric, period, value, status in claims
            if status == "numeric" and value is not None
        ]

        # Coverage is deliberately strict: the requested fiscal period must be
        # explicit. A coincidentally correct value with no period does not qualify.
        covered = [
            m
            for m in must
            if any(
                c[0] == m[0] and c[1] == m[1] and c[2] == m[2] and close(c[3], m[3]) for c in cells
            )
        ]
        coverage = len(covered) / len(must) if must else 0.0

        # accuracy (precision): EVERY stated cell must match some corpus FY.
        # Iterate all cells (not deduped by co/metric) so an internally inconsistent
        # report (right value in one table, wrong in another) is caught.
        matches, wrongs, seen = [], [], set()
        for co, metric, period, val in cells:
            any_fy = [
                v
                for (c, m, fiscal_year), v in facts.items()
                if c == co.lower()
                and m == metric.lower()
                and (period is None or fiscal_year == period.lower())
            ]
            key = (co, metric, period, round(val, 2))
            if key in seen:
                continue
            seen.add(key)
            if any_fy and any(close(val, v) for v in any_fy):
                matches.append((co, metric, val))
            else:
                truth = facts.get((co.lower(), metric.lower(), (latest_fy.get(co) or "").lower()))
                wrongs.append((co, metric, val, truth))

        for co, metric, period, _value, status in claims:
            if status != "unavailable":
                continue
            claim_period = period or expected_periods.get(co) or latest_fy.get(co)
            if facts.get((co.lower(), metric.lower(), (claim_period or "").lower())) is not None:
                wrongs.append(
                    (
                        co,
                        metric,
                        "unavailable",
                        facts[(co.lower(), metric.lower(), claim_period.lower())],
                    )
                )

        covered_set = {(item[0], item[1], item[2]) for item in covered}
        for company, metric, period, value in must:
            passed = (company, metric, period) in covered_set
            requirement_results.append(
                {
                    "id": f"{company.lower()}_{metric.lower().replace(' ', '_').replace('/', '_')}",
                    "label": f"{company} {metric} {period}",
                    "critical": True,
                    "status": "pass" if passed else "missing_or_wrong",
                    "expected": value,
                }
            )

    # ---- explicit false-unavailability claims ----
    unavailable_re = re.compile(
        r"unavailable|not available|no (?:reported |recent )?data|lack(?:s|ing)? disclosed|"
        r"not disclosed|non disponibles?|indisponibles?|aucune donnee|donnees? manquante?s?|"
        r"absence (?:de|d')|non divulgue|pas disponibles?",
        re.I,
    )
    guidance_re = re.compile(r"guidance|forecast|projection|prevision|orientation", re.I)
    contradictions = []
    current_company = None
    for line in report_body.splitlines():
        explicit_companies = [
            company for company in companies if re.search(rf"\b{re.escape(company)}\b", line, re.I)
        ]
        is_heading = re.match(r"^\s*#{1,6}|^\s*\*\*[^*]+\*\*\s*$", line)
        if is_heading:
            current_company = explicit_companies[0] if len(explicit_companies) == 1 else None
        for clause in re.split(r"(?<=[.!?;])\s+|,\s+(?:and|et|but|mais)\s+", line):
            normalized_clause = _deaccent(clause.lower())
            if not unavailable_re.search(normalized_clause) or guidance_re.search(
                normalized_clause
            ):
                continue
            clause_companies = [
                company
                for company in companies
                if re.search(rf"\b{re.escape(company)}\b", clause, re.I)
            ] or ([current_company] if current_company else [])
            mentioned_years = re.findall(r"\b(?:FY\s*)?(20\d{2})\b", normalized_clause, re.I)
            for company in clause_companies:
                latest = latest_fy.get(company)
                if mentioned_years and latest and latest.removeprefix("FY") not in mentioned_years:
                    continue
                for metric, aliases in METRIC_ALIASES.items():
                    if not any(_deaccent(alias.lower()) in normalized_clause for alias in aliases):
                        continue
                    if latest and (company.lower(), metric.lower(), latest.lower()) in facts:
                        contradictions.append(
                            f"{company} {metric}: report says unavailable for {latest}"
                        )
    contradictions = sorted(set(contradictions))

    if mode != "conceptual":
        paragraphs = re.split(r"\n\s*\n", report_body)
        for requirement in ak.get("text_requirements") or []:
            evidence = None
            for paragraph in paragraphs:
                anchors = requirement.get("anchors_any") or []
                if anchors and not _matches_any(paragraph, anchors):
                    continue
                groups = requirement.get("semantic_groups") or []
                if any(not _matches_any(paragraph, group) for group in groups):
                    continue
                if len(paragraph.split()) < int(requirement.get("min_words", 8)):
                    continue
                citations = _citation_ids(paragraph)
                if requirement.get("require_citation") and not set(citations) & valid_source_ids:
                    continue
                evidence = paragraph.strip()[:240]
                break
            requirement_results.append(
                {
                    "id": requirement["id"],
                    "label": requirement.get("label", requirement["id"]),
                    "critical": bool(requirement.get("critical", True)),
                    "status": "pass" if evidence else "missing_or_unsupported",
                    "evidence": evidence,
                }
            )

    # ---- fabrication gate (ZERO TOLERANCE) ----
    report_nums = extract_numbers(report_md)
    # Spans where numbers are NOT grounding claims: fenced/inline code (example data)
    # and heading numbering prefixes such as "## 3.1". Skip fabrication checks there.
    _ignore = []
    for _m in re.finditer(r"```.*?```", report_md, re.S):
        _ignore.append((_m.start(), _m.end()))
    for _m in re.finditer(r"`[^`\n]*`", report_md):
        _ignore.append((_m.start(), _m.end()))
    for _m in re.finditer(r"(?m)^\s*\|.*$", report_body):
        _ignore.append((_m.start(), _m.end()))
    if sources_heading:
        _ignore.append((sources_heading.start(), len(report_md)))
    for _m in re.finditer(
        r"(?m)^#{1,6}\s+(?:[*_~`]+)?\d+(?:[.)-]\d+)*[.)]?(?:[*_~`]+)?\s+",
        report_md,
    ):
        _ignore.append((_m.start(), _m.end()))

    source_numbers = {
        str(source.get("source_id") or "").upper(): [
            v for v, _unit, _pos in extract_numbers(source.get("content") or "")
        ]
        for source in sources
    }

    def _line_citations(pos: int) -> list[str]:
        start = report_md.rfind("\n", 0, pos) + 1
        end = report_md.find("\n", pos)
        line = report_md[start : len(report_md) if end == -1 else end]
        return _citation_ids(line)

    def _in_ignore(p: int) -> bool:
        return any(a <= p < b for a, b in _ignore)

    def _fact_attribution_is_valid(value: float, unit: str, pos: int) -> bool | None:
        line_start = report_md.rfind("\n", 0, pos) + 1
        line_end = report_md.find("\n", pos)
        line = report_md[line_start : len(report_md) if line_end == -1 else line_end]
        if line.lstrip().startswith("|"):
            return None  # Parsed table cells are checked by the accuracy axis.

        relative_line_pos = pos - line_start
        boundaries = [0]
        boundaries.extend(
            match.end() for match in re.finditer(r";\s*|(?<=[!?])\s+|(?<=\.)\s+(?=[A-ZÀ-Ö])", line)
        )
        boundaries.append(len(line))
        clause_start, clause_end = 0, len(line)
        for start, end in pairwise(boundaries):
            if start <= relative_line_pos <= end:
                clause_start, clause_end = start, end
                break
        clause = line[clause_start:clause_end]
        relative_pos = relative_line_pos - clause_start
        if guidance_re.search(_deaccent(clause.lower())):
            return None  # Guidance values are corpus facts but not in key_metrics.csv.

        company_matches = [
            (match.start(), company)
            for company in companies
            for match in re.finditer(rf"\b{re.escape(company)}\b", clause, re.I)
        ]
        inherited_company = None
        if not company_matches:
            prior_companies = list(
                dict.fromkeys(
                    company
                    for company in companies
                    if re.search(rf"\b{re.escape(company)}\b", line[:clause_start], re.I)
                )
            )
            if len(prior_companies) != 1:
                return None
            inherited_company = prior_companies[0]
        ordered_companies = list(
            dict.fromkeys(company for _position, company in sorted(company_matches))
        )
        ordered_numbers = [
            (position, found)
            for found, _unit, position in extract_numbers(clause)
            if not _is_year(found)
        ]
        company_confident = inherited_company is not None or len(ordered_companies) == 1
        if inherited_company is not None:
            company = inherited_company
        elif len(ordered_companies) == len(ordered_numbers):
            number_index = min(
                range(len(ordered_numbers)),
                key=lambda index: abs(ordered_numbers[index][0] - relative_pos),
            )
            company = ordered_companies[number_index]
            company_confident = True
        else:
            company = min(company_matches, key=lambda item: abs(item[0] - relative_pos))[1]

        normalized_clause = _deaccent(clause.lower())
        metric_matches = [
            (match.start(), metric)
            for metric, aliases in METRIC_ALIASES.items()
            for alias in aliases
            for match in re.finditer(re.escape(_deaccent(alias.lower())), normalized_clause)
        ]
        if not metric_matches:
            return None
        ordered_metric_matches = []
        for position, matched_metric in sorted(metric_matches):
            if matched_metric not in {item[1] for item in ordered_metric_matches}:
                ordered_metric_matches.append((position, matched_metric))
        metric_confident = len(ordered_metric_matches) == 1
        percentage_claim = unit == "%"
        prior_metric_matches = [item for item in metric_matches if item[0] <= relative_pos]
        percentage_metrics = [
            item
            for item in metric_matches
            if item[1] in {"Capex/OCF", "Operating margin"} and abs(item[0] - relative_pos) <= 80
        ]
        if unit in {"b", "$"} and prior_metric_matches:
            nearest_prior_metric = min(
                prior_metric_matches,
                key=lambda item: (
                    relative_pos - item[0],
                    METRIC_PRIORITY.get(item[1], 99),
                ),
            )
            metric = nearest_prior_metric[1]
            prior_metric_types = {item[1] for item in prior_metric_matches}
            metric_confident = (
                len(prior_metric_types) == 1 and relative_pos - nearest_prior_metric[0] <= 80
            )
        elif percentage_claim and percentage_metrics:
            metric = min(
                percentage_metrics,
                key=lambda item: (
                    abs(item[0] - relative_pos),
                    METRIC_PRIORITY.get(item[1], 99),
                ),
            )[1]
            metric_confident = True
        elif len(ordered_metric_matches) == len(ordered_numbers):
            number_index = min(
                range(len(ordered_numbers)),
                key=lambda index: abs(ordered_numbers[index][0] - relative_pos),
            )
            metric = ordered_metric_matches[number_index][1]
            metric_confident = True
        else:
            metric = min(
                metric_matches,
                key=lambda item: (
                    abs(item[0] - relative_pos),
                    METRIC_PRIORITY.get(item[1], 99),
                ),
            )[1]

        period_matches = [
            (match.start(), match.end(), f"fy{match.group(1)}")
            for match in re.finditer(r"\bFY\s*(20\d{2})\b", clause, re.I)
        ]
        period = None
        period_confident = False

        # Distance alone reverses comparative pairs such as
        # ``52.5B in FY2024 to 91.4B in FY2025``: FY2024 is closer to 91.4.
        # Bind a following period only when prose explicitly links it to the
        # value, and never jump across another numeric claim.
        following_periods = []
        for period_start, _period_end, fact_period in period_matches:
            if period_start < relative_pos:
                continue
            between = clause[relative_pos:period_start]
            intervening = [
                number_pos
                for number_pos, _number in ordered_numbers
                if relative_pos < number_pos < period_start
            ]
            explicit_link = re.search(r"(?:\(|\b(?:in|en|for)\s*)$", between, re.I)
            if not intervening and explicit_link and len(between) <= 48:
                following_periods.append((period_start, fact_period))
        if following_periods:
            _period_start, period = min(following_periods)
            period_confident = True
        else:
            # Support subject-first claims (``FY2025 capex was $131.8B``), but
            # do not inherit a period across another number or a long clause.
            prior_periods = []
            for _period_start, period_end, fact_period in period_matches:
                if period_end > relative_pos:
                    continue
                between = clause[period_end:relative_pos]
                intervening = [
                    number_pos
                    for number_pos, _number in ordered_numbers
                    if period_end < number_pos < relative_pos
                ]
                comparative_bridge = re.search(
                    r"\b(?:from|to|between|growth|grew|rising|rose|range|ratios?|"
                    r"de|a|entre|croissance|hausse|progression)\b",
                    _deaccent(between.lower()),
                )
                if not intervening and not comparative_bridge and relative_pos - period_end <= 64:
                    prior_periods.append((period_end, fact_period))
            if prior_periods:
                _period_end, period = max(prior_periods)
                period_confident = True
        candidates = [
            fact_value
            for (fact_company, fact_metric, fact_period), fact_value in facts.items()
            if fact_company == company.lower()
            and fact_metric == metric.lower()
            and (period is None or fact_period == period)
        ]
        if candidates and any(close(value, candidate) for candidate in candidates):
            return True
        if percentage_claim:
            claim_prefix = _deaccent(clause[max(0, relative_pos - 72) : relative_pos].lower())
            if re.search(
                r"\b(?:grew|increased|rose|growth|hausse|croissance|progression)\b"
                r".{0,32}\b(?:by|de)\b",
                claim_prefix,
            ):
                return None  # A rate of change is a derivation, not the metric level.
        same_company_period_values = [
            fact_value
            for (fact_company, _fact_metric, fact_period), fact_value in facts.items()
            if fact_company == company.lower() and period is not None and fact_period == period
        ]
        metric_directly_precedes_value = any(
            matched_metric == metric and 0 <= relative_pos - metric_position <= 64
            for metric_position, matched_metric in metric_matches
        )
        if (
            same_company_period_values
            and any(close(value, candidate) for candidate in same_company_period_values)
            and not metric_directly_precedes_value
        ):
            return None
        if company_confident and metric_confident and period_confident:
            return False
        return None

    def _is_derived(x: float, neighbors: list[float]) -> bool:
        # x is a shown derivation if it equals delta / growth% / ratio% / multiple
        # of two corpus-valid numbers that appear right next to it in the report.
        for a in neighbors:
            for b in neighbors:
                if a == b or b == 0:
                    continue
                candidates = (
                    (abs(a - b), 0.25, 0.01),
                    (a / b, 0.06, 0.01),
                    ((a / b - 1.0) * 100.0, 0.6, 0.02),
                    (a / b * 100.0, 0.6, 0.02),
                )
                if any(
                    close(x, candidate, tol_abs=tol_abs, tol_rel=tol_rel)
                    for candidate, tol_abs, tol_rel in candidates
                ):
                    return True
        return False

    def _derivation_status(x: float, pos: int) -> str:
        """Return valid, invalid, or unverifiable for a displayed derivation."""
        boundary = report_md.rfind("\n\n", 0, pos)
        start = 0 if boundary == -1 else boundary + 2
        end = report_md.find("\n\n", pos)
        paragraph = report_md[start : len(report_md) if end == -1 else end]
        relative_pos = pos - start

        company_matches = [
            (match.start(), company)
            for company in companies
            for match in re.finditer(rf"\b{re.escape(company)}\b", paragraph, re.I)
        ]
        prior_companies = [item for item in company_matches if item[0] <= relative_pos]
        if prior_companies:
            company = max(prior_companies)[1]
        elif company_matches:
            company = min(company_matches)[1]
        else:
            return "unverifiable"

        metric_matches = []
        for metric, aliases in METRIC_ALIASES.items():
            for alias in aliases:
                for match in re.finditer(
                    re.escape(_deaccent(alias.lower())), _deaccent(paragraph.lower())
                ):
                    metric_matches.append(
                        (abs(match.start() - relative_pos), match.start(), metric)
                    )
        if not metric_matches:
            return "unverifiable"
        prior_metrics = [item for item in metric_matches if item[1] <= relative_pos]
        metric = min(prior_metrics or metric_matches)[2]

        following = report_md[pos : pos + 100]
        explicit_pair = re.search(
            r"(?:from|between)\s+FY\s*(20\d{2}).{0,30}?FY\s*(20\d{2})",
            following,
            re.I,
        )
        if explicit_pair:
            periods = [f"fy{explicit_pair.group(1)}", f"fy{explicit_pair.group(2)}"]
        else:
            period_boundary = report_md.rfind(". ", 0, pos)
            sentence_start = max(period_boundary + 2, report_md.rfind("\n", 0, pos) + 1)
            subject_period = re.search(r"\bFY\s*(20\d{2})\b", report_md[sentence_start:pos], re.I)
            comparison_period = re.search(r"\bFY\s*(20\d{2})\b", following, re.I)
            periods = (
                [f"fy{subject_period.group(1)}", f"fy{comparison_period.group(1)}"]
                if subject_period and comparison_period
                else []
            )
        shown_numbers = [
            (value, unit, position)
            for value, unit, position in extract_numbers(paragraph)
            if abs(position - relative_pos) > 2 and not _is_year(value)
        ]
        if len(periods) == 2:
            displayed_operands = []
            for period in periods:
                year = period.removeprefix("fy")
                period_positions = [
                    match.start()
                    for match in re.finditer(rf"\bFY\s*{re.escape(year)}\b", paragraph, re.I)
                ]
                prior_period_positions = [
                    position for position in period_positions if position < relative_pos
                ]
                if prior_period_positions:
                    period_positions = prior_period_positions
                raw_candidates = [
                    (value, position)
                    for value, unit, position in shown_numbers
                    if unit not in {"%", "x", "\u00d7"}
                ]
                if not period_positions or not raw_candidates:
                    return "unverifiable"
                displayed_operands.append(
                    min(
                        raw_candidates,
                        key=lambda item: min(
                            abs(item[1] - period_position) for period_position in period_positions
                        ),
                    )[0]
                )
            if _is_derived(x, displayed_operands):
                return "valid"
            expected_operands = [
                facts.get((company.lower(), metric.lower(), period)) for period in periods
            ]
            if all(expected is not None for expected in expected_operands) and all(
                close(displayed, expected)
                for displayed, expected in zip(displayed_operands, expected_operands, strict=True)
            ):
                return "invalid"
            return "unverifiable"
        else:
            grounded_operands = [
                value for value, _unit, _position in shown_numbers if in_whitelist(value, whitelist)
            ]
            if len(grounded_operands) >= 2 and _is_derived(x, grounded_operands):
                return "valid"
        return "unverifiable"

    def _derivable_from_corpus(x: float, pos: int) -> bool:
        boundary = report_md.rfind("\n\n", 0, pos)
        start = 0 if boundary == -1 else boundary + 2
        end = report_md.find("\n\n", pos)
        paragraph = report_md[start : len(report_md) if end == -1 else end]
        relative_pos = pos - start
        company_matches = [
            (abs(match.start() - relative_pos), company)
            for company in companies
            for match in re.finditer(rf"\b{re.escape(company)}\b", paragraph, re.I)
        ]
        if not company_matches:
            return False
        company = min(company_matches)[1]
        normalized_paragraph = _deaccent(paragraph.lower())
        metric_matches = [
            (abs(match.start() - relative_pos), metric)
            for metric, aliases in METRIC_ALIASES.items()
            for alias in aliases
            for match in re.finditer(re.escape(_deaccent(alias.lower())), normalized_paragraph)
        ]
        if not metric_matches:
            return False
        metric = min(
            metric_matches,
            key=lambda item: (item[0], METRIC_PRIORITY.get(item[1], 99)),
        )[1]
        operands = [
            value
            for (fact_company, fact_metric, _period), value in facts.items()
            if fact_company == company.lower() and fact_metric == metric.lower()
        ]
        return len(operands) >= 2 and _is_derived(x, operands)

    hedge_words = (
        "supérieur",
        "superieur",
        "inférieur",
        "inferieur",
        "plus de",
        "moins de",
        "environ",
        "près de",
        "pres de",
        "dans les",
        "au-dessus",
        "au dessus",
        "de l'ordre",
        "autour de",
        "around",
        "about",
        "over ",
        "above",
        "up to",
        "jusqu",
        "~",
        "≈",
        "à peu près",
        "approximately",
    )
    fabricated = []
    unverifiable = []
    grounded_ambiguous = []
    prose_contradictions = []
    for val, unit, pos in report_nums:
        if not unit and 1990 <= val <= 2100 and float(val).is_integer():
            continue  # years
        if _in_ignore(pos):
            continue  # code example / section number, not a grounding claim
        if not in_whitelist(val, whitelist):
            # "72,215 milliards" is FR 3-decimal (72.215), not EN thousands
            # (72215). Fallback only — a primary parse that matches the corpus
            # (e.g. "85,002" as 85002) keeps its reading.
            alt = alternate_comma_value(report_md, pos)
            if alt is not None and in_whitelist(alt, whitelist):
                val = alt
        line_start = report_md.rfind("\n", 0, pos) + 1
        line_end = report_md.find("\n", pos)
        line = report_md[line_start : len(report_md) if line_end == -1 else line_end]
        if mode == "conceptual" and "=" in line and re.search(r"\d\s*[x\u00d7]?\s*[+*/-]", line):
            continue  # pedagogical arithmetic example, not an empirical claim
        citations = _line_citations(pos)
        citation_support_failed = False
        if mode == "conceptual" and citations:
            cited_value_exists = any(
                any(close(val, source_value) for source_value in source_numbers.get(citation, []))
                for citation in citations
            )
            cited_origin_exists = any(
                _source_origins(source_by_id.get(citation, {}), document_names)
                for citation in citations
            )
            if cited_value_exists and (
                not enforce_source_provenance
                or (in_whitelist(val, whitelist) and cited_origin_exists)
            ):
                continue
            citation_support_failed = True
        elif mode == "numeric" and unit not in {"x", "\u00d7"}:
            attribution_valid = _fact_attribution_is_valid(val, unit, pos)
            if attribution_valid is True:
                continue
            if attribution_valid is False:
                ctx = report_md[max(0, pos - 40) : pos + 20].replace("\n", " ")
                prose_contradictions.append(
                    {
                        "value": val,
                        "unit": unit,
                        "context": ctx.strip(),
                        "reason": "contradicted_fact",
                    }
                )
                continue
        # skip round-ten integers used as a hedge/threshold ("marges > 30%"):
        # a reasonable summary, not an invented precise statistic.
        pre = report_md[max(0, pos - 28) : pos].lower()
        if float(val).is_integer() and val % 10 == 0 and any(h in pre for h in hedge_words):
            continue
        # skip correct derivations shown next to their operands (growth %, delta,
        # ratio, multiple) — first-level analysis the task explicitly asks for.
        window = report_md[max(0, pos - 160) : pos + 160]
        neighbors = [v for v, _u, _p in extract_numbers(window) if in_whitelist(v, whitelist)]
        derivation_status = _derivation_status(val, pos)
        if (unit == "%" and _is_derived(val, neighbors)) or derivation_status == "valid":
            continue
        ctx = report_md[max(0, pos - 40) : pos + 20].replace("\n", " ")
        item = {"value": val, "unit": unit, "context": ctx.strip()}
        cited_numbers = [
            source_value
            for citation in citations
            for source_value in source_numbers.get(citation, [])
        ]
        citation_supports_number = any(close(val, source_value) for source_value in cited_numbers)
        citation_supports_derivation = _is_derived(val, cited_numbers)
        if (
            mode == "numeric"
            and citations
            and not in_whitelist(val, whitelist)
            and not citation_supports_number
            and not citation_supports_derivation
        ):
            # A citation asserts source support. Without a demonstrated local
            # or cited-source derivation, an out-of-corpus number is laundering
            # regardless of whether variation language looks plausible.
            item["reason"] = "citation_laundering"
            fabricated.append(item)
            continue
        if derivation_status == "invalid":
            item["reason"] = "invalid_derivation"
            unverifiable.append(item)
            continue
        derivation_context = report_md[max(0, pos - 100) : pos + 100].lower()
        looks_derived = bool(
            re.search(
                r"increase|growth|grew|rose|rise|surpass|exceed|delta|yoy|year-over-year|"
                r"year over year|multiple|hausse|croissance|progress|depass",
                _deaccent(derivation_context),
            )
        )
        corpus_derivable = mode == "numeric" and _derivable_from_corpus(val, pos)
        if citation_support_failed:
            item["reason"] = "citation_laundering"
            fabricated.append(item)
        elif in_whitelist(val, whitelist):
            item["reason"] = "grounded_ambiguous_attribution"
            grounded_ambiguous.append(item)
        elif corpus_derivable:
            item["reason"] = "derivable_but_operands_not_shown"
            unverifiable.append(item)
        elif mode == "numeric" and guidance_re.search(_deaccent(derivation_context)):
            item["reason"] = "guidance_derivation_not_locally_verifiable"
            unverifiable.append(item)
        elif citations:
            item["reason"] = "citation_laundering"
            fabricated.append(item)
        else:
            item["reason"] = "unsupported_derivation" if looks_derived else "unsupported_uncited"
            unverifiable.append(item)

    # ---- agenda discipline (distractors) ----
    # Off-theme FACTS (in-scope companies are fine; citing their off-theme figure is not).
    dblock = ak.get("distractors", {}) or {}
    in_scope = {c.lower() for c in companies}
    distractor_hits = []
    for f in dblock.get("facts", []) or []:
        # Detect by the off-theme TOPIC (keyword), not the value: financial values
        # collide across companies, but an on-theme report won't mention the topic.
        kw = str(f.get("keyword") or f.get("metric") or "")
        if kw and re.search(re.escape(kw), report_body, re.I):
            distractor_hits.append(f"{f.get('company')} {f.get('metric')} ({f.get('value')})")
    # Truly off-scope companies (e.g. consumer-platforms exercise).
    for c in dblock.get("companies", []) or []:
        if c.lower() not in in_scope and re.search(rf"\b{re.escape(c)}\b", report_body):
            distractor_hits.append(c)
    distractor_hits = sorted(set(distractor_hits))

    # ---- tone neutrality ----
    forbidden = ((spec.get("tone") or {}).get("forbidden_language")) or []
    tone_hits = sorted({w for w in forbidden if re.search(re.escape(w), report_body, re.I)})

    # ---- format ----
    req_chapters = (spec.get("required_chapters")) or []
    chapters_present = [
        c
        for c in req_chapters
        if re.search(rf"^#{{1,3}}\s.*{re.escape(c)}", report_body, re.I | re.M)
    ]
    parsed_tables = parse_tables(report_body)
    n_tables = len(parsed_tables)
    word_count = len(report_body.split())
    table_spec = spec.get("embedded_tables", {}) or {}
    expected_columns = table_spec.get("expected_columns") or []
    normalized_expected_columns = {
        _deaccent(str(column).lower()).replace(" ", "") for column in expected_columns
    }
    parseable_tables = 0
    for table in parsed_tables:
        header = {_deaccent(cell.lower()).replace(" ", "") for cell in table[0]}
        if not normalized_expected_columns or normalized_expected_columns <= header:
            parseable_tables += 1

    cited_ids = {
        citation for citation in _citation_ids(report_body) if citation not in valid_source_ids
    }
    external_urls = re.findall(r"https?://[^\s)>]+", report_body, re.I)
    source_violations = []
    if cited_ids:
        source_violations.append(f"unknown citation IDs: {', '.join(sorted(cited_ids))}")
    source_spec = spec.get("only_provided_sources", {}) or {}
    if source_spec.get("forbid_web_citations") and external_urls:
        source_violations.append("external URL cited in report body")
    source_manifest_path = exercise / "source_manifest.yaml"
    if source_manifest_path.is_file():
        source_manifest = yaml.safe_load(source_manifest_path.read_text(encoding="utf-8")) or {}
        data_roots = [exercise / "corpus"]
        if len(run_dir.parents) >= 3:
            data_roots.append(run_dir.parents[2] / "data")
        for expected_source in source_manifest.get("sources") or []:
            file_pattern = expected_source["file_pattern"]
            candidates = [
                path for root in data_roots for path in root.glob(file_pattern) if path.is_file()
            ]
            source_file = next(
                (
                    path
                    for path in candidates
                    if _sha256_bytes(path.read_bytes()) == expected_source["sha256"]
                ),
                None,
            )
            if not candidates:
                source_violations.append(f"frozen source unavailable: {file_pattern}")
                continue
            if source_file is None:
                source_violations.append(f"frozen source hash mismatch: {file_pattern}")

    # ---- root cause via intermediate artifacts (sources.json) ----
    src_blob = "\n".join(
        (s.get("content") or "") + " " + (s.get("file_name") or "") for s in sources
    )
    missing = [m for m in must if m not in covered]
    root_cause = {"n_retrieved_sources": len(sources)}

    def _metric_near_value(text: str, metric: str, pos: int) -> bool:
        aliases = METRIC_ALIASES.get(metric, (metric.lower(),))
        span = _deaccent(text[max(0, pos - 140) : pos + 140].lower())
        return any(_deaccent(alias.lower()) in span for alias in aliases)

    def _retrieved_numeric(m) -> bool:
        company, metric, _fy, value = m
        company_pat = re.compile(rf"\b{re.escape(company)}\b", re.I)
        for source in sources:
            text = " ".join(
                part
                for part in (source.get("topic"), source.get("file_name"), source.get("content"))
                if part
            )
            if not company_pat.search(text):
                continue
            for found, _unit, pos in extract_numbers(text):
                if close(value, found) and _metric_near_value(text, metric, pos):
                    return True
        return False

    def _retrieved(m) -> bool:
        if mode == "conceptual":
            return any(
                _contains_anchor(src_blob, anchor) for anchor in (m.get("anchors_any") or [])
            )
        return _retrieved_numeric(m)

    def _label(m) -> str:
        return m.get("concept", m.get("id", "?")) if isinstance(m, dict) else f"{m[0]} {m[1]}"

    if not sources or not src_blob.strip():
        root_cause["verdict"] = (
            "knowledge_preparation/alimentation: corpus not loaded (0 usable sources)"
        )
    else:
        not_retrieved = [m for m in missing if not _retrieved(m)]
        retrieved_not_written = [m for m in missing if _retrieved(m)]
        root_cause["missing_not_retrieved"] = [_label(m) for m in not_retrieved]
        root_cause["missing_retrieved_but_absent_from_report"] = [
            _label(m) for m in retrieved_not_written
        ]
        if not missing:
            root_cause["verdict"] = "ok: all required items covered"
        elif not_retrieved and not retrieved_not_written:
            root_cause["verdict"] = (
                "search/retrieval: required items were not retrieved into the corpus"
            )
        elif retrieved_not_written and not not_retrieved:
            root_cause["verdict"] = (
                "writer/agenda: items were retrieved but omitted from the report"
            )
        else:
            root_cause["verdict"] = "mixed: some items not retrieved, some retrieved-but-omitted"

    failed_requirement_labels = [
        result["label"] for result in requirement_results if result["status"] != "pass"
    ]
    root_cause["failed_requirements"] = failed_requirement_labels
    root_cause["wrong_claims"] = len(wrongs) + len(contradictions) + len(prose_contradictions)
    root_cause["fabricated_claims"] = len(fabricated)
    root_cause["unverifiable_claims"] = len(unverifiable)
    if source_violations:
        root_cause["verdict"] = "input/provenance: frozen source contract is not satisfied"
    elif fabricated:
        root_cause["verdict"] = "writer/grounding: fabricated factual claims"
    elif wrongs or contradictions or prose_contradictions:
        root_cause["verdict"] = "writer/factuality: claims contradict the frozen corpus"
    elif failed_requirement_labels and not missing:
        root_cause["verdict"] = "writer/contract: non-numeric report requirements were omitted"

    # ---- composite score (severe; fabrication is a hard gate) ----
    axes = ((spec.get("scoring") or {}).get("axes")) or {}
    w_cov = (axes.get("coverage") or {}).get("weight", 0.40)
    w_acc = (axes.get("accuracy") or {}).get("weight", 0.30 if mode == "numeric" else 0.0)
    w_fmt = (axes.get("format") or {}).get("weight", 0.20)
    cap = float((axes.get("fabrication_gate") or {}).get("hard_cap_if_any", 40))
    accuracy_errors = len(wrongs) + len(contradictions)
    accuracy = (
        len(matches) / (len(matches) + accuracy_errors)
        if (matches or accuracy_errors)
        else (1.0 if mode == "conceptual" else 0.0)
    )
    w_agenda = (axes.get("agenda_discipline") or {}).get("weight", 0.0)
    w_tone = (axes.get("tone_neutrality") or {}).get("weight", 0.0)
    min_tables = table_spec.get("min_tables", 0)
    length_spec = spec.get("length", {}) or {}
    min_words, max_words = length_spec.get("min_words"), length_spec.get("max_words")
    format_checks = []
    if req_chapters:
        format_checks.append(len(chapters_present) / len(req_chapters))
    if table_spec.get("required") or min_tables:
        format_checks.append(1.0 if n_tables >= min_tables else 0.0)
    if normalized_expected_columns:
        format_checks.append(1.0 if parseable_tables >= min_tables else 0.0)
    if min_words is not None or max_words is not None:
        format_checks.append(
            1.0
            if (min_words is None or word_count >= min_words)
            and (max_words is None or word_count <= max_words)
            else 0.0
        )
    fmt = sum(format_checks) / len(format_checks) if format_checks else 1.0
    # agenda/tone as positive axes: full credit when clean, decaying per violation.
    agenda_score = max(0.0, 1.0 - 0.34 * len(distractor_hits))
    tone_score = max(0.0, 1.0 - 0.34 * len(tone_hits))
    score = 100.0 * (
        w_cov * coverage
        + w_acc * accuracy
        + w_fmt * fmt
        + w_agenda * agenda_score
        + w_tone * tone_score
    )
    unverifiable_spec = spec.get("unverifiable_claims", {}) or {}
    unverifiable_penalty = float(unverifiable_spec.get("per_item_penalty", 1.0))
    score -= unverifiable_penalty * len(unverifiable)
    prose_penalty = float(unverifiable_spec.get("prose_contradiction_penalty", 5.0))
    score -= prose_penalty * len(prose_contradictions)
    # Fabrication is a hard cap. Unverifiable prose receives a bounded diagnostic
    # penalty and only blocks qualification when its configured volume cap is exceeded.
    if fabricated:
        score = min(score, cap)
    if wrongs or contradictions:
        score = min(score, 60.0)
    score = round(max(0.0, min(100.0, score)), 1)

    critical_requirement_failures = [
        result["label"]
        for result in requirement_results
        if result["critical"] and result["status"] != "pass"
    ]
    format_blockers = []
    if req_chapters and len(chapters_present) != len(req_chapters):
        format_blockers.append("required chapters missing")
    if (table_spec.get("required") or min_tables) and n_tables < min_tables:
        format_blockers.append("insufficient tables")
    if min_words is not None and word_count < min_words:
        format_blockers.append("report too short")
    if max_words is not None and word_count > max_words:
        format_blockers.append("report too long")
    max_unverifiable = unverifiable_spec.get("max_for_qualification")

    qualification_blockers = []
    if critical_requirement_failures:
        qualification_blockers.append("critical requirements failed")
    if wrongs or contradictions or prose_contradictions:
        qualification_blockers.append("wrong factual claims")
    if fabricated:
        qualification_blockers.append("fabricated claims")
    if max_unverifiable is not None and len(unverifiable) > int(max_unverifiable):
        qualification_blockers.append("too many unverifiable numeric claims")
    if format_blockers:
        qualification_blockers.append("report contract not met")
    if source_violations:
        qualification_blockers.append("source policy violations")

    answer_key_path = exercise / "answer_key.yaml"
    spec_path = exercise / "spec.yaml"
    sources_payload = json.dumps(sources, ensure_ascii=False, sort_keys=True).encode()
    provenance = {
        "scorer_sha256": _sha256_bytes(Path(__file__).read_bytes()),
        "answer_key_sha256": _sha256_bytes(answer_key_path.read_bytes()),
        "spec_sha256": _sha256_bytes(spec_path.read_bytes()),
        "corpus_sha256": _hash_tree(exercise / "corpus"),
        "report_sha256": _sha256_bytes(report_md.encode()),
        "sources_sha256": _sha256_bytes(sources_payload),
    }
    if source_manifest_path.is_file():
        provenance["source_manifest_sha256"] = _sha256_bytes(source_manifest_path.read_bytes())

    return {
        "exercise": exercise.name,
        "score": score,
        "qualified": not qualification_blockers,
        "qualification": {
            "passed": not qualification_blockers,
            "blockers": qualification_blockers,
            "critical_requirement_failures": critical_requirement_failures,
            "format_blockers": format_blockers,
        },
        "requirements": requirement_results,
        "coverage": {"hit": len(covered), "total": len(must), "pct": round(coverage, 3)},
        "accuracy": {
            "matching": len(matches),
            "wrong": accuracy_errors,
            "pct": round(accuracy, 3),
            "wrong_details": [f"{c} {m}: report={v} vs corpus={t}" for c, m, v, t in wrongs]
            + contradictions,
        },
        "fabrication": {"count": len(fabricated), "items": fabricated[:20]},
        "prose_contradictions": {
            "count": len(prose_contradictions),
            "items": prose_contradictions[:20],
        },
        "unverifiable": {
            "count": len(unverifiable),
            "max_for_qualification": max_unverifiable,
            "items": unverifiable[:20],
        },
        "grounded_ambiguous": {
            "count": len(grounded_ambiguous),
            "items": grounded_ambiguous[:20],
        },
        "agenda_discipline": {"distractors_cited": distractor_hits},
        "tone": {"violations": tone_hits},
        "format": {
            "chapters_present": len(chapters_present),
            "chapters_required": len(req_chapters),
            "tables": n_tables,
            "parseable_tables": parseable_tables,
            "word_count": word_count,
            "min_words": min_words,
            "max_words": max_words,
        },
        "source_policy": {"violations": source_violations},
        "root_cause": root_cause,
        "provenance": provenance,
    }


def _locate_report(run_dir: Path, stats: dict) -> Path | None:
    name = stats.get("report_file")
    for base in (stats.get("output_dir"), "output", "."):
        if base and name and (Path(base) / name).is_file():
            return Path(base) / name
    hits = list(run_dir.glob("*final_report*.md"))
    return hits[0] if hits else None


def main() -> None:
    p = argparse.ArgumentParser(description="Deterministic grader for research exercises")
    p.add_argument("run_dir", help="benchmarks/runs/<run> directory")
    p.add_argument("--exercise", required=True, help="evaluations/exercises/<name> directory")
    p.add_argument("--report", help="explicit path to the report .md (else located via stats.json)")
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    exercise = Path(args.exercise)
    stats = json.loads((run_dir / "stats.json").read_text(encoding="utf-8"))
    sources_path = run_dir / "sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.is_file() else []

    report_path = Path(args.report) if args.report else _locate_report(run_dir, stats)
    if not report_path or not report_path.is_file():
        raise SystemExit(f"report not found for {run_dir}")
    report_md = report_path.read_text(encoding="utf-8")

    result = grade(run_dir, exercise, report_md, sources)
    (run_dir / "det_grade.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    r = result
    print(f"\n=== {r['exercise']}  |  SCORE {r['score']}/100 ===")
    print(
        f"coverage : {r['coverage']['hit']}/{r['coverage']['total']} headline facts ({r['coverage']['pct']:.0%})"
    )
    print(f"accuracy : {r['accuracy']['matching']} ok / {r['accuracy']['wrong']} WRONG")
    for w in r["accuracy"]["wrong_details"]:
        print(f"           ✗ {w}")
    print(f"fabrication (ZERO TOL): {r['fabrication']['count']}")
    for it in r["fabrication"]["items"]:
        print(f"           ⚠ {it['value']}{it['unit']}  «…{it['context']}…»")
    print(f"distractors cited: {r['agenda_discipline']['distractors_cited'] or 'none'}")
    print(f"tone violations  : {r['tone']['violations'] or 'none'}")
    print(
        f"format : {r['format']['chapters_present']}/{r['format']['chapters_required']} chapters, {r['format']['tables']} tables"
    )
    print(f"ROOT CAUSE: {r['root_cause']['verdict']}")


if __name__ == "__main__":
    main()
