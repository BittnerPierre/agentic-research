#!/usr/bin/env python3
# ruff: noqa: RUF001  (multiplication sign and en dash are deliberate in the UI text and unit regex)
"""Draft: render a finance report.md to HTML with an error/structure overlay.

No LLM. Reuses deterministic_grade.py as a library (numbers, tables, corpus whitelist) and
overlays the verdicts stored in det_grade.json. Usage:
  report_viewer.py <run_dir> <exercise_dir> <out.html>
"""

import html
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]  # tools -> report_viewer -> spike -> spikes -> repo
sys.path.insert(0, str(REPO / "evaluations"))
import deterministic_grade as dg  # noqa: E402

COMPANIES = ["Amazon", "Alphabet", "Meta", "Microsoft", "NVIDIA", "Apple"]
METRICS = [
    "Revenue",
    "Operating income",
    "Operating margin",
    "Operating cash flow",
    "Capex",
    "FCF",
    "Capex/OCF",
]
FYE = {
    "Amazon": "Dec 2025",
    "Alphabet": "Dec 2025",
    "Meta": "Dec 2025",
    "Microsoft": "Jun 2025",
    "NVIDIA": "Jan 2025",
    "Apple": "Sep 2025",
}
YEAR_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


# ---------------------------------------------------------------- inline rendering
def inline_md(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(S\d+(?::\d+)?)\]", r'<span class="cite">[\1]</span>', text)
    return text


class Overlay:
    def __init__(self, corpus: dict, grade: dict, spec: dict):
        self.wl = corpus["whitelist"]
        self.facts = corpus["facts"]
        self.expected_vals = {v for (c, m, fy), v in self.facts.items() if fy == "fy2025"}
        self.fab = grade["fabrication"]["items"]
        self.unv = grade["unverifiable"]["items"]
        self.forbidden = [w.lower() for w in (spec.get("tone", {}).get("forbidden_language") or [])]
        self.counts = {"ok": 0, "grounded": 0, "fab": 0, "unv": 0, "out": 0, "forbidden": 0}

    def _flag(self, items, val, ctx):
        for it in items:
            if dg.close(val, float(it["value"]), tol_abs=0.001, tol_rel=0.0005):
                snippet = it.get("context", "")
                if not snippet or snippet[10:40] in ctx or ctx[:30] in snippet:
                    return it
        return None

    def number_status(self, val, unit, text, pos):
        if unit == "" and YEAR_RE.fullmatch(str(int(val))) and float(val).is_integer():
            return None, None
        ctx = text[max(0, pos - 60) : pos + 60]
        it = self._flag(self.fab, val, ctx)
        if it:
            return "fab", f"Absent du corpus. Grader : {it.get('reason')}"
        it = self._flag(self.unv, val, ctx)
        if it:
            return "unv", f"Invérifiable. Grader : {it.get('reason')}"
        if any(dg.close(val, e, tol_abs=0.001, tol_rel=0.0005) for e in self.expected_vals):
            return "ok", "Fait FY2025 attendu, présent dans le corpus"
        if dg.in_whitelist(val, self.wl):
            return "grounded", "Dans le corpus (non requis)"
        return "out", "Hors liste blanche du corpus, non sanctionné par le grader"

    def mark_numbers(self, raw: str) -> str:
        """Return raw text with <mark> around numbers (before HTML escaping of the rest)."""
        nums = dg.extract_numbers(raw)
        out, last = [], 0
        for val, unit, pos in sorted(nums, key=lambda t: t[2]):
            st, why = self.number_status(val, unit, raw, pos)
            if st is None:
                continue
            m = dg._NUM.match(raw, pos) if hasattr(dg, "_NUM") else None
            end = m.end() if m else pos + len(str(val))
            # extend to swallow a trailing unit glued to the number ($131.8B, 94.4%)
            m2 = re.match(r"[\d.,]+\s?(?:bn|B|M|%|x|×)?", raw[pos:])
            if m2:
                end = pos + m2.end()
            if pos < last:
                continue
            self.counts[st] += 1
            out.append(inline_md(raw[last:pos]))
            out.append(f'<mark class="n {st}" title="{esc(why)}">{inline_md(raw[pos:end])}</mark>')
            last = end
        out.append(inline_md(raw[last:]))
        return "".join(out)

    def mark_forbidden(self, rendered: str) -> str:
        for w in self.forbidden:
            pat = re.compile(re.escape(w), re.I)
            if pat.search(rendered):
                self.counts["forbidden"] += len(pat.findall(rendered))
                rendered = pat.sub(
                    lambda m: (
                        f'<span class="forb" title="Langage interdit par le contrat">{m.group(0)}</span>'
                    ),
                    rendered,
                )
        return rendered

    def inline(self, raw: str) -> str:
        return self.mark_forbidden(self.mark_numbers(raw))


