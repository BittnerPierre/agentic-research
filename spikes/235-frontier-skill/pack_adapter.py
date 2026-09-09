#!/usr/bin/env python3
"""Adaptateur banc : dossier de travail du skill → pack notable (spike #235).

Le skill produit son livrable naturel (rapport citant des extraits [E<n>],
extraits verbatim avec provenance). Le banc note un PACK : report.md ([S<n>]),
sources.json, chunks.json (extraits bruts vérifiables), stats.json,
raw_sources/. Cet adaptateur fait la traduction, sans rien ajouter au contenu :

- [E<n>] → [S<k>] dans l'ordre de première citation ; une source par extrait cité ;
- bras A : chaque extrait devient un chunk `<fichier>:<i>` dont le texte est
  vérifié verbatim contre le fichier du fonds (repli : relocalisation à
  espaces normalisés, sinon extrait non résolu — signalé, jamais corrigé) ;
- bras B : chunks.json = registre exact des extraits renvoyés par vector_search
  (comme le workflow) ; les extraits pointent sur leur chunk_id ;
- stats.json : provenance, requête encadrée, durée, tokens, coût (prix liste)
  et statistiques de sous-agents issues du résultat `claude -p`.

Usage :
  uv run python spikes/235-frontier-skill/pack_adapter.py --workdir output/spike235/<run> \
      --request evaluations/exercises/<ex>/syllabus.md --arm A [--out benchmarks/runs/<dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluations.chunk_snapshot import ChunkSnapshot  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usage_from_events import aggregate as aggregate_events  # noqa: E402

from src.dataprep.vector_backends import clean_for_rag  # noqa: E402

CITE_RE = re.compile(r"\[(E\d+(?:\s*[,;]\s*E?\d+)*)\]")
SOURCES_RE = re.compile(r"(?im)^##\s+Sources\s*$")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_extracts(workdir: Path) -> dict[str, dict]:
    """Extraits = parts/*.jsonl (texte qui fait foi) + extraits.jsonl (index ; texte si absent des parts)."""
    root = workdir / "03-extraits"
    files = sorted((root / "parts").glob("*.jsonl")) + (
        [root / "extraits.jsonl"] if (root / "extraits.jsonl").is_file() else []
    )
    out: dict[str, dict] = {}
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not (isinstance(rec, dict) and rec.get("id")):
                continue
            eid = str(rec["id"]).upper()
            prev = out.get(eid)
            if prev is None:
                out[eid] = rec
            else:
                # l'index (extraits.jsonl) peut porter `retenu` ; les parts portent le texte complet
                merged = dict(prev)
                for key, value in rec.items():
                    if key == "texte" and len(str(value or "")) < len(str(prev.get("texte") or "")):
                        continue
                    merged[key] = value
                out[eid] = merged
    return out


def find_report(workdir: Path) -> tuple[Path | None, str]:
    candidates = [
        (workdir / "08-livraison" / "rapport.md", "livraison"),
        *sorted(
            ((p, "revision") for p in (workdir / "07-revision").glob("revision-*.md")), reverse=True
        ),
        (workdir / "06-redaction" / "manuscrit.md", "manuscrit"),
    ]
    for path, stage in candidates:
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return path, stage
    return None, "aucun"


def split_body(report: str) -> str:
    matches = list(SOURCES_RE.finditer(report))
    return report[: matches[-1].start()].rstrip() if matches else report.rstrip()


def relocate(text: str, raw: str) -> str | None:
    """Retrouve un passage à espaces normalisés et renvoie le span brut exact."""
    norm_chars: list[str] = []
    index_map: list[int] = []
    prev_space = False
    for i, ch in enumerate(raw):
        if ch.isspace():
            if prev_space:
                continue
            norm_chars.append(" ")
            prev_space = True
        else:
            norm_chars.append(ch)
            prev_space = False
        index_map.append(i)
    norm_raw = "".join(norm_chars)
    norm_text = re.sub(r"\s+", " ", text).strip()
    if not norm_text:
        return None
    pos = norm_raw.find(norm_text)
    if pos < 0:
        return None
    start = index_map[pos]
    end = index_map[pos + len(norm_text) - 1] + 1
    return raw[start:end]


def build_arm_a(
    extracts: dict[str, dict], workdir: Path, log: list[str]
) -> tuple[dict, dict[str, str]]:
    fonds = workdir / "fonds"
    raw_cache: dict[str, tuple[str, str]] = {}
    chunks: list[dict] = []
    e_to_chunk: dict[str, str] = {}
    counters: dict[str, int] = {}
    for eid, rec in extracts.items():
        if rec.get("retenu") is False:
            continue
        filename = Path(str(rec.get("fichier") or "")).name
        text = str(rec.get("texte") or "")
        source_path = fonds / filename
        if not filename or not source_path.is_file() or not text.strip():
            log.append(f"{eid}: fichier introuvable ou texte vide ({filename!r}) → non résolu")
            chunks.append(
                {
                    "chunk_id": None,
                    "document_id": None,
                    "chunk_index": None,
                    "filename": filename or None,
                    "source": None,
                    "text": text,
                    "sha256": sha256_text(text),
                    "resolved": False,
                }
            )
            continue
        if filename not in raw_cache:
            raw = source_path.read_text(encoding="utf-8", errors="ignore")
            raw_cache[filename] = (raw, clean_for_rag(raw))
        raw, cleaned = raw_cache[filename]
        final_text = text
        if text not in raw and text not in cleaned:
            span = relocate(text, raw) or relocate(text, cleaned)
            if span is None:
                log.append(f"{eid}: extrait non verbatim dans {filename} → non résolu")
                chunks.append(
                    {
                        "chunk_id": None,
                        "document_id": None,
                        "chunk_index": None,
                        "filename": filename,
                        "source": None,
                        "text": text,
                        "sha256": sha256_text(text),
                        "resolved": False,
                    }
                )
                continue
            log.append(f"{eid}: relocalisé (espaces) dans {filename}")
            final_text = span
        counters[filename] = counters.get(filename, 0) + 1
        chunk_id = f"{filename}:{counters[filename]}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "document_id": filename,
                "chunk_index": counters[filename],
                "filename": filename,
                "source": None,
                "text": final_text,
                "sha256": sha256_text(final_text),
                "resolved": True,
            }
        )
        e_to_chunk[eid] = chunk_id
        rec["_content"] = final_text
    return {"schema_version": 1, "chunks": chunks, "conflicts": []}, e_to_chunk


def build_arm_b(
    extracts: dict[str, dict], workdir: Path, log: list[str]
) -> tuple[dict, dict[str, str]]:
    registry = workdir / "retrieval" / "chunks.jsonl"
    by_id: dict[str, dict] = {}
    conflicts: list[dict] = []
    unresolved: list[dict] = []
    if registry.is_file():
        for line in registry.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            record = {
                k: rec.get(k)
                for k in (
                    "chunk_id",
                    "document_id",
                    "chunk_index",
                    "filename",
                    "source",
                    "text",
                    "sha256",
                    "resolved",
                )
            }
            if not record.get("chunk_id") or not record.get("resolved"):
                record["resolved"] = False
                record["chunk_id"] = None
                unresolved.append(record)
                continue
            prev = by_id.get(record["chunk_id"])
            if prev and prev["sha256"] != record["sha256"]:
                conflicts.append(
                    {
                        "chunk_id": record["chunk_id"],
                        "first_sha256": prev["sha256"],
                        "second_sha256": record["sha256"],
                    }
                )
                continue
            by_id[record["chunk_id"]] = record
    else:
        log.append("registre retrieval/chunks.jsonl absent : aucun chunk")
    e_to_chunk: dict[str, str] = {}
    for eid, rec in extracts.items():
        if rec.get("retenu") is False:
            continue
        text = str(rec.get("texte") or "")
        cid = str(rec.get("chunk_id") or "").strip() or None
        if cid and cid in by_id:
            if text and text not in by_id[cid]["text"]:
                log.append(f"{eid}: texte non contenu dans le chunk {cid} (cité tel quel)")
        else:
            hit = next((k for k, c in by_id.items() if text and text in c["text"]), None)
            if hit:
                log.append(f"{eid}: chunk_id absent/inconnu → retrouvé par le texte ({hit})")
                cid = hit
            else:
                log.append(f"{eid}: aucun chunk du registre ne contient l'extrait → doc_ids vide")
                cid = None
        if cid:
            e_to_chunk[eid] = cid
        rec["_content"] = text
    chunks = [by_id[k] for k in sorted(by_id)] + unresolved
    return {"schema_version": 1, "chunks": chunks, "conflicts": conflicts}, e_to_chunk


def renumber(body: str, extracts: dict[str, dict]) -> tuple[str, list[str]]:
    order: list[str] = []

    def repl(match: re.Match) -> str:
        ids = [f"E{re.sub(r'\D', '', part)}" for part in re.split(r"[,;]", match.group(1))]
        out = []
        for eid in ids:
            if eid not in extracts:
                out.append(f"[{eid}]")  # identifiant inconnu : laissé tel quel (faute du candidat)
                continue
            if eid not in order:
                order.append(eid)
            out.append(f"[S{order.index(eid) + 1}]")
        return "".join(out)

    return CITE_RE.sub(repl, body), order


def claude_usage(meta: dict) -> tuple[dict, dict]:
    result = (meta or {}).get("result") or {}
    usage = result.get("usage") or {}
    inp = int(usage.get("input_tokens") or 0)
    cache_r = int(usage.get("cache_read_input_tokens") or 0)
    cache_c = int(usage.get("cache_creation_input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    think = int(((usage.get("output_tokens_details") or {}).get("thinking_tokens")) or 0)
    total = {
        "requests": int(result.get("num_turns") or 0),
        "input_tokens": inp + cache_r + cache_c,
        "output_tokens": out,
        "total_tokens": inp + cache_r + cache_c + out,
        "cached_tokens": cache_r,
        "reasoning_tokens": think,
        "uncached_input_tokens": inp,
        "cache_creation_input_tokens": cache_c,
    }
    extra = {
        "cost_usd_list_price": result.get("total_cost_usd"),
        "duration_api_ms": result.get("duration_api_ms"),
        "num_turns": result.get("num_turns"),
        "subagent_stats": result.get("subagent_stats"),
        "model_usage": result.get("modelUsage"),
        "stop_reason": result.get("stop_reason"),
        "is_error": result.get("is_error"),
        "terminal_reason": result.get("terminal_reason"),
    }
    return total, extra


def git_info() -> tuple[str | None, bool | None]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True
            ).stdout.strip()
        )
        return sha or None, dirty
    except Exception:
        return None, None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", required=True)
    p.add_argument(
        "--request", required=True, help="fichier de la demande (syllabus/brief) tel que fourni"
    )
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--run-name", help="nom du run (défaut : nom du dossier de travail)")
    p.add_argument(
        "--out", help="dossier du pack (défaut : benchmarks/runs/<ts>_fable-skill-<arm>)"
    )
    p.add_argument(
        "--data-dir", default=str(REPO / "data"), help="bras B : stockage dataprep (raw_sources)"
    )
    p.add_argument("--config", help="bras B : config dataprep (provenance embeddings)")
    args = p.parse_args()

    workdir = Path(args.workdir).resolve()
    run_name = args.run_name or workdir.name
    meta = (
        json.loads((workdir / "run_meta.json").read_text(encoding="utf-8"))
        if (workdir / "run_meta.json").is_file()
        else {}
    )
    launch = (
        json.loads((workdir / "launch.json").read_text(encoding="utf-8"))
        if (workdir / "launch.json").is_file()
        else {}
    )
    model = meta.get("model") or launch.get("model") or "claude"
    request_text = Path(args.request).read_text(encoding="utf-8")
    query = f"<research_request>\n{request_text}\n</research_request>"

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = (
        Path(args.out)
        if args.out
        else REPO / "benchmarks" / "runs" / f"{ts}_fable-skill-{args.arm}_{run_name}"
    )
    out.mkdir(parents=True, exist_ok=False)
    log: list[str] = []

    extracts = load_extracts(workdir)
    report_path, stage = find_report(workdir)
    arbitrage = (workdir / "ARBITRAGE-REQUIS.md").is_file()
    success = report_path is not None and stage == "livraison" and not arbitrage
    if stage != "livraison":
        log.append(f"rapport final absent : repli sur « {stage} »")
    if arbitrage:
        log.append("ARBITRAGE-REQUIS.md présent : intervention humaine demandée → run non autonome")

    if args.arm == "A":
        chunks_payload, e_to_chunk = build_arm_a(extracts, workdir, log)
    else:
        chunks_payload, e_to_chunk = build_arm_b(extracts, workdir, log)
    ChunkSnapshot.model_validate(chunks_payload)  # auto-contrôle du schéma

    body = split_body(report_path.read_text(encoding="utf-8")) if report_path else ""
    body, order = renumber(body, extracts)
    sources = []
    for i, eid in enumerate(order, 1):
        rec = extracts[eid]
        filename = Path(str(rec.get("fichier") or "")).name
        chunk = next(
            (c for c in chunks_payload["chunks"] if c.get("chunk_id") == e_to_chunk.get(eid)), None
        )
        if chunk and chunk.get("filename"):
            filename = chunk["filename"]
        sources.append(
            {
                "source_id": f"S{i}",
                "file_name": filename,
                "topic": str(rec.get("question") or rec.get("localisation") or eid),
                "content": rec.get("_content") or str(rec.get("texte") or ""),
                "doc_ids": [e_to_chunk[eid]] if eid in e_to_chunk else [],
                "extract_id": eid,
            }
        )
    sources_md = "\n".join(f"- [{s['source_id']}] {s['topic']} — {s['file_name']}" for s in sources)
    report_md = f"{body}\n\n## Sources\n{sources_md}\n" if body else ""

    # raw_sources : fichiers exacts utilisés (bras A : fonds ; bras B : stockage dataprep)
    root = workdir / "fonds" if args.arm == "A" else Path(args.data_dir)
    archived, missing = [], []
    filenames = sorted({c["filename"] for c in chunks_payload["chunks"] if c.get("filename")})
    for filename in filenames:
        src = root / Path(filename).name
        if not src.is_file():
            missing.append(filename)
            continue
        (out / "raw_sources").mkdir(exist_ok=True)
        shutil.copy2(src, out / "raw_sources" / src.name)
        archived.append(
            {"filename": src.name, "sha256": hashlib.sha256(src.read_bytes()).hexdigest()}
        )

    usage_total, extra = claude_usage(meta)
    events_usage = aggregate_events(workdir) if (workdir / "events.jsonl").is_file() else {}
    sub_tokens = int(events_usage.get("subagents_total_tokens_reported") or 0)
    usage_main = dict(usage_total)
    usage_total = dict(usage_main)
    # Les sous-agents ne sont pas dans l'usage final du CLI (seul le coût les inclut) :
    # on ajoute leurs tokens déclarés (task_progress) pour un total comparable au workflow.
    usage_total["subagent_tokens"] = sub_tokens
    usage_total["total_tokens"] = usage_main["total_tokens"] + sub_tokens
    extra["subagents_total_tokens_reported"] = sub_tokens
    extra["rate_limit_events"] = events_usage.get("rate_limit_events")
    extra["events_usage"] = {
        k: v for k, v in events_usage.items() if k in ("main_agent", "subagents", "all_agents")
    }
    wall = float(meta.get("wall_seconds") or 0.0)
    sha, dirty = git_info()
    provenance = {
        "git_sha": sha,
        "git_dirty": dirty,
        "harness": "claude-code -p",
        "skill": "document-research",
        "arm": args.arm,
        "skill_sha256": sha256_text(
            (workdir / ".claude/skills/document-research/SKILL.md").read_text(encoding="utf-8")
        )
        if (workdir / ".claude/skills/document-research/SKILL.md").is_file()
        else None,
    }
    if args.arm == "B" and args.config:
        import yaml

        cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
        vs = cfg.get("vector_search") or {}
        provenance.update(
            {
                "config_file": args.config,
                "chroma_collection": meta.get("collection"),
                "embedding_provider": vs.get("chroma_embedding_provider"),
                "embedding_api_base": vs.get("chroma_embedding_api_base"),
                "embedding_model": vs.get("chroma_embedding_model"),
            }
        )
    deliverables = {
        rel: (workdir / rel).is_file()
        for rel in (
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
        )
    }
    stats = {
        "provenance": provenance,
        "config_name": f"fable-skill-{args.arm}",
        "writer_strategy": "skill-8-etapes",
        "manager": "claude-code-skill",
        "query": query,
        "report_file": "report.md",
        "output_dir": f"output/{run_name}",
        "success": bool(success),
        "models": {
            role: model
            for role in (
                "research",
                "planning",
                "search",
                "writer",
                "knowledge_preparation",
                "outline",
                "chapter_writer",
            )
        },
        "timings": {"total": wall, "wall_seconds": wall},
        "usage_by_phase": {"main_agent": usage_main, "total": usage_total},
        "agent_calls": {
            "subagents_spawned": ((extra.get("subagent_stats") or {}).get("spawned")),
            "turns": extra.get("num_turns"),
        },
        "n_sources": len(sources),
        "n_chunks": len(chunks_payload["chunks"]),
        "source_archive": {"files": archived, "missing": missing},
        "skill_run": {
            **extra,
            "report_stage": stage,
            "arbitrage_required": arbitrage,
            "deliverables": deliverables,
            "n_extracts": len(extracts),
            "n_extracts_cited": len(order),
            "adapter_log": log,
        },
    }
    if not success:
        stats["status"] = "failed"
        stats["failure"] = {
            "phase": "skill",
            "exception_type": "IncompleteRun",
            "message": "; ".join(log) or "rapport final absent",
        }

    (out / "report.md").write_text(report_md, encoding="utf-8")
    (out / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "chunks.json").write_text(
        json.dumps(chunks_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    keep = [
        d
        for d in (
            "01-cadrage",
            "02-collecte",
            "03-extraits",
            "04-analyse",
            "05-conception",
            "06-redaction",
            "07-revision",
            "08-livraison",
        )
        if (workdir / d).is_dir()
    ]
    (out / "skill_workdir").mkdir()
    for d in keep:
        shutil.copytree(workdir / d, out / "skill_workdir" / d)
    for f in ("journal.md", "retex.md", "ARBITRAGE-REQUIS.md", "run_meta.json", "launch.json"):
        if (workdir / f).is_file():
            shutil.copy2(workdir / f, out / "skill_workdir" / f)
    print(f"pack: {out}")
    print(
        f"  rapport: {stage} | succès: {success} | sources: {len(sources)} | chunks: {len(chunks_payload['chunks'])} "
        f"(non résolus: {sum(1 for c in chunks_payload['chunks'] if not c.get('resolved'))}) | raw_sources: {len(archived)} manquants: {missing}"
    )
    for line in log:
        print(f"  ! {line}")


if __name__ == "__main__":
    main()
