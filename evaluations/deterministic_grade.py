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
import json
import re
import unicodedata
from pathlib import Path

import yaml


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

# ---------------------------------------------------------------------------
# Number parsing / normalization
# ---------------------------------------------------------------------------

# A number token, optionally signed/approx, optional $, with optional unit suffix.
_NUM = re.compile(
    r"(?P<sign>[-+~≈]?)\s*\$?\s*(?P<body>\d[\d.,]*\d|\d)\s*"
    r"(?P<unit>%|bps|Md\$|B\b|billions?|M\b|millions?|k\b|thousands?)?",
    re.IGNORECASE,
)


def to_float(body: str) -> float | None:
    """Parse a numeric body, handling thousands separators and French decimals."""
    s = body.strip()
    if "," in s and "." in s:
        # both present: comma = thousands, dot = decimal
        s = s.replace(",", "")
    elif "," in s:
        # comma only: decimal if 1-2 trailing digits (French), else thousands
        frac = s.rsplit(",", 1)[1]
        s = s.replace(",", "." if (s.count(",") == 1 and len(frac) <= 2) else "")
    try:
        return float(s)
    except ValueError:
        return None


def extract_numbers(text: str) -> list[tuple[float, str, int]]:
    """Return (value, unit, position) for every specific number in the text.

    Keeps numbers that carry financial semantics (a unit, a decimal, or magnitude);
    drops bare small integers that are almost always structural (counts, list items)."""
    out: list[tuple[float, str, int]] = []
    for m in _NUM.finditer(text):
        val = to_float(m.group("body"))
        if val is None:
            continue
        unit = (m.group("unit") or "").lower().strip()
        has_decimal = "." in m.group("body") or ("," in m.group("body"))
        # keep if: has a unit, or a decimal, or is a 4-digit year, or magnitude >= 100
        is_year = 1990 <= val <= 2100 and float(val).is_integer()
        if unit or has_decimal or is_year or abs(val) >= 100:
            out.append((val, unit, m.start()))
    return out


def close(a: float, b: float, tol_abs: float = 0.15, tol_rel: float = 0.01) -> bool:
    return abs(a - b) <= max(tol_abs, tol_rel * max(abs(a), abs(b)))


# Change/derivation language: a number nearby is first-level trend analysis (growth,
# delta, ratio, multiple) the data-prep task explicitly asks for — not a fabricated
# primary fact. Used as a backstop to the operand-based derivation check.
_DERIVED_CTX = (
    "increase", "increased", "rise", "rose", "risen", "grew", "grow", "growth",
    "growing", "jump", "jumped", "doubl", "tripl", "fold", "year-over-year",
    "year over year", "yoy", "single-year", "basis point", "bps", "x increase",
    "cagr", "expand", "compress", "declin", "decreas", "up from", "down from",
    "rise from", "increase from", "vs.", "versus", "delta", "range", "trajectory",
    "escalation", "nearly doubled", "represents a", "climbed", "diverged",
    "exceed", "surpass", "shy of", "above the", "below the", "more than",
)


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
    ("%ocf", "Capex/OCF"),          # "Capex as % OCF" -> intensity, not OCF
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


def load_corpus(exercise: Path) -> dict:
    """Whitelist of every corpus number + a fact index from key_metrics.csv."""
    corpus_dir = exercise / "corpus"
    whitelist: list[float] = []
    for f in corpus_dir.glob("*"):
        if f.is_file():
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


