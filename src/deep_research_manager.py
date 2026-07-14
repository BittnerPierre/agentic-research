from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from agents.mcp import MCPServer
from rich.console import Console

from agents import Runner, custom_span, gen_trace_id, trace

from .agents.file_search_agent import create_file_search_agent
from .agents.file_search_planning_agent import create_file_planner_agent
from .agents.file_writer_agent import create_writer_agent
from .agents.knowledge_preparation_agent import create_knowledge_preparation_agent
from .agents.schemas import (
    FileSearchItem,
    FileSearchPlan,
    ReportData,
    ResearchInfo,
)
from .agents.utils import coerce_report_data, save_final_report_function
from .config import get_config
from .gates import check_search_results_gate
from .printer import Printer
from .report_writer.aggregate import aggregate_sources
from .report_writer.pipeline import write_report_decomposed

logger = logging.getLogger(__name__)
_CHUNK_CITATION_RE = re.compile(r"\[[^\]\n:]+:[^\]\n]+\]")


class DeepResearchManager:
    def __init__(self):
        self.console = Console()
        self.printer = Printer(self.console)
        self._config = get_config()
        self.timings = {}  # Store timing information for benchmarking
        self.writer_metrics: dict = {}  # Per-step writer stats (decomposed strategy)
        self.agent_calls = {  # Track agent calls for benchmarking
            "knowledge_preparation_agent": 0,
            "file_planner_agent": 0,
            "file_search_agent": 0,
            "writer_agent": 0,
            "total": 0,
            "failures": 0,
        }
        self.search_failure_breakdown: dict[str, int] = {}
        self._benchmark_run_dir: Path | None = None
        self._benchmark_search_results: list[str] = []
        self.usage_summary = {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
        }
        self.usage_by_phase = {
            "knowledge_preparation": {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
            "planning": {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
            "search": {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
            "writing": {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
        }
        # Désactiver le tracing automatique pour cet appel
        # self._run_config = RunConfig(
        #     workflow_name="deep_research",
        #     tracing_disabled=False,
        #     trace_metadata= {
        #         "config_name": self._config.config_name
        #     })

    async def run(
        self,
        fs_server: MCPServer,
        dataprep_server: MCPServer,
        query: str,
        research_info: ResearchInfo,
    ) -> None:
        self.fs_server = fs_server
        self.dataprep_server = dataprep_server
        self.research_info = research_info

        # Start timing
        workflow_start = time.time()
        self._start_benchmark_run()

        trace_id = gen_trace_id()
        with trace(
            "Deep Research", trace_id=trace_id, metadata={"config_name": self._config.config_name}
        ):
            self.printer.update_item(
                "trace_id",
                f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}",
                is_done=True,
                hide_checkmark=True,
            )

            self.printer.update_item(
                "starting",
                "Démarrage de la recherche dans les fichiers...",
                is_done=True,
                hide_checkmark=True,
            )

            self.knowledge_preparation_agent = create_knowledge_preparation_agent(
                [self.dataprep_server]
            )
            self.file_planner_agent = create_file_planner_agent([self.fs_server])
            self.file_search_agent = create_file_search_agent(
                [self.fs_server], research_info.vector_store_id
            )
            self.writer_agent = create_writer_agent([self.fs_server], do_save_report=False)

            # Phase 1: Knowledge Preparation
            agenda = await self._execute_benchmark_phase(
                "knowledge_preparation", self._prepare_knowledge(query), query
            )
            print("\n\n=====AGENDA=====\n\n")
            print(agenda)

            # Phase 2: Planning
            search_plan = await self._execute_benchmark_phase(
                "planning", self._plan_file_searches(agenda), query
            )
            print("\n\n=====SEARCH PLAN=====\n\n")
            print(search_plan)

            # Phase 3: Search
            search_results = await self._execute_benchmark_phase(
                "search", self._perform_file_searches(search_plan), query
            )
            self._benchmark_search_results = search_results

            # Gate: block report if no exploitable source was produced
            try:
                check_search_results_gate(search_results)
            except Exception as exc:
                self.agent_calls["failures"] += 1
                self._persist_benchmark_failure(query, "search_gate", exc)
                raise

            # Phase 4: Writing
            report = await self._execute_benchmark_phase(
                "writing", self._write_report(query, search_results, agenda), query
            )

            final_report = f"Report summary\n\n{report.short_summary}"
            self.printer.update_item("final_report", final_report, is_done=True)

            self.printer.end()

        # Total timing
        self.timings["total"] = time.time() - workflow_start
        self.usage_by_phase["total"] = dict(self.usage_summary)

        print("\n\n=====SAVING REPORT=====\n\n")
        _new_report = await save_final_report_function(
            self.research_info.output_dir,
            report.research_topic,
            report.markdown_report,
            report.short_summary,
            report.follow_up_questions,
        )
        print(f"Report saved: {_new_report.file_name}")
        self._persist_benchmark_stats(query, _new_report, search_results)
        print("\n\n=====REPORT=====\n\n")
        print(f"Report: {report.markdown_report}")
        print("\n\n=====FOLLOW UP QUESTIONS=====\n\n")
        follow_up_questions = "\n".join(report.follow_up_questions)
        print(f"Follow up questions: {follow_up_questions}")

    async def _prepare_knowledge(self, query: str) -> str:
        self.printer.update_item("preparing", "Préparation de la connaissance...")
        result = await Runner.run(
            self.knowledge_preparation_agent,
            query,
            context=self.research_info,
        )
        self._record_usage(result, phase="knowledge_preparation")
        self.agent_calls["knowledge_preparation_agent"] += 1
        self.agent_calls["total"] += 1
        self.printer.update_item(
            "preparing", "Préparation de la connaissance terminée", is_done=True
        )
        return str(result.final_output)

    def _start_benchmark_run(self) -> None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        strategy = self._config.agents.writer_strategy
        self._benchmark_run_dir = (
            Path("benchmarks") / "runs" / f"{timestamp}_{self._config.config_name}_{strategy}"
        )
        self._benchmark_run_dir.mkdir(parents=True, exist_ok=True)

    async def _execute_benchmark_phase(self, phase: str, operation, query: str):
        started = time.time()
        try:
            return await operation
        except Exception as exc:
            self.timings[phase] = time.time() - started
            self.timings["total"] = sum(
                duration for name, duration in self.timings.items() if name != "total"
            )
            self.agent_calls["failures"] += 1
            self._persist_benchmark_failure(query, phase, exc)
            raise
        finally:
            self.timings.setdefault(phase, time.time() - started)

    async def _plan_file_searches(self, query: str) -> FileSearchPlan:
        self.printer.update_item("planning", "Planification des recherches dans les fichiers...")

        base_input = f"{query}"
        strict_json_retry_hint = (
            "\n\nIMPORTANT RETRY INSTRUCTION:\n"
            "Return ONLY a valid JSON object matching this exact schema:\n"
            '{"searches":[{"query":"<string>","reason":"<string>"}]}\n'
            "No markdown, no code fence, no additional text."
        )
        max_attempts = 2
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            planner_input = base_input if attempt == 1 else base_input + strict_json_retry_hint
            try:
                result = await Runner.run(
                    self.file_planner_agent,
                    planner_input,
                    context=self.research_info,
                )
                self._record_usage(result, phase="planning")
                plan = result.final_output_as(FileSearchPlan)
                if not plan.searches:
                    raise ValueError("FileSearchPlan is empty")

                self.printer.update_item(
                    "planning",
                    f"Effectuera {len(plan.searches)} recherches dans les fichiers",
                    is_done=True,
                )
                return plan
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    self.printer.update_item(
                        "planning",
                        f"Plan invalide (tentative {attempt}/{max_attempts}), nouvelle tentative...",
                    )
                else:
                    raise
            finally:
                self.agent_calls["file_planner_agent"] += 1
                self.agent_calls["total"] += 1

        # Defensive fallback; loop returns on success or raises on final failure.
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected planner failure without exception")

    async def _perform_file_searches(self, search_plan: FileSearchPlan) -> list[str]:
        with custom_span("Recherche dans les fichiers"):
            self.printer.update_item("searching", "Recherche dans les fichiers...")
            num_completed = 0
            tasks = [asyncio.create_task(self._file_search(item)) for item in search_plan.searches]
            results = []
            for task in asyncio.as_completed(tasks):
                result = await task
                if result is not None:
                    results.append(result)
                num_completed += 1
                self.printer.update_item(
                    "searching", f"Recherche... {num_completed}/{len(tasks)} terminées"
                )
            self.printer.mark_item_done("searching")
            return results

    async def _file_search(self, item: FileSearchItem) -> str | None:
        base_input = f"Terme de recherche: {item.query}\nRaison de la recherche: {item.reason}"
        if item.filenames:
            filenames = ", ".join(item.filenames)
            base_input += f"\nFichiers cibles: {filenames}"

        retry_hint = (
            "\n\nIMPORTANT RETRY INSTRUCTION:\n"
            "Write the summary to a file and return ONLY the filename.\n"
            "Every key claim must include a bracket citation.\n"
            "Prefer [document_id:chunk_index] when available in retrieval metadata.\n"
            "If document_id is unavailable, use [filename:chunk_index].\n"
            "Do not omit bracket citations.\n"
        )
        max_attempts = 2
        best_effort_path: str | None = None

        for attempt in range(1, max_attempts + 1):
            input_text = base_input if attempt == 1 else base_input + retry_hint
            try:
                result = await Runner.run(
                    self.file_search_agent,
                    input_text,
                    context=self.research_info,
                )
                self._record_usage(result, phase="search")
                # file_search_agent has no output_type (dropped in 2f35b47); per
                # its prompt it returns the bare filename as final_output text.
                raw_file_name = str(result.final_output or "").strip()
                normalized_path = self._normalize_search_result_path(raw_file_name)
                if normalized_path is None:
                    if attempt < max_attempts:
                        logger.warning(
                            "file_search invalid output path on attempt %s/%s for query=%r: %r",
                            attempt,
                            max_attempts,
                            item.query,
                            raw_file_name,
                        )
                        continue
                    self._record_search_failure("invalid_output_path", item)
                    return None

                if not self._search_result_has_chunk_citations(normalized_path):
                    if attempt < max_attempts:
                        best_effort_path = normalized_path
                        logger.warning(
                            "file_search missing chunk citations on attempt %s/%s for query=%r: %s",
                            attempt,
                            max_attempts,
                            item.query,
                            os.path.basename(normalized_path),
                        )
                        continue
                    logger.warning(
                        "file_search kept result without chunk citations after retry for query=%r: %s",
                        item.query,
                        os.path.basename(normalized_path),
                    )
                return normalized_path
            except Exception as exc:
                if attempt < max_attempts:
                    logger.warning(
                        "file_search exception on attempt %s/%s for query=%r: %s: %s",
                        attempt,
                        max_attempts,
                        item.query,
                        type(exc).__name__,
                        exc,
                    )
                    continue
                if best_effort_path is not None:
                    logger.warning(
                        "file_search retry failed after a usable uncited result for query=%r; "
                        "keeping first attempt file %s",
                        item.query,
                        os.path.basename(best_effort_path),
                    )
                    return best_effort_path
                self._record_search_failure(f"exception:{type(exc).__name__}", item, exc=exc)
                return None
            finally:
                self.agent_calls["file_search_agent"] += 1
                self.agent_calls["total"] += 1

        return None

    def _record_search_failure(
        self,
        reason: str,
        item: FileSearchItem,
        *,
        exc: Exception | None = None,
    ) -> None:
        self.agent_calls["failures"] += 1
        self.search_failure_breakdown[reason] = self.search_failure_breakdown.get(reason, 0) + 1
        if exc is None:
            logger.error("file_search failed for query=%r: %s", item.query, reason)
            return
        logger.error(
            "file_search failed for query=%r: %s (%s: %s)",
            item.query,
            reason,
            type(exc).__name__,
            exc,
        )

    def _search_result_has_chunk_citations(self, file_path: str) -> bool:
        try:
            with open(file_path, encoding="utf-8") as handle:
                return _CHUNK_CITATION_RE.search(handle.read()) is not None
        except OSError:
            return False

    def _normalize_search_result_path(self, raw_file_name: str) -> str | None:
        """
        Resolve the file_search output to a file inside temp_dir only.
        This prevents leaking/reading paths outside benchmark sandbox roots.
        """
        value = raw_file_name.strip().strip("`").strip('"').strip("'").strip("<>").strip()
        if not value:
            return None

        temp_root = os.path.realpath(self.research_info.temp_dir)
        candidate = Path(value)

        def _is_within_temp(path: str) -> bool:
            try:
                return os.path.commonpath([path, temp_root]) == temp_root
            except ValueError:
                return False

        # Absolute path: allow only if it is inside temp_dir and exists.
        if candidate.is_absolute():
            resolved = os.path.realpath(str(candidate))
            if _is_within_temp(resolved) and os.path.isfile(resolved):
                return resolved
            return None

        # Relative path: keep basename only, then resolve under temp_dir.
        # This blocks parent traversal or nested paths outside temp_dir.
        safe_name = candidate.name
        if not safe_name:
            return None

        possible_names = [safe_name]
        if "." not in safe_name:
            possible_names.append(f"{safe_name}.txt")

        normalized_name = self._normalize_search_filename(value)
        if normalized_name:
            possible_names.append(normalized_name)
            if "." not in normalized_name:
                possible_names.append(f"{normalized_name}.txt")

        for name in possible_names:
            resolved = os.path.realpath(os.path.join(temp_root, name))
            if _is_within_temp(resolved) and os.path.isfile(resolved):
                return resolved

        return None

    def _normalize_search_filename(self, raw_file_name: str) -> str:
        lower = raw_file_name.strip().lower()
        cleaned = re.sub(r"[^a-z0-9_\s]", "", lower)
        cleaned = re.sub(r"\s+", "_", cleaned).strip("_")
        if not cleaned:
            return ""
        max_len = 255
        txt_ext_len = 4
        base_max = max_len - txt_ext_len
        return cleaned[:base_max]

    async def _write_report(self, query: str, search_results: list[str], agenda: str) -> ReportData:
        if self._config.agents.writer_strategy == "decomposed":
            return await self._write_report_decomposed(query, search_results, agenda)
        return await self._write_report_monolithic(query, search_results)

    async def _write_report_decomposed(
        self, query: str, search_results: list[str], agenda: str
    ) -> ReportData:
        self.printer.update_item("writing", "Writing report (decomposed)...")
        self.writer_metrics = {}
        report = await write_report_decomposed(
            query,
            agenda,
            search_results,
            self.research_info,
            usage_sink=self._record_usage,
            metrics=self.writer_metrics,
        )
        self.printer.mark_item_done("writing")
        # Honest cost: the decomposed writer makes 1 outline call + N chapter
        # calls (+ retries), not one. spike-compare reads agent_calls.total, so
        # under-counting here would skew the monolithic-vs-decomposed comparison.
        writer_calls = int(self.writer_metrics.get("llm_calls", 1))
        self.agent_calls["writer_agent"] += writer_calls
        self.agent_calls["total"] += writer_calls
        return report

    async def _write_report_monolithic(self, query: str, search_results: list[str]) -> ReportData:
        self.printer.update_item("writing", "Thinking about report...")
        # Affichage plus lisible des fichiers de résultats de recherche
        formatted_results = (
            "\n".join(f"- {fname}" for fname in search_results) if search_results else "None"
        )
        input = (
            f"Rédige un rapport de recherche exhaustif et détaillé repondant à la demande suivante:\n\n {query}.\n\n"
            f"Utilise l'agenda produit ainsi que les contenus des fichiers attachés "
            f" pour rédiger un rapport conforme aux attentes.\n\n"
            f"Search results:\n{formatted_results}"
        )

        result = Runner.run_streamed(
            self.writer_agent,
            input,
            context=self.research_info,
        )
        update_messages = [
            "Thinking about report...",
            "Planning report structure...",
            "Writing outline...",
            "Creating sections...",
            "Cleaning up formatting...",
            "Finalizing report...",
            "Finishing report...",
        ]

        last_update = time.time()
        next_message = 0

        async for _ in result.stream_events():
            if time.time() - last_update > 5 and next_message < len(update_messages):
                self.printer.update_item("writing", update_messages[next_message])
                next_message += 1
                last_update = time.time()

        self.printer.mark_item_done("writing")
        self.agent_calls["writer_agent"] += 1
        self.agent_calls["total"] += 1
        self._record_usage(result, phase="writing")
        output = result.final_output
        return coerce_report_data(output, query)

    def _model_summary(self) -> dict:
        models = self._config.models

        def describe(spec) -> str | None:
            if spec is None:
                return None
            if isinstance(spec, str):
                return spec
            base_url = getattr(spec, "base_url", None)
            name = getattr(spec, "name", str(spec))
            return f"{name}@{base_url}" if base_url else name

        roles = [
            "research",
            "planning",
            "search",
            "writer",
            "knowledge_preparation",
            "outline",
            "chapter_writer",
        ]
        return {role: describe(getattr(models, f"{role}_model", None)) for role in roles}

    def _persist_benchmark_stats(self, query: str, report: ReportData, search_results) -> None:
        """Write a format-agnostic stats sidecar for cross-run comparison.

        Always emits ``sources.json`` (the aggregated *retrieved* corpus) so the
        grounding eval judges against what search actually returned — not the
        report — which is the whole point of moving aggregation out of the writer.
        """
        try:
            cfg = self._config
            strategy = cfg.agents.writer_strategy
            run_dir = self._benchmark_run_dir
            if run_dir is None:
                self._start_benchmark_run()
                run_dir = self._benchmark_run_dir
            assert run_dir is not None
            run_dir.mkdir(parents=True, exist_ok=True)

            sources = aggregate_sources(search_results)
            (run_dir / "sources.json").write_text(
                json.dumps([s.model_dump() for s in sources], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            writing_usage = self.usage_by_phase.get("writing", {})
            writing_out = writing_usage.get("output_tokens") or 0
            writing_time = self.timings.get("writing") or 0
            stats = {
                "config_name": cfg.config_name,
                "writer_strategy": strategy,
                "manager": "deep_manager",
                "query": query,  # full query/syllabus — spec-compliance grading needs it
                "report_file": report.file_name,
                # Record where the report was written so spike-grade can locate it
                # even under a custom --output-dir (stats stores only the basename).
                "output_dir": cfg.agents.output_dir,
                "success": True,
                "models": self._model_summary(),
                "timings": self.timings,
                "usage_by_phase": self.usage_by_phase,
                "agent_calls": self.agent_calls,
                "n_sources": len(sources),
                "derived": {
                    "writing_throughput_tok_s": (
                        writing_out / writing_time if writing_time else None
                    ),
                },
                "writer_metrics": self.writer_metrics,
            }
            (run_dir / "stats.json").write_text(
                json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"Benchmark stats saved: {run_dir / 'stats.json'}")
        except Exception as exc:  # never let stats persistence break a run
            print(f"Warning: could not persist benchmark stats: {exc}")

    def _persist_benchmark_failure(self, query: str, phase: str, exc: Exception) -> None:
        """Persist a zero-score artifact so failed workflows remain comparable."""
        try:
            run_dir = self._benchmark_run_dir
            if run_dir is None:
                self._start_benchmark_run()
                run_dir = self._benchmark_run_dir
            assert run_dir is not None

            sources = aggregate_sources(self._benchmark_search_results)
            (run_dir / "sources.json").write_text(
                json.dumps(
                    [source.model_dump() for source in sources], ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )
            failure = {
                "phase": phase,
                "exception_type": type(exc).__name__,
                "message": str(exc),
            }
            self.usage_by_phase["total"] = dict(self.usage_summary)
            stats = {
                "config_name": self._config.config_name,
                "writer_strategy": self._config.agents.writer_strategy,
                "manager": "deep_manager",
                "query": query,
                "report_file": None,
                "output_dir": self._config.agents.output_dir,
                "success": False,
                "status": "failed",
                "failure": failure,
                "models": self._model_summary(),
                "timings": self.timings,
                "usage_by_phase": self.usage_by_phase,
                "agent_calls": self.agent_calls,
                "n_sources": len(sources),
                "writer_metrics": self.writer_metrics,
            }
            (run_dir / "stats.json").write_text(
                json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            deterministic_failure = {
                "exercise": None,
                "score": 0.0,
                "qualified": False,
                "qualification": {
                    "passed": False,
                    "blockers": ["workflow failed"],
                    "critical_requirement_failures": [],
                    "format_blockers": [],
                },
                "requirements": [],
                "root_cause": {
                    "verdict": f"{phase}: {type(exc).__name__}",
                    **failure,
                },
            }
            (run_dir / "det_grade.json").write_text(
                json.dumps(deterministic_failure, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Benchmark failure saved: {run_dir / 'stats.json'}")
        except Exception as persist_exc:
            print(f"Warning: could not persist benchmark failure: {persist_exc}")

    def _record_usage(self, result, phase: str | None = None) -> None:
        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        if usage is None:
            return

        def _get_value(obj, key):
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        for key in (
            "requests",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_tokens",
            "reasoning_tokens",
        ):
            value = _get_value(usage, key)
            if value is None:
                continue
            try:
                value_int = int(value)
            except (TypeError, ValueError):
                continue
            self.usage_summary[key] += value_int
            if phase and phase in self.usage_by_phase:
                self.usage_by_phase[phase][key] += value_int
