import argparse
import asyncio
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from langsmith.wrappers import OpenAIAgentsTracingProcessor
from rich.console import Console

from agentic_research.agents.file_writer_agent import create_writer_agent
from agentic_research.agents.schemas import ReportData, ResearchInfo
from agentic_research.agents.utils import (
    context_aware_filter,
    generate_final_report_filename,
    model_spec_to_string,
)
from agentic_research.config import get_config
from agentic_research.printer import Printer
from agentic_research.tracing.trace_processor import FileTraceProcessor
from agents import (
    Agent,
    RunConfig,
    Runner,
    TResponseInputItem,
    add_trace_processor,
    gen_trace_id,
    trace,
)
from agents.mcp import MCPServer, MCPServerStdio

from .eval_utils import (
    build_fs_server_params,
    format_trajectory_report,
    load_test_case,
    save_result_input_list_to_json,
    save_trajectory_evaluation_report,
    test_trajectory_from_existing_files,
    validate_trajectory_spec,
)
from .prompts import llm_as_judge_prompt_v1
from .schemas import EvaluationResult

DEFAULT_SEARCH_DIR = Path("evaluations/temp_search_dir")


def _placeholder_content(test_case: dict, file_name: str) -> str:
    syllabus = test_case.get("syllabus") or test_case.get("query") or "Placeholder content"
    return f"{file_name}\n\n{syllabus}\n"


def _prepare_writer_inputs(test_case: dict) -> tuple[list[str], list[str], Path]:
    writer_eval = test_case.get("writer_eval", {})
    agenda = writer_eval.get("agenda") or []
    search_results = writer_eval.get("search_results") or []

    if not agenda or not search_results:
        raise ValueError("Test case missing writer_eval.agenda or writer_eval.search_results")

    search_results_dir = Path(writer_eval.get("search_results_dir", DEFAULT_SEARCH_DIR))
    temp_dir = Path(tempfile.mkdtemp(prefix="writer_eval_"))

    prepared_files: list[str] = []
    for entry in search_results:
        if isinstance(entry, str):
            source_path = search_results_dir / entry
            dest_path = temp_dir / entry
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if source_path.exists():
                shutil.copyfile(source_path, dest_path)
            else:
                dest_path.write_text(_placeholder_content(test_case, entry), encoding="utf-8")
            prepared_files.append(entry)
        elif isinstance(entry, dict):
            name = entry.get("name")
            if not name:
                raise ValueError("writer_eval.search_results entries must include 'name'")
            content = entry.get("content") or _placeholder_content(test_case, name)
            dest_path = temp_dir / name
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(content, encoding="utf-8")
            prepared_files.append(name)
        else:
            raise TypeError("writer_eval.search_results entries must be strings or dicts")

    return agenda, prepared_files, temp_dir


# ✅ ORDRE CORRIGÉ : read_multiple_files PUIS save_report PUIS generations
TRAJECTORY_SPEC = {
    "trajectory_spec": [
        {
            "id": "load_data",
            "type": "function_call",
            "name": "read_multiple_files",
            "required": True,
        },
        {
            "id": "report_generation_raw_notes",
            "type": "generation",
            "match_regex": r"## Raw Notes",
            "expected_content": "## Raw Notes",
            "required": True,
        },
        {
            "id": "report_generation_detailed_agenda",
            "type": "generation",
            "match_regex": r"## Detailed Agenda",
            "expected_content": "## Detailed Agenda",
            "required": True,
        },
        {
            "id": "report_generation_report",
            "type": "generation",
            "match_regex": r"## Report",
            "expected_content": "## Report",
            "required": True,
        },
        {"id": "save_report", "type": "function_call", "name": "save_report", "required": True},
    ]
}

spec = TRAJECTORY_SPEC["trajectory_spec"]

# répertoire où enregistrer le rapport final
output_report_dir = "evaluations/output_report_dir"


