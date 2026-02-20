from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from rich.console import Console

from agents import Runner, custom_span, gen_trace_id, trace
from agents.mcp import MCPServer

from .agents.file_search_agent import create_file_search_agent
from .agents.file_search_planning_agent import create_file_planner_agent
from .agents.file_writer_agent import create_writer_agent
from .agents.knowledge_preparation_agent import create_knowledge_preparation_agent
from .agents.schemas import (
    FileSearchItem,
    FileSearchPlan,
    FileSearchResult,
    ReportData,
    ResearchInfo,
)
from .agents.utils import coerce_report_data, save_final_report_function
from .config import get_config
from .printer import Printer


class DeepResearchManager:
    def __init__(self):
        self.console = Console()
        self.printer = Printer(self.console)
        self._config = get_config()
        self.timings = {}  # Store timing information for benchmarking
        self.agent_calls = {  # Track agent calls for benchmarking
            "knowledge_preparation_agent": 0,
            "file_planner_agent": 0,
            "file_search_agent": 0,
            "writer_agent": 0,
            "total": 0,
            "failures": 0,
        }
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
        vector_mcp_server: MCPServer | None,
        query: str,
        research_info: ResearchInfo,
        progress_callback: (
            Callable[[float, float | None, str | None], Awaitable[None]] | None
        ) = None,
    ) -> ReportData:
        self.fs_server = fs_server
        self.dataprep_server = dataprep_server
        self.research_info = research_info

        # Start timing
        workflow_start = time.time()

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

            try:
                # Phase 1: Knowledge Preparation
                await asyncio.sleep(0)  # yield so cancellation can be delivered
                if progress_callback:
                    await progress_callback(0, 100, "Préparation connaissance")
                prep_start = time.time()
                agenda = await self._prepare_knowledge(query)
                self.timings["knowledge_preparation"] = time.time() - prep_start
                print("\n\n=====AGENDA=====\n\n")
                print(agenda)

                # Phase 2: Planning
                await asyncio.sleep(0)  # yield so cancellation can be delivered
                if progress_callback:
                    await progress_callback(25, 100, "Plan de recherche")
                plan_start = time.time()
                search_plan = await self._plan_file_searches(agenda)
                self.timings["planning"] = time.time() - plan_start
                print("\n\n=====SEARCH PLAN=====\n\n")
                print(search_plan)

                # Phase 3: Search
                await asyncio.sleep(0)  # yield so cancellation can be delivered
                if progress_callback:
                    await progress_callback(50, 100, "Recherche dans les documents")
                search_start = time.time()
                search_results = await self._perform_file_searches(search_plan)
                self.timings["search"] = time.time() - search_start

                # Phase 4: Writing
                await asyncio.sleep(0)  # yield so cancellation can be delivered
                if progress_callback:
                    await progress_callback(75, 100, "Rédaction du rapport")
                write_start = time.time()
                report = await self._write_report(query, search_results)
                self.timings["writing"] = time.time() - write_start
                if progress_callback:
                    await progress_callback(100, 100, "Terminé")

                final_report = f"Report summary\n\n{report.short_summary}"
                self.printer.update_item("final_report", final_report, is_done=True)
            finally:
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
        print("\n\n=====REPORT=====\n\n")
        print(f"Report: {report.markdown_report}")
        print("\n\n=====FOLLOW UP QUESTIONS=====\n\n")
        follow_up_questions = "\n".join(report.follow_up_questions)
        print(f"Follow up questions: {follow_up_questions}")

        return _new_report

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
        input_text = f"Terme de recherche: {item.query}\nRaison de la recherche: {item.reason}"
        if item.filenames:
            filenames = ", ".join(item.filenames)
            input_text += f"\nFichiers cibles: {filenames}"

        try:
            result = await Runner.run(
                self.file_search_agent,
                input_text,
                context=self.research_info,
            )
            self._record_usage(result, phase="search")
            self.agent_calls["file_search_agent"] += 1
            self.agent_calls["total"] += 1
            raw_file_name = str(result.final_output_as(FileSearchResult).file_name)
            normalized_path = self._normalize_search_result_path(raw_file_name)
            if normalized_path is None:
                self.agent_calls["failures"] += 1
            return normalized_path
        except Exception:
            self.agent_calls["failures"] += 1
            return None

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

    async def _write_report(self, query: str, search_results: list[str]) -> ReportData:
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
