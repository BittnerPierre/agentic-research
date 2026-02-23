### Logging et métriques (évaluation modèles) ⚠️ **NOUVEAU, ESSENTIEL**

**Objectif** : Mesurer fiabilité modèles, pas juste debugger.

**Principe** : Métriques centralisées compatibles avec `./evaluations/` pour benchmark comparatif modèles.

**Justification** :

- UAT = validation qualitative, mais aussi **extraction métriques quantitatives**
- Baseline pour comparaison modèles (gpt-oss-20b vs Qwen3-30b vs Ministral-14B vs cloud)
- Décisions data-driven : Quelle stratégie récupère le plus ? Quel agent échoue le plus ?

**Implémentation** (`src/agents/metrics.py`) :

```python
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime

@dataclass
class RunMetric:
    """Métrique d'un run individuel."""
    agent_name: str
    timestamp: str
    success_first_try: bool
    attempts: int
    strategies_used: list[str]  # ["retry", "passk"]
    final_success: bool
    error_type: str | None  # "ModelBehaviorError", "ValidationError"
    error_message: str | None
    tokens_used: int | None = None
    duration_ms: int | None = None

@dataclass
class FallbackMetrics:
    """
    Métriques centralisées pour évaluation modèles.

    ⚠️ OBJECTIF : Mesurer fiabilité modèles, pas juste debug.
    Compatible avec ./evaluations/ pour benchmark comparatif.
    """
    runs: list[RunMetric] = field(default_factory=list)

    def log_success(self, agent_name: str, attempt: int, strategy_used: str):
        self.runs.append(RunMetric(
            agent_name=agent_name,
            timestamp=datetime.now().isoformat(),
            success_first_try=(attempt == 0),
            attempts=attempt + 1,
            strategies_used=[strategy_used] if strategy_used != "first_try" else [],
            final_success=True,
            error_type=None,
            error_message=None
        ))

    def log_failure(self, agent_name: str, attempt: int, error: str, error_type: str):
        self.runs.append(RunMetric(
            agent_name=agent_name,
            timestamp=datetime.now().isoformat(),
            success_first_try=False,
            attempts=attempt,
            strategies_used=[],
            final_success=False,
            error_type=error_type,
            error_message=str(error)
        ))

    def log_recovery(self, agent_name: str, strategy: str, attempt: int):
        # Mettre à jour le dernier run
        if self.runs and self.runs[-1].agent_name == agent_name:
            self.runs[-1].strategies_used.append(strategy)
            self.runs[-1].final_success = True

    def log_final_failure(self, agent_name: str, attempt: int):
        # Marquer échec définitif
        if self.runs and self.runs[-1].agent_name == agent_name:
            self.runs[-1].final_success = False

    def summary(self) -> dict:
        """Résumé agrégé par agent."""
        agents = {}
        for run in self.runs:
            if run.agent_name not in agents:
                agents[run.agent_name] = {
                    "total_runs": 0,
                    "success_first_try": 0,
                    "final_success": 0,
                    "total_attempts": 0,
                    "recovered_by_strategy": {}
                }

            a = agents[run.agent_name]
            a["total_runs"] += 1
            a["total_attempts"] += run.attempts

            if run.success_first_try:
                a["success_first_try"] += 1
            if run.final_success:
                a["final_success"] += 1

            for strategy in run.strategies_used:
                if strategy not in a["recovered_by_strategy"]:
                    a["recovered_by_strategy"][strategy] = 0
                a["recovered_by_strategy"][strategy] += 1

        # Calcul rates
        for agent_name, stats in agents.items():
            total = stats["total_runs"]
            stats["first_try_rate"] = stats["success_first_try"] / total if total > 0 else 0.0
            stats["final_success_rate"] = stats["final_success"] / total if total > 0 else 0.0
            stats["recovery_rate"] = (stats["final_success"] - stats["success_first_try"]) / total if total > 0 else 0.0
            stats["avg_attempts"] = stats["total_attempts"] / total if total > 0 else 0.0

        return agents

    def export_json(self, path: Path):
        """Exporte pour analyse post-run et ./evaluations/."""
        data = {
            "meta": {
                "version": "2.3.0",
                "timestamp": datetime.now().isoformat(),
                "total_runs": len(self.runs)
            },
            "summary": self.summary(),
            "runs": [
                {
                    "agent_name": r.agent_name,
                    "timestamp": r.timestamp,
                    "success_first_try": r.success_first_try,
                    "attempts": r.attempts,
                    "strategies_used": r.strategies_used,
                    "final_success": r.final_success,
                    "error_type": r.error_type,
                    "error_message": r.error_message,
                    "tokens_used": r.tokens_used,
                    "duration_ms": r.duration_ms
                }
                for r in self.runs
            ]
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def to_evaluation_format(self) -> dict:
        """
        Convertit les métriques au format ./evaluations/schemas.py.

        Compatible avec EvaluationResult pour intégration future.
        Permet d'alimenter les benchmarks comparatifs modèles.
        """
        summary = self.summary()

        # Calcul grades simples basés sur success rate
        def calc_grade(success_rate: float) -> str:
            if success_rate >= 0.9: return "A"
            if success_rate >= 0.75: return "B"
            if success_rate >= 0.6: return "C"
            if success_rate >= 0.4: return "D"
            return "E"

        grades = {}
        for agent, stats in summary.items():
            rate = stats["final_success_rate"]
            grades[agent] = {
                "grade": calc_grade(rate),
                "success_rate": rate,
                "recovery_rate": stats["recovery_rate"],
                "first_try_rate": stats["first_try_rate"]
            }

        # Judgment global
        avg_success = sum(g["success_rate"] for g in grades.values()) / len(grades) if grades else 0.0
        judgment = "PASS" if avg_success >= 0.75 else ("BORDERLINE" if avg_success >= 0.5 else "FAIL")

        return {
            "judgment": judgment,
            "grades": grades,
            "reasoning": f"Fallback metrics: {len(self.runs)} runs, {len(grades)} agents, avg success {avg_success:.1%}"
        }
```

