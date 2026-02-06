# FALLBACK STRATEGY

## ramework fallback générique (configurable) ✅ **ARCHITECTURE CORE**

**Principe** : Framework réutilisable avec Strategy pattern pour gérer les erreurs LLM de manière configurable par agent.

**Justification** :

- **Éviter hard-coding** : Stratégies définies en config YAML, pas dans le code
- **Réutilisable** : `writer_agent`, `search_agent`, `planner_agent`, futurs agents
- **Mesurable** : Logging centralisé pour évaluation modèles
- **Extensible** : Ajouter nouvelles stratégies sans toucher code existant
- **Itération rapide** : Tester Pass@K=2 vs Pass@K=3 en changeant config

**Architecture** (`src/agents/fallback_strategy.py`) :

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
import asyncio

@dataclass
class FallbackContext:
    """Contexte passé à la stratégie."""
    agent_name: str
    original_error: Exception
    attempt_number: int
    research_info: Any  # ResearchInfo original
    last_result: Any | None = None

class FallbackStrategy(ABC):
    """Abstraction pour stratégies de récupération."""

    @abstractmethod
    async def handle_error(
        self,
        ctx: FallbackContext,
        agent_fn: Callable
    ) -> tuple[bool, Any]:
        """
        Tente de récupérer l'erreur.

        Returns:
            (success: bool, result: Any)
        """
        pass

    def should_retry(self) -> bool:
        """Si True, le wrapper peut retry global après échec stratégie."""
        return False
```

**Wrapper générique** (`src/agents/agent_runner.py`) :

```python
from src.agents.fallback_strategy import FallbackStrategy, FallbackContext
from src.agents.metrics import FallbackMetrics
from openai.agents import Runner, Agent, ModelBehaviorError

async def run_agent_with_fallback(
    agent: Agent,
    strategy: FallbackStrategy,
    context: Any,  # ResearchInfo ou autre
    metrics: FallbackMetrics
) -> Any:
    """Wrapper générique avec fallback configurable et logging."""

    async def agent_fn():
        return await Runner.run(agent, context=context)

    attempt = 0
    max_attempts = 10

    while attempt < max_attempts:
        try:
            result = await agent_fn()

            # Log succès
            metrics.log_success(
                agent_name=agent.name,
                attempt=attempt,
                strategy_used=strategy.__class__.__name__ if attempt > 0 else "first_try"
            )

            return result

        except ModelBehaviorError as e:
            attempt += 1

            # Log échec
            metrics.log_failure(
                agent_name=agent.name,
                attempt=attempt,
                error=str(e),
                error_type="ModelBehaviorError"
            )

            # Appliquer stratégie
            ctx = FallbackContext(
                agent_name=agent.name,
                original_error=e,
                attempt_number=attempt,
                research_info=context
            )

            success, result = await strategy.handle_error(ctx, agent_fn)

            if success:
                metrics.log_recovery(
                    agent_name=agent.name,
                    strategy=strategy.__class__.__name__,
                    attempt=attempt
                )
                return result

            # Si stratégie échoue, retry ou fail
            if not strategy.should_retry():
                # Log échec final
                metrics.log_final_failure(agent.name, attempt)
                raise

    raise MaxRetriesExceededError(f"Agent {agent.name} failed after {attempt} attempts")
```

**Configuration** (`configs/config-default.yaml`) :

```yaml
agents:
  fallback_strategies:
    writer:
      type: "chained"
      strategies:
        - type: "retry_hint"
          max_retries: 1
        - type: "passk"
          k: 2
        - type: "markdown_fallback"

    search:
      type: "passk"
      k: 2 # Lancer 2 recherches, prendre première valide

    planner:
      type: "retry_hint"
      max_retries: 1

    # Autres agents : fail fast (default)
    default:
      type: "none"
```

**Factory pour créer stratégies depuis config** :

```python
# src/agents/strategy_factory.py
def create_strategy_from_config(config: dict) -> FallbackStrategy:
    """Crée une stratégie depuis la config YAML."""
    strategy_type = config["type"]

    if strategy_type == "none":
        return NoFallbackStrategy()

    elif strategy_type == "retry_hint":
        return RetryWithHintStrategy(max_retries=config.get("max_retries", 1))

    elif strategy_type == "passk":
        return PassAtKStrategy(k=config.get("k", 2))

    elif strategy_type == "markdown_fallback":
        return MarkdownFallbackStrategy()

    elif strategy_type == "chained":
        sub_strategies = [
            create_strategy_from_config(s)
            for s in config.get("strategies", [])
        ]
        return ChainedStrategy(sub_strategies)

    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