# ---------------------------------------------------------------- tables
def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def company_of(cell: str):
    for c in COMPANIES:
        if c.lower() in cell.lower():
            return c
    return None


def period_check(period: str, company: str):
    years = {m.group(0) for m in YEAR_RE.finditer(period)}
    if not period.strip():
        return "bad", "Période absente"
    if "2025" not in period:
        return "bad", "FY2025 attendu, période non explicite"
    wrong = years - {"2025"}
    if wrong:
        return (
            "bad",
            f"Année {', '.join(sorted(wrong))} incompatible avec FY2025 (clôture {FYE[company]})",
        )
    return "ok", f"FY2025, clôture {FYE[company]}"


def render_table(rows, ov: Overlay, matrix: dict, tcounts: dict):
    header = rows[0]
    hn = [norm(h) for h in header]
    contract = all(k in hn for k in ("company", "metric", "period", "value"))
    cls = "t-contract" if contract else "t-free"
    tcounts["contract" if contract else "free"] += 1
    out = [
        f'<div class="tbl {cls}"><div class="tlabel">{"Tableau au contrat : Company · Metric · Period · Value" if contract else "Tableau libre (hors contrat, non lu pour les faits)"}</div><table>'
    ]
    out.append("<tr>" + "".join(f"<th>{inline_md(h)}</th>" for h in header) + "</tr>")
    idx = {k: hn.index(k) for k in ("company", "metric", "period", "value")} if contract else {}
    for r in rows[1:]:
        if contract and len(r) >= 4:
            co = company_of(r[idx["company"]])
            met = dg._canonical_metric(r[idx["metric"]])
            vals = dg.extract_numbers(r[idx["value"]])
            val = vals[0][0] if vals else None
            exp = ov.facts.get((co.lower(), met.lower(), "fy2025")) if co and met else None
            pst, pwhy = (
                period_check(r[idx["period"]], co) if co else ("bad", "Société non reconnue")
            )
            if (
                exp is not None
                and val is not None
                and dg.close(val, exp, tol_abs=0.051, tol_rel=0.0)
            ):
                vst, vwhy = "ok", f"= attendu {exp}"
            elif exp is not None and val is not None:
                vst, vwhy = "bad", f"attendu {exp}, lu {val}"
            elif exp is None:
                vst, vwhy = (
                    "na",
                    f"métrique non reconnue ({r[idx['metric']].strip()[:30]})"
                    if co
                    else "société non reconnue",
                )
            else:
                vst, vwhy = "bad", "valeur illisible"
            tcounts["rows"] += 1
            tcounts["bad_value" if vst == "bad" else "ok_value" if vst == "ok" else "na"] += 1
            if pst == "bad":
                tcounts["bad_period"] += 1
            if co and met and (co, met) in matrix:
                m = matrix[(co, met)]
                m["seen"] = True
                m["value"] = vst
                m["period"] = pst
                m["why"] = f"{vwhy} ; période : {pwhy}"
            cells = []
            for j, c in enumerate(r):
                if j == idx["period"]:
                    cells.append(f'<td class="p-{pst}" title="{esc(pwhy)}">{inline_md(c)}</td>')
                elif j == idx["value"]:
                    cells.append(f'<td class="v-{vst}" title="{esc(vwhy)}">{inline_md(c)}</td>')
                elif j == idx["metric"]:
                    cells.append(f'<td title="canonique : {esc(met or "?")}">{inline_md(c)}</td>')
                else:
                    cells.append(f"<td>{inline_md(c)}</td>")
            out.append("<tr>" + "".join(cells) + "</tr>")
        else:
            out.append("<tr>" + "".join(f"<td>{ov.inline(c)}</td>" for c in r) + "</tr>")
    out.append("</table></div>")
    return "".join(out)