def table_cells(tables, companies: list[str]) -> list[tuple[str, str, float]]:
    """Yield (company, metric_key, value) from tables whose rows are companies."""
    cmap = {c.lower(): c for c in companies}
    out = []
    for tbl in tables:
        header = [_deaccent(h.lower().replace(" ", "")) for h in tbl[0]]
        # map each column index to a metric key
        col_metric = {}
        for i, h in enumerate(header):
            for k, canon in METRIC_ORDER:
                if k in h:
                    col_metric[i] = canon
                    break
        for row in tbl[1:]:
            if not row:
                continue
            co = next((cmap[c] for c in cmap if c in row[0].lower()), None)
            if not co:
                continue
            for i, cell in enumerate(row):
                if i in col_metric:
                    # only single-value cells are a fact; skip multi-year lists
                    # ("FY2020 40.1; …; FY2025 131.8") and strip year tokens.
                    nums = [n for n in extract_numbers(cell) if not _is_year(n[0])]
                    if len(nums) == 1:
                        out.append((co, col_metric[i], nums[0][0]))
    return out


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

    if mode == "conceptual":
        # ---- coverage by concept anchors (mechanical); no numeric accuracy ----
        must = ak.get("must_cover", [])
        covered = [
            c for c in must
            if any(re.search(re.escape(a), report_md, re.I) for a in (c.get("anchors_any") or []))
        ]
        coverage = len(covered) / len(must) if must else 0.0
        cells, matches, wrongs = [], [], []
    else:
        # ---- derived numeric must-cover: latest-FY headline per company ----
        headline = ["Revenue", "Operating margin", "Capex", "Capex/OCF"]
        must = []
        for co in companies:
            fy = latest_fy.get(co)
            for metric in headline:
                v = facts.get((co.lower(), metric.lower(), (fy or "").lower()))
                if v is not None:
                    must.append((co, metric, fy, v))

        cells = table_cells(parse_tables(report_md), companies)

        # coverage (recall): a must-fact is covered if ANY cell matches it
        covered = [m for m in must if any(c[0] == m[0] and c[1] == m[1] and close(c[2], m[3]) for c in cells)]
        coverage = len(covered) / len(must) if must else 0.0

        # accuracy (precision): EVERY stated cell must match some corpus FY.
        # Iterate all cells (not deduped by co/metric) so an internally inconsistent
        # report (right value in one table, wrong in another) is caught.
        matches, wrongs, seen = [], [], set()
        for co, metric, val in cells:
            any_fy = [v for (c, m, _f), v in facts.items() if c == co.lower() and m == metric.lower()]
            if not any_fy:
                continue
            key = (co, metric, round(val, 2))
            if key in seen:
                continue
            seen.add(key)
            if any(close(val, v) for v in any_fy):
                matches.append((co, metric, val))
            else:
                truth = facts.get((co.lower(), metric.lower(), (latest_fy.get(co) or "").lower()))
                wrongs.append((co, metric, val, truth))

    # ---- fabrication gate (ZERO TOLERANCE) ----
    report_nums = extract_numbers(report_md)
    # Spans where numbers are NOT grounding claims: fenced/inline code (example data)
    # and heading lines (section numbers like "3.1"). Skip fabrication checks there.
    _ignore = []
    for _m in re.finditer(r"```.*?```", report_md, re.S):
        _ignore.append((_m.start(), _m.end()))
    for _m in re.finditer(r"`[^`\n]*`", report_md):
        _ignore.append((_m.start(), _m.end()))
    for _m in re.finditer(r"(?m)^#{1,6}.*$", report_md):
        _ignore.append((_m.start(), _m.end()))

    def _in_ignore(p: int) -> bool:
        return any(a <= p < b for a, b in _ignore)

    def _is_derived(x: float, neighbors: list[float]) -> bool:
        # x is a shown derivation if it equals delta / growth% / ratio% / multiple
        # of two corpus-valid numbers that appear right next to it in the report.
        for a in neighbors:
            for b in neighbors:
                if a == b or b == 0:
                    continue
                for cand in (abs(a - b), a / b, (a / b - 1.0) * 100.0, a / b * 100.0):
                    if close(x, cand, tol_abs=0.6, tol_rel=0.02):
                        return True
        return False

    hedge_words = (
        "supérieur", "superieur", "inférieur", "inferieur", "plus de", "moins de",
        "environ", "près de", "pres de", "dans les", "au-dessus", "au dessus",
        "de l'ordre", "autour de", "around", "about", "over ", "above", "up to",
        "jusqu", "~", "≈", "à peu près",
    )
    fabricated = []
    for val, unit, pos in report_nums:
        if 1990 <= val <= 2100 and float(val).is_integer():
            continue  # years
        if _in_ignore(pos):
            continue  # code example / section number, not a grounding claim
        if in_whitelist(val, whitelist):
            continue
        # skip round-ten integers used as a hedge/threshold ("marges > 30%"):
        # a reasonable summary, not an invented precise statistic.
        pre = report_md[max(0, pos - 28) : pos].lower()
        if float(val).is_integer() and val % 10 == 0 and any(h in pre for h in hedge_words):
            continue
        # skip correct derivations shown next to their operands (growth %, delta,
        # ratio, multiple) — first-level analysis the task explicitly asks for.
        window = report_md[max(0, pos - 90) : pos + 90]
        neighbors = [v for v, _u, _p in extract_numbers(window) if in_whitelist(v, whitelist)]
        if _is_derived(val, neighbors):
            continue
        # backstop: numbers in explicit change/derivation language are first-level
        # trend analysis (the task asks for it), not fabricated primary facts.
        ctx_low = report_md[max(0, pos - 60) : pos + 40].lower()
        if any(w in ctx_low for w in _DERIVED_CTX):
            continue
        ctx = report_md[max(0, pos - 40) : pos + 20].replace("\n", " ")
        fabricated.append({"value": val, "unit": unit, "context": ctx.strip()})

    # ---- agenda discipline (distractors) ----
    # Off-theme FACTS (in-scope companies are fine; citing their off-theme figure is not).
    dblock = ak.get("distractors", {}) or {}
    in_scope = {c.lower() for c in companies}
    distractor_hits = []
    for f in dblock.get("facts", []) or []:
        # Detect by the off-theme TOPIC (keyword), not the value: financial values
        # collide across companies, but an on-theme report won't mention the topic.
        kw = str(f.get("keyword") or f.get("metric") or "")
        if kw and re.search(re.escape(kw), report_md, re.I):
            distractor_hits.append(f"{f.get('company')} {f.get('metric')} ({f.get('value')})")
    # Truly off-scope companies (e.g. consumer-platforms exercise).
    for c in dblock.get("companies", []) or []:
        if c.lower() not in in_scope and re.search(rf"\b{re.escape(c)}\b", report_md):
            distractor_hits.append(c)
    distractor_hits = sorted(set(distractor_hits))

    # ---- tone neutrality ----
    forbidden = ((spec.get("tone") or {}).get("forbidden_language")) or []
    tone_hits = sorted({w for w in forbidden if re.search(re.escape(w), report_md, re.I)})

    # ---- format ----
    req_chapters = (spec.get("required_chapters")) or []
    chapters_present = [c for c in req_chapters if re.search(rf"^#{{1,3}}\s.*{re.escape(c)}", report_md, re.I | re.M)]
    n_tables = len(parse_tables(report_md))

    # ---- root cause via intermediate artifacts (sources.json) ----
    src_blob = "\n".join((s.get("content") or "") + " " + (s.get("file_name") or "") for s in sources)
    missing = [m for m in must if m not in covered]
    root_cause = {"n_retrieved_sources": len(sources)}

    def _retrieved(m) -> bool:
        if mode == "conceptual":
            return any(re.search(re.escape(a), src_blob, re.I) for a in (m.get("anchors_any") or []))
        return any(close(m[3], v) for v, _u, _p in extract_numbers(src_blob))

    def _label(m) -> str:
        return m.get("concept", m.get("id", "?")) if isinstance(m, dict) else f"{m[0]} {m[1]}"

    if not sources or not src_blob.strip():
        root_cause["verdict"] = "knowledge_preparation/alimentation: corpus not loaded (0 usable sources)"
    else:
        not_retrieved = [m for m in missing if not _retrieved(m)]
        retrieved_not_written = [m for m in missing if _retrieved(m)]
        root_cause["missing_not_retrieved"] = [_label(m) for m in not_retrieved]
        root_cause["missing_retrieved_but_absent_from_report"] = [_label(m) for m in retrieved_not_written]
        if not missing:
            root_cause["verdict"] = "ok: all required items covered"
        elif not_retrieved and not retrieved_not_written:
            root_cause["verdict"] = "search/retrieval: required items were not retrieved into the corpus"
        elif retrieved_not_written and not not_retrieved:
            root_cause["verdict"] = "writer/agenda: items were retrieved but omitted from the report"
        else:
            root_cause["verdict"] = "mixed: some items not retrieved, some retrieved-but-omitted"

    # ---- composite score (severe; fabrication is a hard gate) ----
    axes = ((spec.get("scoring") or {}).get("axes")) or {}
    w_cov = (axes.get("coverage") or {}).get("weight", 0.40)
    w_acc = (axes.get("accuracy") or {}).get("weight", 0.30 if mode == "numeric" else 0.0)
    w_fmt = (axes.get("format") or {}).get("weight", 0.20)
    cap = float((axes.get("fabrication_gate") or {}).get("hard_cap_if_any", 40))
    accuracy = (
        len(matches) / (len(matches) + len(wrongs))
        if (matches or wrongs)
        else (1.0 if mode == "conceptual" else 0.0)
    )
    w_agenda = (axes.get("agenda_discipline") or {}).get("weight", 0.0)
    w_tone = (axes.get("tone_neutrality") or {}).get("weight", 0.0)
    min_tables = (spec.get("embedded_tables", {}) or {}).get("min_tables", 0)
    fmt = 0.5 * (len(chapters_present) / len(req_chapters) if req_chapters else 1.0) + 0.5 * (
        1.0 if n_tables >= min_tables else 0.0
    )
    # agenda/tone as positive axes: full credit when clean, decaying per violation.
    agenda_score = max(0.0, 1.0 - 0.34 * len(distractor_hits))
    tone_score = max(0.0, 1.0 - 0.34 * len(tone_hits))
    score = 100.0 * (
        w_cov * coverage + w_acc * accuracy + w_fmt * fmt
        + w_agenda * agenda_score + w_tone * tone_score
    )
    # ZERO TOLERANCE: any fabrication or wrong figure caps the grade hard.
    if fabricated:
        score = min(score, cap)
    if wrongs:
        score = min(score, 60.0)
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "exercise": exercise.name,
        "score": score,
        "coverage": {"hit": len(covered), "total": len(must), "pct": round(coverage, 3)},
        "accuracy": {"matching": len(matches), "wrong": len(wrongs), "pct": round(accuracy, 3),
                     "wrong_details": [f"{c} {m}: report={v} vs corpus={t}" for c, m, v, t in wrongs]},
        "fabrication": {"count": len(fabricated), "items": fabricated[:20]},
        "agenda_discipline": {"distractors_cited": distractor_hits},
        "tone": {"violations": tone_hits},
        "format": {"chapters_present": len(chapters_present), "chapters_required": len(req_chapters),
                   "tables": n_tables},
        "root_cause": root_cause,
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
    (run_dir / "det_grade.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    r = result
    print(f"\n=== {r['exercise']}  |  SCORE {r['score']}/100 ===")
    print(f"coverage : {r['coverage']['hit']}/{r['coverage']['total']} headline facts ({r['coverage']['pct']:.0%})")
    print(f"accuracy : {r['accuracy']['matching']} ok / {r['accuracy']['wrong']} WRONG")
    for w in r["accuracy"]["wrong_details"]:
        print(f"           ✗ {w}")
    print(f"fabrication (ZERO TOL): {r['fabrication']['count']}")
    for it in r["fabrication"]["items"]:
        print(f"           ⚠ {it['value']}{it['unit']}  «…{it['context']}…»")
    print(f"distractors cited: {r['agenda_discipline']['distractors_cited'] or 'none'}")
    print(f"tone violations  : {r['tone']['violations'] or 'none'}")
    print(f"format : {r['format']['chapters_present']}/{r['format']['chapters_required']} chapters, {r['format']['tables']} tables")
    print(f"ROOT CAUSE: {r['root_cause']['verdict']}")


if __name__ == "__main__":
    main()