```

### S5 : Stratégies de récupération (implémentations)

**Stratégie 1 : Retry avec hint d'erreur**

```python
class RetryWithHintStrategy(FallbackStrategy):
    def __init__(self, max_retries: int = 1):
        self.max_retries = max_retries
        self.retries = 0

    async def handle_error(self, ctx, agent_fn):
        if ctx.attempt_number > self.max_retries:
            return (False, None)

        # ⚠️ IMPORTANT : Garder contexte original (search results, plan, etc.)
        # Ne pas créer "nouvelle question"

        # Ajouter hint d'erreur au contexte
        hint_message = {
            "role": "system",
            "content": f"Erreur de validation : {ctx.original_error}. Corrige le JSON avec un patch minimal."
        }

        # Retry avec même contexte + hint
        # L'implémentation exacte dépend de l'API Agents SDK
        # Il faut réinjecter ctx.research_info + hint

        self.retries += 1
        # result = await agent_fn_with_hint(ctx.research_info, hint_message)
        # return (True, result)

        # Placeholder pour le draft
        return (False, None)  # À implémenter

    def should_retry(self) -> bool:
        return self.retries < self.max_retries
```

**Stratégie 2 : Pass@K (génération multiple)**

```python
class PassAtKStrategy(FallbackStrategy):
    def __init__(self, k: int = 2):
        self.k = k

    async def handle_error(self, ctx, agent_fn):
        """
        Génère K candidats en parallèle, retourne le premier valide.

        Use case:
        - writer_agent: K=2 (après retry échoué)
        - search_agent: K=2 (lancer 2 recherches, prendre première)
        """
        # Lancer K candidats en parallèle
        tasks = [agent_fn() for _ in range(self.k)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Retourner premier valide
        for i, result in enumerate(results):
            if not isinstance(result, Exception):
                try:
                    # Validation Pydantic (dépend du type de result)
                    # Pour writer : validate ReportData
                    # Pour search : validate SearchResult
                    # validate(result)
                    return (True, result)
                except Exception as validation_error:
                    continue

        return (False, None)
```

**Stratégie 3 : Markdown fallback (writer uniquement)**

```python
class MarkdownFallbackStrategy(FallbackStrategy):
    async def handle_error(self, ctx, agent_fn):
        """
        Génère rapport en markdown pur (pas de JSON strict).
        Parse avec regex pour extraire structured data.
        """
        # Charger prompt markdown
        markdown_prompt = load_prompt("file_writer_agent_markdown.md")

        # Générer en mode markdown (pas de structured output)
        markdown_result = await generate_markdown_report(
            research_info=ctx.research_info,
            prompt=markdown_prompt
        )

        # Parser vers ReportData
        parsed = parse_markdown_report(
            markdown_result,
            ctx.research_info.research_topic
        )

        return (True, parsed)

def parse_markdown_report(markdown: str, research_topic: str) -> ReportData:
    """
    Parse markdown → ReportData avec validation.

    ⚠️ Impose titre : soit extrait, soit fallback sur research_topic.
    """
    # Extraire titre
    title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)

    # Fallback titre si absent
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = research_topic if research_topic else "Untitled Research Report"

    # Extraire summary
    summary_match = re.search(
        r'##\s+Executive Summary\s+(.+?)(?=##|\Z)',
        markdown,
        re.DOTALL | re.IGNORECASE
    )

    # Extraire questions
    questions = re.findall(
        r'^\d+\.\s+(.+)$',
        markdown,
        re.MULTILINE
    )

    # Si pas de titre dans markdown, insérer au début
    if not title_match:
        markdown = f"# {title}\n\n{markdown}"

    # Validation post-parse (Pydantic)
    return ReportData(
        markdown_report=markdown,
        short_summary=summary_match.group(1).strip() if summary_match else "",
        follow_up_questions=questions[:3] if questions else [],
        research_topic=research_topic
    )
```

**Stratégie 4 : No fallback (fail fast)**

```python
class NoFallbackStrategy(FallbackStrategy):
    async def handle_error(self, ctx, agent_fn):
        """Pas de récupération, échec immédiat."""
        return (False, None)
```

**Stratégie 5 : Chained (chaîne plusieurs stratégies)**

```python
class ChainedStrategy(FallbackStrategy):
    """
    Chaîne plusieurs stratégies dans l'ordre.

    Exemple pour writer:
    1. RetryWithHint
    2. PassAtK
    3. MarkdownFallback
    """
    def __init__(self, strategies: list[FallbackStrategy]):
        self.strategies = strategies

    async def handle_error(self, ctx, agent_fn):
        for i, strategy in enumerate(self.strategies):
            success, result = await strategy.handle_error(ctx, agent_fn)
            if success:
                return (True, result)
            # Si échec, passer à la stratégie suivante

        return (False, None)  # Toutes les stratégies ont échoué
```

**Exemple de Séquence de récupération** :

Avec config `chained` pour writer :

1. **Génération initiale** (structured output)
2. **Validation** Pydantic
3. ❌ Si échec → **Retry patch-mode** (max 1) avec error hint
4. **Validation** Pydantic
5. ❌ Si échec → **Pass@K=2** (générer 2 candidats, prendre premier valide)
6. **Validation** Pydantic
7. ❌ Si échec → **Fallback markdown** (génération pure markdown + parser regex)

**Avantage** : Configurable sans toucher code. Tester Pass@K=3 ? Changer YAML.