# ---------------------------------------------------------------- document
def exec_block(stats: dict) -> str:
    if not stats:
        return "<h4>Exécution</h4><ul><li class='muted'>stats.json absent</li></ul>"
    tim = stats.get("timings") or {}
    use = stats.get("usage_by_phase") or {}
    calls = stats.get("agent_calls") or {}
    models = stats.get("models") or {}
    wm = stats.get("writer_metrics") or {}
    gr = wm.get("grounding") or {}
    total_t = tim.get("total") or sum(v for k, v in tim.items() if k != "total") or 1
    phases = [
        ("knowledge_preparation", "préparation"),
        ("planning", "plan"),
        ("search", "recherche"),
        ("writing", "écriture"),
    ]
    tot_tok = (use.get("total") or {}).get("total_tokens") or 1
    rows = []
    for k, lab in phases:
        sec = tim.get(k) or 0
        u = use.get(k) or {}
        rows.append(
            f"<div class='ph'><div class='phl'>{lab}</div>"
            f"<div class='phb'><i style='width:{sec / total_t * 100:.1f}%'></i></div><div class='phv'>{sec:.0f} s</div>"
            f"<div class='phb tok'><i style='width:{(u.get('total_tokens') or 0) / tot_tok * 100:.1f}%'></i></div>"
            f"<div class='phv' title='{u.get('input_tokens', 0):,} entrée · {u.get('output_tokens', 0):,} sortie'>{(u.get('total_tokens') or 0) / 1000:.0f} k · {u.get('requests', 0)} req</div></div>"
        )
    models = {r: m for r, m in models.items() if m}
    uniq = sorted(set(models.values()))
    model_txt = (
        esc(uniq[0])
        if len(uniq) == 1
        else "<br>".join(f"{esc(r)} : {esc(m)}" for r, m in models.items())
    )
    tt = use.get("total") or {}
    items = [
        f"<b>{total_t:.0f} s</b> au total · {tt.get('requests', 0)} requêtes LLM · {tt.get('total_tokens', 0):,} tokens ({tt.get('input_tokens', 0):,} entrée / {tt.get('output_tokens', 0):,} sortie{', ' + str(tt.get('reasoning_tokens')) + ' raisonnement' if tt.get('reasoning_tokens') else ''})",
        f"agents : recherche ×{calls.get('file_search_agent', 0)}, écriture ×{calls.get('writer_agent', 0)}, préparation ×{calls.get('knowledge_preparation_agent', 0)}, plan ×{calls.get('file_planner_agent', 0)}, échecs {calls.get('failures', 0)}",
        f"sources {stats.get('n_sources', '?')} · chunks {stats.get('n_chunks', '?')} · citées {gr.get('n_cited_sources', '?')}/{gr.get('n_sources', '?')} · citations invalides {gr.get('n_invalid_citations', '?')}",
        f"écriture : {wm.get('n_chapters', '?')} chapitres, plan {wm.get('outline_seconds', 0):.0f} s, chapitres {wm.get('chapters_wall_seconds', 0):.0f} s en parallèle ×{wm.get('concurrency_ratio', 0):.1f}, {(stats.get('derived') or {}).get('writing_throughput_tok_s', 0):.0f} tok/s",
        f"stratégie {esc(str(stats.get('writer_strategy', '?')))} · manager {esc(str(stats.get('manager', '?')))} · modèle {model_txt}",
    ]
    legend = "<div class='mnote'>barre grise : temps · barre bleue : tokens</div>"
    return (
        "<h4>Exécution</h4>"
        + "".join(rows)
        + legend
        + "<ul>"
        + "".join(f"<li>{x}</li>" for x in items)
        + "</ul>"
    )


