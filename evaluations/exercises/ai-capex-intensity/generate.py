"""Generate the AI-capex-intensity exercise corpus + answer key from EDGAR XBRL.

Corpus and answer key come from the SAME extraction, so they are consistent by
construction (no transcription drift). Emits multi-format corpus files + the
numeric tiers of answer_key.yaml. Framing: junior-analyst factual data prep.
"""
import json
from datetime import date
from pathlib import Path

CF = Path("/Users/pierrebittner/Documents/GitHub/DeepResearch/claude/financial analysis/companyfacts")
OUT = Path("/Users/pierrebittner/Documents/GitHub/DeepResearch/claude/agentic-research/evaluations/exercises/ai-capex-intensity")

COMPANIES = [
    # (name, cik file, fye_label, latest_fy)
    ("Amazon",    "CIK0001018724.json", "Dec",  2024),
    ("Alphabet",  "CIK0001652044.json", "Dec",  2024),
    ("Meta",      "CIK0001326801.json", "Dec",  2024),
    ("Microsoft", "CIK0000789019.json", "Jun",  2024),
    ("NVIDIA",    "CIK0001045810.json", "Jan",  2025),
    ("Apple",     "CIK0000320193.json", "Sep",  2025),
]

CONCEPTS = {
    "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "OperatingIncome": ["OperatingIncomeLoss"],
    "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities",
                          "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "Capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


def _annual_by_endyear(node):
    best = {}
    for pts in node.get("units", {}).values():
        for p in pts:
            s, e = p.get("start"), p.get("end")
            if not s or not e or not str(p.get("form", "")).startswith("10-K"):
                continue
            days = (date.fromisoformat(e) - date.fromisoformat(s)).days
            if not (350 <= days <= 380):
                continue
            y, filed = date.fromisoformat(e).year, p.get("filed", "")
            if y not in best or filed > best[y][0]:
                best[y] = (filed, p.get("val"))
    return {y: v for y, (_, v) in best.items()}


def annual(gaap, fbs):
    out = {}
    for c in fbs:
        if c in gaap:
            for y, v in _annual_by_endyear(gaap[c]).items():
                out.setdefault(y, v)
    return out


def load(name, fname):
    gaap = json.loads((CF / fname).read_text())["facts"]["us-gaap"]
    return {k: annual(gaap, fb) for k, fb in CONCEPTS.items()}


def b(v):  # to $B, 1 decimal
    return None if v is None else round(v / 1e9, 1)


def rows(series):
    """Per-year derived record."""
    out = {}
    for y in YEARS:
        rev, opi = series["Revenue"].get(y), series["OperatingIncome"].get(y)
        ocf, cpx = series["OperatingCashFlow"].get(y), series["Capex"].get(y)
        if rev is None and cpx is None:
            continue
        out[y] = {
            "rev": b(rev), "opinc": b(opi),
            "opmrg": round(opi / rev * 100, 1) if (opi and rev) else None,
            "ocf": b(ocf), "capex": b(cpx),
            "fcf": b(ocf - cpx) if (ocf is not None and cpx is not None) else None,
            "cpx_ocf": round(cpx / ocf * 100) if (cpx and ocf) else None,
        }
    return out


def main():
    (OUT / "corpus").mkdir(parents=True, exist_ok=True)
    data = {name: (fye, lfy, rows(load(name, f))) for name, f, fye, lfy in COMPANIES}

    # ---- corpus file 1: clean data tables (markdown) ----
    md = ["# Capital-Expenditure Reference Data (from SEC 10-K filings)\n",
          "All figures in US$ billions unless noted. Sourced from each company's annual",
          "report (Form 10-K), consolidated statements. **Fiscal-year-end differs by company**:",
          "Amazon/Alphabet/Meta = December; Microsoft = June; NVIDIA = late January;",
          "Apple = late September. Compare on a fiscal-year basis, not calendar.\n",
          "Metric definitions: Operating margin = Operating income / Revenue. ",
          "Free cash flow (FCF) = Operating cash flow − Capex. ",
          "Capex intensity = Capex / Operating cash flow.\n"]
    for name, (fye, lfy, rr) in data.items():
        md.append(f"\n## {name} (FYE {fye})\n")
        md.append("| Fiscal Year | Revenue | Operating income | Operating margin | Operating cash flow | Capex | FCF | Capex/OCF |")
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for y, r in rr.items():
            md.append(f"| FY{y} | {r['rev']} | {r['opinc']} | "
                      f"{'' if r['opmrg'] is None else str(r['opmrg'])+'%'} | "
                      f"{r['ocf']} | {r['capex']} | {r['fcf']} | "
                      f"{'' if r['cpx_ocf'] is None else str(r['cpx_ocf'])+'%'} |")
    (OUT / "corpus" / "capex_reference_data.md").write_text("\n".join(md) + "\n")

    # ---- corpus file 2: compact structured extract (CSV) ----
    csv = ["Company,FYE_basis,Metric,FiscalYear,Value,Unit"]
    for name, (fye, lfy, rr) in data.items():
        for y, r in rr.items():
            for metric, key, unit in [("Revenue", "rev", "USD_billions"),
                                       ("Operating income", "opinc", "USD_billions"),
                                       ("Operating margin", "opmrg", "percent"),
                                       ("Operating cash flow", "ocf", "USD_billions"),
                                       ("Capex", "capex", "USD_billions"),
                                       ("FCF", "fcf", "USD_billions"),
                                       ("Capex/OCF", "cpx_ocf", "percent")]:
                if r[key] is not None:
                    csv.append(f"{name},{fye},{metric},FY{y},{r[key]},{unit}")
    (OUT / "corpus" / "key_metrics.csv").write_text("\n".join(csv) + "\n")

    # ---- corpus file 3: analyst prep notes (prose, factual) ----
    notes = ["# Analyst Prep Notes — Capex & Cash Generation\n",
             "*Neutral, factual notes compiled from 10-K figures. No positioning.*\n"]
    for name, (fye, lfy, rr) in data.items():
        r = rr[lfy]
        first_y = min(rr)
        c0, c1 = rr[first_y]["capex"], r["capex"]
        notes.append(f"\n## {name}")
        notes.append(
            f"For its most recent fiscal year (FY{lfy}, FYE {fye}), {name} reported "
            f"revenue of ${r['rev']}B, an operating margin of {r['opmrg']}%, operating "
            f"cash flow of ${r['ocf']}B, and capital expenditures of ${r['capex']}B. "
            f"Free cash flow was ${r['fcf']}B and capex represented {r['cpx_ocf']}% of "
            f"operating cash flow. Over FY{first_y}–FY{lfy}, reported capex moved from "
            f"${c0}B to ${c1}B.")
    (OUT / "corpus" / "analyst_prep_notes.md").write_text("\n".join(notes) + "\n")

    # ---- answer key numeric tiers (printed; folded into answer_key.yaml) ----
    print("### must_cover (latest FY headline figures per company) ###")
    for name, (fye, lfy, rr) in data.items():
        r = rr[lfy]
        print(f"{name} FY{lfy}: rev={r['rev']} opmrg={r['opmrg']} capex={r['capex']} cpx/ocf={r['cpx_ocf']}")
    print("\n### files written ###")
    for p in sorted((OUT / "corpus").glob("*")):
        print(" ", p.relative_to(OUT), p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