class EvaluationManager:
    def __init__(self):
        self.console = Console()
        self.printer = Printer(self.console)

    async def run(
        self,
        fs_server: MCPServer,
        research_info: ResearchInfo,
        agenda: list[str],
        search_results: list[str],
    ) -> None:
        self.fs_server = fs_server
        self.research_info = research_info

        trace_id = gen_trace_id()
        with trace(
            "Writer Agent Evaluation trace",
            trace_id=trace_id,
            metadata={"trace_type": "evaluation"},
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

            self.writer_agent = create_writer_agent([self.fs_server])

            report, messages = await self._write_report(agenda, search_results)

            final_report = f"Report summary\n\n{report.short_summary}"

            self.printer.update_item("final_report", final_report, is_done=True)
            self.printer.update_item("final_report_file", report.file_name, is_done=True)

            evaluation_report, evaluation_report_file = await self._evaluate_report_trajectory(
                report, messages
            )

            self.printer.update_item("evaluation_report", evaluation_report, is_done=True)
            self.printer.update_item("evaluation_report_file", evaluation_report_file, is_done=True)

            evaluation_result = await self._evaluate_report_quality(report)

            self.printer.update_item("evaluation_result", str(evaluation_result), is_done=True)

            print(f"Evaluation result: {evaluation_result.model_dump_json(indent=2)}")

            self.printer.end()

    async def _write_report(
        self, agenda: list[str], search_results: list[str]
    ) -> tuple[ReportData, list[TResponseInputItem]]:
        self.printer.update_item("writing", "Thinking about report...")
        input = (
            "Utilise l'agenda suivant ainsi que les contenus des fichiers attachés pour rédiger un rapport de recherche exhaustif et détaillé"
            ' sur le thème "Agent Engineer Fondations Course" avec focus sur les systèmes multi-agents en IA.'
            "\n\nAgenda:\n- " + "\n- ".join(agenda) + "\n"
            "\n\nSearch results: \n- " + "\n- ".join(search_results) + "\n"
        )

        # Désactiver le tracing automatique pour cet appel
        run_config = RunConfig(
            tracing_disabled=False,
            workflow_name="write_agent_eval",
            trace_metadata={"run_type": "evaluation"},
        )

        result = Runner.run_streamed(
            self.writer_agent, input, run_config=run_config, context=self.research_info
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

        report = result.final_output_as(ReportData)

        messages = result.to_input_list()

        return report, messages

    async def _evaluate_report_trajectory(
        self, report: ReportData, messages: list[TResponseInputItem]
    ) -> tuple[str, str]:
        ## EVALUATION SPECIFIC
        model_name = model_spec_to_string(self.writer_agent.model)
        report_file_name = (
            report.file_name
            if report.file_name
            else generate_final_report_filename(research_topic=report.research_topic)
        )

        # Générer le nom de base du fichier
        base_file_name = os.path.basename(report_file_name).rsplit(".md", 1)[0]
        safe_model_name = model_name.replace("/", "-")

        # Vérifier si le fichier original existe
        original_file_path = os.path.join(output_report_dir, report_file_name)
        if not os.path.exists(original_file_path):
            # Le fichier n'existe pas, le créer
            print(f"📝 Création du fichier rapport: {report_file_name}")
            with open(original_file_path, "w", encoding="utf-8") as f:
                f.write(report.markdown_report)

        # Renommer le fichier avec le nom de modèle
        final_file_name = f"{base_file_name}_{safe_model_name}.md"
        final_file_path = os.path.join(output_report_dir, final_file_name)
        os.rename(original_file_path, final_file_path)
        print(f" Fichier renommé: {report_file_name} -> {final_file_name}")

        # Utiliser le nom de base pour les autres fichiers
        original_report_file_name = f"{base_file_name}.md"

        save_result_input_list_to_json(
            model_name=model_name,
            report_file_name=original_report_file_name,
            messages=messages,
            output_report_dir=output_report_dir,
        )

        validation_report = validate_trajectory_spec(messages, spec)

        # Afficher le rapport lisible
        human_readable_report = format_trajectory_report(
            model_name=model_name, evaluation=validation_report, title="Writer Agent Trajectory"
        )

        # Utilisation de la fonction pour sauvegarder le rapport
        evaluation_report_file = save_trajectory_evaluation_report(
            model_name=model_name,
            output_report_dir=output_report_dir,
            report_file_name=original_report_file_name,
            human_readable_report=human_readable_report,
        )

        return human_readable_report, evaluation_report_file

    async def _evaluate_report_quality(self, report: ReportData) -> EvaluationResult:
        self.printer.update_item("evaluating", "Evaluating report quality...")

        report_quality_agent = Agent(
            name="report_quality_agent",
            instructions=llm_as_judge_prompt_v1,
            model="openai/gpt-4.1-mini",
            output_type=EvaluationResult,
        )

        result = await Runner.run(
            report_quality_agent,
            report.markdown_report,
        )

        evaluation_result = result.final_output_as(EvaluationResult)

        return evaluation_result


async def main(
    writer_model: str | None = None,
    test_case_name: str | None = None,
    config_file: str = "configs/config-default.yaml",
) -> None:
    """
    Fonction principale pour l'évaluation de l'agent writer.

    Args:
        writer_model: Modèle à utiliser pour l'agent writer. Si None, utilise la valeur par défaut du config.
    """
    # add_trace_processor(OpenAIAgentsTracingProcessor())
    add_trace_processor(FileTraceProcessor(log_dir="traces"))

    if not test_case_name:
        raise ValueError("test_case_name is required")

    test_case = load_test_case(test_case_name)
    agenda, search_results, temp_dir = _prepare_writer_inputs(test_case)

    config = get_config(config_file)
    # anthropic models does not seems to work (issue with json output)
    # "litellm/anthropic/claude-3-7-sonnet-latest"
    # "litellm/anthropic/claude-3-5-haiku-latest"
    # Mistral is working very WELL
    # Mistral small is working very WELL
    # OpenAI models
    # "openai/gpt-4.1-mini" # does not call the function save_report
    # "openai/gpt-4.1" does not call the function save_report
    if writer_model:
        config.models.writer_model = writer_model

    print(f"Writer model: {model_spec_to_string(config.models.writer_model)}")

    Path(output_report_dir).mkdir(parents=True, exist_ok=True)
    canonical_tmp_dir = os.path.realpath(str(temp_dir))
    print(f"Canonical tmp dir: {canonical_tmp_dir}")

    fs_server = MCPServerStdio(
        name="FS_MCP_SERVER",
        params=build_fs_server_params(canonical_tmp_dir),
        tool_filter=context_aware_filter,
        cache_tools_list=True,
    )
    async with fs_server:
        add_trace_processor(OpenAIAgentsTracingProcessor())

        research_info = ResearchInfo(temp_dir=canonical_tmp_dir, output_dir=output_report_dir)

        evaluation_manager = EvaluationManager()
        await evaluation_manager.run(fs_server, research_info, agenda, search_results)


def eval_main():
    """
    Point d'entrée synchrone pour les scripts Poetry.
    Parse les arguments CLI et passe le modèle à main().
    """
    parser = argparse.ArgumentParser(description="Évaluation de l'agent writer")
    parser.add_argument(
        "--writer-model",
        type=str,
        help="Modèle à utiliser pour l'agent writer. "
        "Valeurs recommandées: openai/gpt-5-mini, "
        "litellm/mistral/mistral-medium-latest, openai/gpt-4.1",
    )
    parser.add_argument(
        "--test-case",
        type=str,
        required=True,
        help="Test case name in evaluations/test_cases (without .yaml)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config-default.yaml",
        help="Config file to use (e.g., 'configs/config-gpt-4.1-mini.yaml')",
    )

    # Parse seulement les arguments connus pour éviter les erreurs avec d'autres arguments
    args, unknown = parser.parse_known_args()

    asyncio.run(
        main(
            writer_model=args.writer_model,
            test_case_name=args.test_case,
            config_file=args.config,
        )
    )


def test_main():
    """
    🚀 Point d'entrée pour tester la trajectoire et la qualité du rapport sur des fichiers existants
    Usage: poetry run test_trajectory <file_prefix>

    Args:
        file_prefix: Préfixe du fichier (ex: "evaluations/output/agent_engineer_fondations_course_final_report_20250715_161950")
                    Le script cherchera automatiquement les fichiers _messages.json et _final_report.md correspondants
    """
    if len(sys.argv) != 2:
        print("Usage: poetry run test_trajectory <file_prefix>")
        print("\nExemple:")
        print(
            "poetry run test_trajectory evaluations/output/agent_engineer_fondations_course_final_report_20250715_161950"
        )
        print("\nLe script cherchera automatiquement:")
        print("- <file_prefix>_messages.json (pour la trajectoire)")
        print("- <file_prefix>_final_report.md (pour la qualité du rapport)")
        return

    file_prefix = sys.argv[1]
    messages_file = f"{file_prefix}_messages.json"
    report_file = f"{file_prefix}.md"

    print(f"🔍 Test de trajectoire et qualité sur: {file_prefix}")
    print("=" * 80)

    # Vérifier que les fichiers existent
    if not os.path.exists(messages_file):
        print(f"❌ Fichier messages non trouvé: {messages_file}")
        return

    if not os.path.exists(report_file):
        print(f"❌ Fichier rapport non trouvé: {report_file}")
        return

    print(f"✅ Fichier messages trouvé: {messages_file}")
    print(f"✅ Fichier rapport trouvé: {report_file}")
    print()

    # 1. Test de la trajectoire
    print("📊 1. Test de la trajectoire...")
    print("-" * 40)
    spec = TRAJECTORY_SPEC["trajectory_spec"]
    trajectory_report = test_trajectory_from_existing_files(messages_file, spec)
    print(trajectory_report)

    # Sauvegarder le rapport de trajectoire
    trajectory_report_file = f"{file_prefix}_trajectory_test.txt"
    with open(trajectory_report_file, "w", encoding="utf-8") as f:
        f.write(trajectory_report)
    print(f"\n💾 Rapport de trajectoire sauvegardé: {trajectory_report_file}")

    # 2. Test de la qualité du rapport
    print("\n📈 2. Test de la qualité du rapport...")
    print("-" * 40)

    try:
        # Lire le contenu du rapport
        with open(report_file, encoding="utf-8") as f:
            report_content = f.read()

        # Créer un objet ReportData minimal pour l'évaluation
        report_data = ReportData(
            research_topic="Agent Engineer Fondations Course",
            report=report_content,
            file_name=os.path.basename(report_file),
            short_summary="Rapport de test chargé depuis fichier",
            follow_up_questions=[],
        )

        # Évaluer la qualité du rapport
        async def evaluate_quality():
            return await EvaluationManager()._evaluate_report_quality(report_data)

        # Exécuter l'évaluation de qualité
        evaluation_result = asyncio.run(evaluate_quality())

        print("📊 Résultat de l'évaluation de qualité:")
        print(f"{evaluation_result.model_dump_json(indent=2)}")

        # Sauvegarder le résultat de l'évaluation de qualité
        quality_report_file = f"{file_prefix}_quality_evaluation.json"
        with open(quality_report_file, "w", encoding="utf-8") as f:
            f.write(evaluation_result.model_dump_json(indent=2))
        print(f"\n💾 Résultat de qualité sauvegardé: {quality_report_file}")

    except Exception as e:
        print(f"❌ Erreur lors de l'évaluation de la qualité: {e}")
        import traceback

        traceback.print_exc()

    print("\n✅ Tests terminés!")


if __name__ == "__main__":
    eval_main()