def render(
    report: str, grade: dict, spec: dict, corpus: dict, title: str, stats: dict | None = None
) -> str:
    ov = Overlay(corpus, grade, spec)
    chapters = spec.get("required_chapters", [])
    found_ch = {c: False for c in chapters}
    matrix = {
        (c, m): {
            "seen": False,
            "value": "na",
            "period": "na",
            "why": "absent des tableaux au contrat",
        }
        for c in COMPANIES
        for m in METRICS
    }
    tcounts = {
        "contract": 0,
        "free": 0,
        "rows": 0,
        "ok_value": 0,
        "bad_value": 0,
        "bad_period": 0,
        "na": 0,
    }
    lines = report.splitlines()
    body, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.startswith("#"):
            level = len(ln) - len(ln.lstrip("#"))
            text = ln.lstrip("#").strip()
            hit = (
                None
                if level == 1
                else next(
                    (
                        c
                        for c in sorted(chapters, key=len, reverse=True)
                        if c.lower() in text.lower() and not found_ch[c]
                    ),
                    None,
                )
            )
            if hit:
                found_ch[hit] = True
                body.append(
                    f'<h{level} class="ch ok" title="Chapitre du contrat : {esc(hit)}">{inline_md(text)}<span class="tag">contrat · {esc(hit)}</span></h{level}>'
                )
            elif level == 1 or text.lower().startswith("sources"):
                body.append(f"<h{level}>{inline_md(text)}</h{level}>")
            else:
                body.append(
                    f'<h{level} class="ch extra" title="Section hors contrat">{inline_md(text)}<span class="tag">hors contrat</span></h{level}>'
                )
            i += 1
        elif ln.strip().startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            rows = [
                [c.strip() for c in r.strip().strip("|").split("|")]
                for r in block
                if not re.match(r"^\s*\|?\s*:?-{2,}", r)
            ]
            if rows:
                body.append(render_table(rows, ov, matrix, tcounts))
        elif re.match(r"^\s*[-*•]\s+", ln):
            items = []
            while i < n and re.match(r"^\s*[-*•]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*•]\s+", "", lines[i]))
                i += 1
            body.append("<ul>" + "".join(f"<li>{ov.inline(x)}</li>" for x in items) + "</ul>")
        elif ln.strip() == "":
            i += 1
        else:
            para = []
            while (
                i < n
                and lines[i].strip()
                and not lines[i].startswith("#")
                and not lines[i].strip().startswith("|")
                and not re.match(r"^\s*[-*•]\s+", lines[i])
            ):
                para.append(lines[i])
                i += 1
            body.append(f"<p>{ov.inline(' '.join(para))}</p>")
    missing_ch = [c for c, ok in found_ch.items() if not ok]
    if missing_ch:
        body.append(
            '<div class="ghost"><b>Chapitres du contrat absents :</b> '
            + ", ".join(esc(c) for c in missing_ch)
            + "</div>"
        )

    # ---- margin data
    q = grade["qualification"]
    fmt = grade["format"]
    reqs = grade["requirements"]
    missing = [r["label"] for r in reqs if r.get("status") != "pass"]
    wc, mn, mx = fmt["word_count"], fmt["min_words"], fmt["effective_max_words"]
    gauge_pct = min(100, wc / (mx * 1.2) * 100)
    wc_cls = "ok" if mn <= wc <= mx else "bad"

    # ---- matrix
    mrows = []
    for c in COMPANIES:
        cells = []
        for m in METRICS:
            st = matrix[(c, m)]
            req = next(
                (r for r in reqs if r["label"].lower().startswith(f"{c.lower()} {m.lower()}")), None
            )
            gr = (req or {}).get("status", "?")
            if gr == "pass" and st["period"] != "bad":
                k, lab = "ok", "✓"
            elif gr == "pass" and st["period"] == "bad":
                k, lab = "period", "FY?"
            elif st["seen"] and st["value"] == "ok" and st["period"] == "bad":
                k, lab = "period", "FY?"
            elif st["seen"] and st["value"] == "bad":
                k, lab = "bad", "≠"
            elif st["seen"] and st["value"] == "ok":
                k, lab = "gok", "✓*"
            else:
                k, lab = "miss", "—"
            cells.append(
                f'<td class="m {k}" title="{esc(c)} · {esc(m)} · grader : {esc(gr)} · {esc(st["why"])}">{lab}</td>'
            )
        mrows.append(f"<tr><th>{c}</th>{''.join(cells)}</tr>")
    matrix_html = (
        "<table class='matrix'><tr><th></th>"
        + "".join(f"<th>{esc(m)}</th>" for m in METRICS)
        + "</tr>"
        + "".join(mrows)
        + "</table>"
    )

    def li(items):
        return "".join(f"<li>{esc(str(x))}</li>" for x in items) or "<li class='muted'>aucun</li>"

    margin = f"""
<div class="score {"qual" if grade["qualified"] else "nq"}"><div class="big">{grade["score"]}</div><div>{"qualifié" if grade["qualified"] else "non qualifié"}</div></div>
{exec_block(stats or {})}
<h4>Blocages</h4><ul>{li(q["blockers"] + q["format_blockers"])}</ul>
<h4>Couverture {grade["coverage"]["hit"]}/{grade["coverage"]["total"]}</h4><ul>{li(missing[:12])}{"<li class=muted>…</li>" if len(missing) > 12 else ""}</ul>
<h4>Valeurs fausses ({grade["accuracy"]["wrong"]})</h4><ul>{li(grade["accuracy"]["wrong_details"][:10])}</ul>
<h4>Fabrications ({grade["fabrication"]["count"]})</h4><ul>{li([f"{x['value']}{x['unit']} · {x['reason']}" for x in ov.fab])}</ul>
<h4>Invérifiables ({grade["unverifiable"]["count"]})</h4><ul>{li([f"{x['value']}{x['unit']} · {x['reason']}" for x in ov.unv])}</ul>
<h4>Ton</h4><ul>{li(grade["tone"]["violations"])}</ul>
<h4>Format</h4><ul><li>chapitres {fmt["chapters_present"]}/{fmt["chapters_required"]}</li><li>tableaux {fmt["parseable_tables"]} lisibles / {fmt["tables"]}</li><li>{wc} mots (contrat {mn}–{fmt["max_words"]}, toléré {mx})</li></ul>
"""
    legend = """
<span><i class="sw ok"></i>fait attendu</span><span><i class="sw grounded"></i>dans le corpus</span><span><i class="sw out"></i>hors corpus, toléré</span><span><i class="sw unv"></i>invérifiable</span><span><i class="sw fab"></i>fabrication</span><span><i class="sw forbx"></i>langage interdit</span><span><i class="sw pbad"></i>période fausse</span><span><i class="sw vbad"></i>valeur fausse</span>
"""
    toggles = """
<label><input type="checkbox" checked data-layer="numbers"> nombres</label>
<label><input type="checkbox" checked data-layer="tables"> tableaux</label>
<label><input type="checkbox" checked data-layer="structure"> structure</label>
<label><input type="checkbox" checked data-layer="margin"> marge</label>
<label><input type="checkbox" checked data-layer="matrix"> matrice</label>
"""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>
:root{{--ink:#1b2430;--muted:#66717f;--line:#e2e6ec;--bg:#f7f8fa;--panel:#fff;--ok:#1f8f4e;--okbg:#e3f5ea;--gr:#2f6fe4;--grbg:#e6eefc;--out:#b7791f;--outbg:#fbf1dc;--unv:#7c4dcc;--unvbg:#efe7fb;--fab:#c62828;--fabbg:#fde3e3;--per:#d9730d;--perbg:#fdebd8}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}}
.top{{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line);padding:10px 18px;display:flex;gap:18px;flex-wrap:wrap;align-items:center}}
.top b{{font-size:15px}}.legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted)}}.legend .sw{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-1px}}
.sw.ok{{background:var(--okbg);border:1px solid var(--ok)}}.sw.grounded{{background:var(--grbg);border:1px solid var(--gr)}}.sw.out{{background:var(--outbg);border:1px solid var(--out)}}.sw.unv{{background:var(--unvbg);border:1px solid var(--unv)}}.sw.fab{{background:var(--fabbg);border:1px solid var(--fab)}}.sw.forbx{{border-bottom:2px solid var(--fab)}}.sw.pbad{{background:var(--perbg);border:1px solid var(--per)}}.sw.vbad{{background:var(--fabbg);border:1px solid var(--fab)}}
.toggles{{display:flex;gap:10px;font-size:12px;margin-left:auto}}
.wrap{{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;max-width:1380px;margin:0 auto;padding:18px}}
.doc{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:26px 34px}}
.gauge{{height:8px;background:var(--line);border-radius:4px;position:relative;margin:4px 0 18px}}.gauge i{{position:absolute;left:0;top:0;bottom:0;border-radius:4px}}.gauge .lim{{position:absolute;top:-4px;width:2px;height:16px;background:var(--muted)}}
.gauge.ok i{{background:var(--ok)}}.gauge.bad i{{background:var(--fab)}}
h1{{font-size:24px;margin:0 0 6px}}h2{{font-size:19px;margin:28px 0 8px;padding-top:8px;border-top:1px solid var(--line)}}h3{{font-size:16px;margin:18px 0 6px}}
.tag{{font-size:11px;font-weight:600;margin-left:10px;padding:2px 8px;border-radius:999px;vertical-align:middle}}
h2.ch.ok .tag,h3.ch.ok .tag{{background:var(--okbg);color:var(--ok)}}h2.ch.extra .tag,h3.ch.extra .tag{{background:var(--outbg);color:var(--out)}}
body.no-structure .tag{{display:none}}
mark.n{{background:transparent;border-radius:3px;padding:0 2px;border-bottom:2px solid transparent}}
body:not(.no-numbers) mark.n.ok{{background:var(--okbg);border-color:var(--ok)}}body:not(.no-numbers) mark.n.grounded{{background:var(--grbg);border-color:var(--gr)}}body:not(.no-numbers) mark.n.out{{background:var(--outbg);border-color:var(--out)}}body:not(.no-numbers) mark.n.unv{{background:var(--unvbg);border-color:var(--unv)}}body:not(.no-numbers) mark.n.fab{{background:var(--fabbg);border-color:var(--fab);font-weight:700}}
body:not(.no-numbers) .forb{{border-bottom:2px solid var(--fab);background:var(--fabbg)}}
.cite{{color:var(--muted);font-size:12px}}
.tbl{{margin:12px 0 16px;border:2px solid var(--line);border-radius:8px;overflow:auto}}body:not(.no-tables) .tbl.t-contract{{border-color:var(--ok)}}body:not(.no-tables) .tbl.t-free{{border-color:var(--muted);border-style:dashed}}
.tlabel{{font-size:11px;color:var(--muted);padding:4px 10px;background:var(--bg)}}body.no-tables .tlabel{{display:none}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}td,th{{padding:5px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:var(--muted);font-weight:600}}
body:not(.no-tables) td.p-bad{{background:var(--perbg);color:#8a4a0a;font-weight:600}}body:not(.no-tables) td.v-ok{{background:var(--okbg)}}body:not(.no-tables) td.v-bad{{background:var(--fabbg);color:var(--fab);font-weight:700}}body:not(.no-tables) td.v-na{{background:var(--bg);color:var(--muted)}}
.ghost{{margin:16px 0;padding:10px 14px;border:2px dashed var(--fab);border-radius:8px;color:var(--fab);background:var(--fabbg)}}body.no-structure .ghost{{display:none}}
.margin{{position:sticky;top:64px;align-self:start;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;font-size:13px;max-height:calc(100vh - 80px);overflow:auto}}body.no-margin .margin{{display:none}}body.no-margin .wrap{{grid-template-columns:1fr}}
.margin h4{{margin:12px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}.margin ul{{margin:0;padding-left:16px}}.margin li{{margin:2px 0}}.muted{{color:var(--muted)}}
.ph{{display:grid;grid-template-columns:70px 1fr 42px 1fr 86px;gap:6px;align-items:center;font-size:11px;margin:3px 0}}.phl{{color:var(--muted)}}.phb{{height:7px;background:var(--line);border-radius:4px;overflow:hidden}}.phb i{{display:block;height:100%;background:var(--muted)}}.phb.tok i{{background:var(--gr)}}.phv{{text-align:right;white-space:nowrap}}
.score{{text-align:center;border-radius:8px;padding:8px}}.score .big{{font-size:30px;font-weight:800}}.score.qual{{background:var(--okbg);color:var(--ok)}}.score.nq{{background:var(--fabbg);color:var(--fab)}}
.matrix{{font-size:12px;margin:0 0 6px}}.matrix th{{font-size:11px;padding:3px 4px;text-align:center}}.matrix td.m{{text-align:center;font-weight:700;padding:3px 4px;border:1px solid #fff}}
.matrix td.ok{{background:var(--okbg);color:var(--ok)}}.matrix td.gok{{background:var(--grbg);color:var(--gr)}}.matrix td.period{{background:var(--perbg);color:#8a4a0a}}.matrix td.bad{{background:var(--fabbg);color:var(--fab)}}.matrix td.miss{{background:var(--bg);color:var(--muted)}}
.mbox{{margin:0 0 14px}}body.no-matrix .mbox{{display:none}}.mnote{{font-size:11px;color:var(--muted)}}
@media(max-width:900px){{.wrap{{grid-template-columns:1fr}}.margin{{position:static;max-height:none}}}}
</style></head><body>
<div class="top"><b>{esc(title)}</b><div class="legend">{legend}</div><div class="toggles">{toggles}</div></div>
<div class="wrap"><div class="doc">
<div class="mbox">{matrix_html}<div class="mnote">42 faits FY2025 lus dans les tableaux au contrat : ✓ exact · ✓* exact dans le tableau mais non crédité par le grader · FY? valeur exacte, période fausse · ≠ valeur fausse · — absent. Survoler une case pour le détail.</div></div>
<div class="mnote">Longueur : {wc} mots (contrat {mn} à {fmt["max_words"]}, toléré jusqu'à {mx})</div>
<div class="gauge {wc_cls}"><i style="width:{gauge_pct:.1f}%"></i><span class="lim" style="left:{mn / (mx * 1.2) * 100:.1f}%" title="min {mn}"></span><span class="lim" style="left:{mx / (mx * 1.2) * 100:.1f}%" title="max toléré {mx}"></span></div>
{"".join(body)}
</div><aside class="margin">{margin}</aside></div>
<script>
document.querySelectorAll('.toggles input').forEach(cb=>cb.addEventListener('change',()=>{{document.body.classList.toggle('no-'+cb.dataset.layer,!cb.checked)}}));
</script></body></html>"""


def main():
    run, exercise, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    report = (run / "report.md").read_text(encoding="utf-8")
    grade = json.loads((run / "det_grade.json").read_text(encoding="utf-8"))
    spec = yaml.safe_load((exercise / "spec.yaml").read_text(encoding="utf-8"))
    corpus = dg.load_corpus(exercise)
    stats = (
        json.loads((run / "stats.json").read_text(encoding="utf-8"))
        if (run / "stats.json").is_file()
        else {}
    )
    model = (stats.get("models") or {}).get("writer") or stats.get("config_name") or run.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render(report, grade, spec, corpus, f"{model} · {run.name[:15]}", stats), encoding="utf-8"
    )
    print("written", out, len(out.read_text()), "chars")


if __name__ == "__main__":
    main()