**Exemple de sortie `fallback_metrics.json`** :

```json
{
  "meta": {
    "version": "2.3.0",
    "timestamp": "2026-02-04T15:30:00",
    "total_runs": 12
  },
  "summary": {
    "writer": {
      "total_runs": 4,
      "success_first_try": 2,
      "final_success": 4,
      "first_try_rate": 0.5,
      "final_success_rate": 1.0,
      "recovery_rate": 0.5,
      "avg_attempts": 1.5,
      "recovered_by_strategy": {
        "RetryWithHintStrategy": 1,
        "PassAtKStrategy": 1
      }
    },
    "search": {
      "total_runs": 8,
      "success_first_try": 6,
      "final_success": 8,
      "first_try_rate": 0.75,
      "final_success_rate": 1.0,
      "recovery_rate": 0.25,
      "avg_attempts": 1.25,
      "recovered_by_strategy": {
        "PassAtKStrategy": 2
      }
    }
  },
  "runs": [...]
}
```

**Usage dans managers** :

```python
# src/agentic_manager.py
from src.agents.metrics import FallbackMetrics
from src.agents.agent_runner import run_agent_with_fallback
from src.agents.strategy_factory import create_strategy_from_config

class AgenticResearchManager:
    def __init__(self, config: Config):
        self.config = config
        self.metrics = FallbackMetrics()

        # Charger stratégies depuis config
        self.strategies = {
            agent_name: create_strategy_from_config(strategy_config)
            for agent_name, strategy_config in config.agents.fallback_strategies.items()
        }

    async def run_research(self, query: str):
        # Planning avec fallback
        planner_strategy = self.strategies.get("planner", NoFallbackStrategy())
        plan = await run_agent_with_fallback(
            agent=planner_agent,
            strategy=planner_strategy,
            context=research_info,
            metrics=self.metrics
        )

        # Search avec Pass@K
        search_strategy = self.strategies.get("search", NoFallbackStrategy())
        search_results = await run_agent_with_fallback(
            agent=search_agent,
            strategy=search_strategy,
            context=research_info,
            metrics=self.metrics
        )

        # Writer avec fallback complet (chained)
        writer_strategy = self.strategies.get("writer", NoFallbackStrategy())
        report = await run_agent_with_fallback(
            agent=writer_agent,
            strategy=writer_strategy,
            context=research_info,
            metrics=self.metrics
        )

        # Save déterministe
        filepath = save_report_programmatically(report, output_dir, timestamp)

        # Export métriques
        self.metrics.export_json(output_dir / "fallback_metrics.json")

        return report
```

### S7 : Save programmatique (déterministe)

**Problème** : Writer agent peut skip `save_report` tool call (#7).

**Solution** : Appel programmatique après génération réussie (conservation v2.2.1) :

```python
import json
from pathlib import Path
from src.agents.schemas import ReportData

def save_report_programmatically(
    report: ReportData,
    output_dir: Path,
    timestamp: str
) -> Path:
    """
    Sauvegarde déterministe du rapport (sans tool call).

    ⚠️ Écrit TOUJOURS les métadonnées, même si rapport vide/invalide.
    Permet traçabilité des échecs.
    """
    filename = f"research_report_{timestamp}.md"
    filepath = output_dir / filename

    # Métadonnées (TOUJOURS écrire, même si rapport invalide)
    meta_file = output_dir / f"metadata_{timestamp}.json"
    metadata = report.model_dump()
    metadata["_saved_at"] = timestamp
    metadata["_is_valid"] = bool(report.markdown_report and len(report.markdown_report) > 100)

    meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Rapport markdown (lever si vide critique)
    if not report.markdown_report:
        # Écrire fichier vide + marquer invalide dans metadata (déjà fait)
        filepath.write_text("# [Rapport vide - échec génération]\n", encoding="utf-8")
        raise ValueError(f"Rapport vide généré (metadata sauvegardé: {meta_file})")

    filepath.write_text(report.markdown_report, encoding="utf-8")

    return filepath
```

**Intégration** : Manager appelle cette fonction directement après `run_agent_with_fallback` :

```python
try:
    report = await run_agent_with_fallback(writer_agent, strategy, context, metrics)
    filepath = save_report_programmatically(report, output_dir, timestamp)
    logger.info(f"Rapport sauvegardé: {filepath}")
except ValueError as e:
    logger.error(f"Rapport invalide mais metadata tracée: {e}")
    # Continuer ou lever selon politique
```
