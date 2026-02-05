# Plan de robustification du système agentic-research sur DGX Spark

**Version**: 2.3.1 DRAFT  
**Date**: 4 février 2026  
**Objectif**: Fiabiliser le workflow en 1 journée (UAT inclus) + mesurer fiabilité modèles

**⚠️ DRAFT v2.3.1** : Refonte architecture majeure pour validation avant intégration dans le plan principal.

**Note de lecture** :
- Ce document est un plan : les extraits de code/commandes sont illustratifs et
  non prescriptifs.
- L'implémentation finale reste à la main du développeur ; adapter aux
  contraintes réelles et éviter les chemins en dur.
- **Périmètre** : robustification uniquement (pas de nouvelles features). On
  conserve l'approche actuelle : répertoire syllabus monté en volume Docker ;
  l'envoi de fichiers sera traité ultérieurement.

**Amendements V2.3.1 (Architecture majeure)** :
- **Refonte S4-S8** : Framework fallback générique (Strategy pattern) dès S4 (pas de hard-coding)
- **Nouveau S6** : Logging et métriques pour évaluation modèles (compatible `./evaluations/`)
- **Context trimming** : Écarté de cette itération (hors scope robustification simple)
- **Phases restructurées** : Phase 2 groupée (framework + défenses + métriques, 4-5h avec TDD)
- **UAT renforcé** : Génération syllabus test bout-en-bout + extraction métriques JSON

---

## 1. Contexte

Le système **agentic-research** (multi-agent OpenAI Agents SDK + MCP) présente un **taux d'échec élevé** en mode local DGX Spark, principalement des **`ModelBehaviorError`** (JSON invalide, EOF, troncatures).

**Setup DGX actuel** :
- **Modèles** : Qwen3-Embedding (4B-Q8), gpt-oss-20b-mxfp4 (instruct), Ministral-3-14B-Q8 (reasoning)
- **Moteur d'inférence** : llama.cpp server
- **Vector store** : ChromaDB local
- **Contrainte** : Mono-utilisateur, zéro dépendance cloud (AgentOS local)

**Observation** : En mode cloud API (gpt-4.1-mini, claude, mistral), le workflow est stable. En mode local, nombreux échecs structurés.

---

## 2. Problèmes identifiés

### Logs analysés

**`test_files/writer_error.txt`** :
```
ModelBehaviorError: [...] Invalid JSON: EOF while parsing a string at line 1 column 6639
TypeAdapter(ReportData); 1 validation error for ReportData
```

**`test_files/dgx-spark-run.log`** :
- Mêmes erreurs JSON truncated
- `pydantic_core.ValidationError` sur JSONRPCMessage (MCP stdout non-JSON)

**Issues GitHub** :
- **#46** : gpt-oss-20b JSON invalide (structured output)
- **#47** : gpt-oss-20b génère URLs corrompues/hallucinations
- **#6** : upload_files_to_vectorstore fail si agent passe file_id au lieu de filename
- **#7** : Max turns exceeded (writer loop sur chemins incorrects)

---

## 3. Hypothèses (causes racines)

### H1 : Configuration llama.cpp sous-optimale ⚠️ **PRIORITÉ ABSOLUE**

**Constat dans `docker-compose.dgx.yml`** :

```yaml
llm-instruct:
  command:
    - "-n"
    - "${LLM_INSTRUCT_N_CTX:-2048}"  # ⚠️ Flag AMBIGU
    - "--n-gpu-layers"
    - "${LLM_INSTRUCT_N_GPU_LAYERS:-70}"
    # ❌ MANQUE: --n-predict (max output tokens)
    # ❌ MANQUE: --batch-size (traitement par batch)
```

**⚠️ ERREUR DE FLAG** (feedback reçu) :

Dans **llama.cpp server**, la syntaxe correcte est :
- **`--ctx-size`** (ou `-c`) : taille du contexte (input + output combinés)
- **`--n-predict`** : nombre max de tokens de sortie
- **`--batch-size`** (ou `-b`) : taille des batchs de traitement

Le flag `-n` seul est **ambigu** (CLI vs server ont des conventions différentes).

**Mécanique du contexte** :
- Le `ctx-size` est **input + output** (tout ce qui passe dans le contexte)
- Si prompt = 1500 tokens et ctx-size = 2048, il reste **~548 tokens max** pour la génération
- Sans `--n-predict` explicite, le modèle peut s'arrêter prématurément ou tronquer

**Conséquence** :
- Troncature en plein JSON → `EOF while parsing`
- Output incohérent sous pression mémoire

**Preuve attendue** (test contrôlé) :

Pour valider H1, exécuter ce test minimal **avant** Phase 1 :

```bash
# Test direct avec llama.cpp server (service isolé)
docker run --rm -it --gpus all \
  -v ${MODELS_DIR}:/models \
  ghcr.io/ggml-org/llama.cpp:server \
  --ctx-size 512 \          # Contexte volontairement TRÈS petit
  --n-predict 2000 \        # Output demandé GRAND
  -m /models/gpt-oss-20b-mxfp4.gguf \
  --prompt "Generate a very long JSON object with at least 50 fields describing a research report." \
  --log-disable

# Attendu : sortie tronquée vers ~450 tokens (512 - prompt)
# → Preuve que ctx-size limite output même si n-predict est élevé
```

Alternative (script Python minimal, optionnelle ; nécessite tiktoken) :

```python
# test_ctx_saturation.py
import requests, tiktoken

prompt = "Generate JSON..." * 100  # ~1500 tokens
enc = tiktoken.get_encoding("cl100k_base")
prompt_tokens = len(enc.encode(prompt))

response = requests.post("http://localhost:8002/completion", json={
    "prompt": prompt,
    "n_predict": 4000
})

output = response.json()["content"]
output_tokens = len(enc.encode(output))

print(f"Prompt: {prompt_tokens} tokens")
print(f"Output: {output_tokens} tokens")
print(f"Total: {prompt_tokens + output_tokens} (ctx-size actuel: 2048)")
# Si total ≈ 2048 → H1 confirmé
```

### H2 : Fragilité structured output avec modèles quantifiés

Modèles petits/quantifiés (gpt-oss-20b-mxfp4) moins fiables sur JSON strict :
- Hallucinations (URLs corrompues #47)
- Non-respect schéma Pydantic

### H3 : Pression contextuelle (conversations multi-agents longues)

Workflow multi-agent → conversations longues → contexte saturé → qualité ↓

Référence : `docs/Deep Research - How to Build a Multi-Agent Research Workflow That Actually Works.pdf` :
> "Garder une conversation courte augmente la qualité du rendu."

### H4 : Appels fonctions non déterministes

Writer agent doit appeler `save_report` tool → modèle peut skip ou boucler sur chemins incorrects (#7).

---

## 4. Solutions retenues

### S1 : Corriger configuration llama.cpp ✅ **PHASE 1 - BLOQUANT**

**Changements `docker-compose.dgx.yml`** :

```yaml
llm-instruct:
  command:
    - "--ctx-size"  # ✅ CORRECTION (était "-n")
    - "${LLM_INSTRUCT_CTX_SIZE:-8192}"  # 2048 → 8192
    - "--n-predict"  # ✅ NOUVEAU
    - "${LLM_INSTRUCT_N_PREDICT:-4096}"  # Limite explicite output
    - "--batch-size"  # ✅ CORRECTION (était "--n-batch")
    - "${LLM_INSTRUCT_BATCH_SIZE:-512}"
    - "--n-gpu-layers"
    - "${LLM_INSTRUCT_N_GPU_LAYERS:-70}"

llm-reasoning:
  command:
    - "--ctx-size"
    - "${LLM_REASONING_CTX_SIZE:-8192}"
    - "--n-predict"
    - "${LLM_REASONING_N_PREDICT:-4096}"
    - "--batch-size"
    - "${LLM_REASONING_BATCH_SIZE:-512}"
    - "--n-gpu-layers"
    - "${LLM_REASONING_N_GPU_LAYERS:-70}"
```

**Changements `models.env`** :

```bash
# Context size (input + output combinés)
LLM_INSTRUCT_CTX_SIZE=8192
LLM_REASONING_CTX_SIZE=8192

# Max output tokens (limite explicite génération)
LLM_INSTRUCT_N_PREDICT=4096
LLM_REASONING_N_PREDICT=4096

# Batch size (traitement par batch)
LLM_INSTRUCT_BATCH_SIZE=512
LLM_REASONING_BATCH_SIZE=512
```

**⚠️ Note sur defaults** :

Les valeurs par défaut **doivent rester cohérentes** entre `models.env` et `docker-compose.dgx.yml`.

**Stratégie recommandée** :
- `docker-compose.dgx.yml` : Utilise `${VAR:-default}` (fallback si variable absente)
- `models.env` : Fournit les valeurs explicites (prioritaires)
- Éviter divergence : si `models.env` change, vérifier que defaults dans compose sont cohérents

Exemple dans `docker-compose.dgx.yml` :
```yaml
- "--ctx-size"
- "${LLM_INSTRUCT_CTX_SIZE:-8192}"  # ✅ Default = valeur models.env
```

**Risque si divergence** :
- `models.env` dit `CTX_SIZE=8192`
- `docker-compose.yml` dit `${CTX_SIZE:-2048}` (default 2048)
- → Si variable non chargée, on retombe sur 2048 (régression silencieuse)

**Validation** :
1. Smoke test complet (query simple → rapport final)
2. Vérifier logs : pas de troncature EOF
3. Mesurer taux de complétion sur 3-5 runs

### S2 : Validations préventives d'entrée

**Problème** : Agent passe `file-xxx` au lieu de filename (#6), ou URLs corrompues (#47).

**Solution** : Fonction `validate_and_classify_input()` dans `src/dataprep/input_validation.py` :

```python
import re
from enum import Enum

class InputType(str, Enum):
    FILE_ID = "file_id"
    URL = "url"
    FILENAME = "filename"
    LOCAL_PATH = "local_path"
    INVALID = "invalid"

def validate_and_classify_input(value: str) -> tuple[InputType, str | None]:
    """
    Valide et classifie une entrée (file_id, URL, filename, path).
    
    **Contrat de retour** : (InputType, error_msg)
    - Si valide → (type, None)
    - Si invalide → (INVALID, message d'erreur)
    
    ⚠️ Le second élément est TOUJOURS un message d'erreur (ou None si valide).
    Pour obtenir la valeur normalisée, utiliser `value` directement si error_msg est None.
    """
    # File ID OpenAI
    if value.startswith("file-"):
        return (InputType.FILE_ID, None)
    
    # URL
    if value.startswith(("http://", "https://")):
        # Détection caractères corrompus/non-ASCII
        try:
            value.encode('ascii')
        except UnicodeEncodeError:
            return (InputType.INVALID, "URL contient caractères non-ASCII")
        return (InputType.URL, None)
    
    # Filename strict (sans séparateurs de chemin, évite path traversal)
    # Format: nom_fichier.ext (alphanumériques, tirets, underscores)
    if re.fullmatch(r"[a-zA-Z0-9_\-\.]+\.(txt|md|pdf|json|yaml)", value):
        return (InputType.FILENAME, None)
    
    # Path local (avec séparateurs)
    # ⚠️ Attention : accepté en mode mono-user, mais validation chemin recommandée
    if "/" in value or "\\" in value:
        # Détection path traversal basique
        if ".." in value:
            return (InputType.INVALID, "Path traversal détecté")
        return (InputType.LOCAL_PATH, None)
    
    return (InputType.INVALID, "Format non reconnu")
```

**Intégration** : `upload_files_to_vectorstore` appelle cette fonction et traite les erreurs :

```python
input_type, error_msg = validate_and_classify_input(file_or_url)

if input_type == InputType.INVALID:
    raise ValueError(f"Input invalide: {error_msg}")

# Ici input_type est valide, utiliser file_or_url directement
if input_type == InputType.FILE_ID:
    # Traiter file_id...
    pass
elif input_type == InputType.URL:
    # Traiter URL...
    pass
# etc.
```

### S3 : Support file_id dans upload_files_to_vectorstore

Ajouter `find_by_file_id()` dans `KnowledgeDBManager` (`src/dataprep/knowledge_db.py`) :

```python
def find_by_file_id(self, file_id: str) -> KnowledgeEntry | None:
    """Retrouve une entrée par son OpenAI file_id."""
    with self._lock:
        entries = self._load_entries()
        for entry in entries:
            if entry.openai_file_id == file_id:
                return entry
    return None
```

Modifier `upload_files_to_vectorstore` pour accepter file_id :

```python
input_type, error = validate_and_classify_input(file_or_url)

if input_type == InputType.FILE_ID:
    # Lookup dans knowledge_db
    entry = knowledge_db.find_by_file_id(file_or_url)
    if not entry:
        raise ValueError(f"file_id non trouvé: {file_or_url}")
    # Réutiliser openai_file_id existant
    file_id = entry.openai_file_id
```

### S4 : Framework fallback générique (configurable) ✅ **ARCHITECTURE CORE**

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
      k: 2  # Lancer 2 recherches, prendre première valide
      
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

**Séquence de récupération (ordre fixé pour writer)** :

Avec config `chained` pour writer :

1. **Génération initiale** (structured output)
2. **Validation** Pydantic
3. ❌ Si échec → **Retry patch-mode** (max 1) avec error hint
4. **Validation** Pydantic
5. ❌ Si échec → **Pass@K=2** (générer 2 candidats, prendre premier valide)
6. **Validation** Pydantic
7. ❌ Si échec → **Fallback markdown** (génération pure markdown + parser regex)

**Avantage** : Configurable sans toucher code. Tester Pass@K=3 ? Changer YAML.

### S6 : Logging et métriques (évaluation modèles) ⚠️ **NOUVEAU, ESSENTIEL**

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
                "version": "2.3.1",
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
    "version": "2.3.1",
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

### S8 : Validations préventives d'entrée

(Voir S2 dans document principal v2.2.1 - conservation intégrale)

**⚠️ Note** : Cette section n'est pas implémentée à ce jour ; s'appuyer sur la
S2 du plan principal v2.2.1 pour le design et les tests.

---

## 5. Solutions écartées (pour cette itération)

### E1 : Prompts spécifiques par modèle

**Justification** : Objectif = prompts agnostiques (cloud/local). Adaptation par modèle → Phase évaluation.

### E2 : Pass@K systématique

**Justification** : Coût élevé (double tokens, temps). **Alternative retenue** : Pass@K conditionnel via framework Strategy.

### E3 : Frameworks long-running (Restate/Temporal)

**Justification** : Overhead architecture. Pas nécessaire si S1-S7 suffisent. **Reconsidération** : Si problèmes persistent après cette itération.

### E4 : Grammars llama.cpp

**Justification initiale** : Faisabilité inconnue, effort incertain.

**⚠️ Reconsidération** (feedback reçu) :
- Grammars attaquent **classe d'erreurs** (syntaxe JSON) à la source
- **Décision révisée** : Non prioritaire tant que S1 pas corrigé
- **Reconsidérer si** : Taux fallback markdown > 30% après S1-S8

### E5 : Changement moteur inférence (vllm)

**Justification** : Overhead migration. Tester llama.cpp optimisé d'abord.

### E6 : Context trimming (call_model_input_filter)

**Justification** : Écarté de cette itération (hors scope robustification simple).

**Raison** :
- Complexité implémentation (filtrer par agent)
- Risque perdre références critiques (search agent)
- Bénéfice incertain si S1 (llama.cpp config) résout pression contextuelle

**Reconsidération** : Post-itération si conversations multi-agents dépassent ctx-size malgré S1.

---

## 6. Plan d'implémentation (1 journée avec TDD)

### Workflow TDD (rappel)

Pour chaque phase :
1. **Unit tests** (TDD) : Reproduire bugs, tester isolément
2. **Poetry test** : `poetry run pytest`
3. **Docker local smoke** : `docker-compose -f docker-compose.dgx.yml up -d` + smoke test
4. **Spark smoke** : Déploiement + smoke test
5. **Test fonctionnel** : UAT si applicable

**Possibilité grouper sprints** si couverture tests élevée.

---

### Phase 1 : Fix llama.cpp config (2-3h) ✅ **PRIORITÉ BLOQUANTE**

**Objectif** : Éliminer cause racine H1.

**Tâches** :
1. **Test H1 ctx saturation** (avant fix) : Valider hypothèse avec script Python
   - Script `test_ctx_saturation.py` : mesure tokens prompt + output vs ctx-size
   - Attendu : total ≈ 2048 (preuve que ctx limite output)
2. Corriger `docker-compose.dgx.yml` : `-n` → `--ctx-size`, ajouter `--n-predict`, `--batch-size`
3. Mettre à jour `models.env` avec nouvelles variables (vérifier cohérence defaults)
4. Redémarrer services : `docker-compose -f docker-compose.dgx.yml restart llm-instruct llm-reasoning`
5. **Validation** : Smoke test (query → rapport complet) × 3 runs
6. Vérifier logs : pas de troncature EOF, pas de `ModelBehaviorError` JSON

**TDD** :
- Test ctx saturation **avant** fix (baseline)
- Test ctx saturation **après** fix (validation)
- Assert : `total_tokens` peut atteindre ctx_size sans truncation

**Critère de succès** : 3/3 runs complètent sans `ModelBehaviorError` JSON truncation.

**Estimation** : 2-3h (incluant TDD + docker smoke + spark smoke)

---

### Phase 2 : Framework + Défenses + Métriques (4-5h) ⚠️ **GROUPÉ**

**Objectif** : Framework fallback générique + défenses inputs + logging pour évaluation modèles.

**2.1. Framework fallback (2h)**

**Tâches** :
1. Créer `src/agents/fallback_strategy.py` : 
   - `FallbackStrategy` (ABC)
   - `FallbackContext` (dataclass)
   - `RetryWithHintStrategy`
   - `PassAtKStrategy`
   - `MarkdownFallbackStrategy`
   - `NoFallbackStrategy`
   - `ChainedStrategy`

2. Créer `src/agents/agent_runner.py` : 
   - Wrapper `run_agent_with_fallback`
   - Exception `MaxRetriesExceededError`

3. Créer `src/agents/strategy_factory.py` :
   - Factory `create_strategy_from_config(config: dict) -> FallbackStrategy`

4. Ajouter config YAML : `agents.fallback_strategies` dans `config-default.yaml`

**TDD** :
- Unit tests pour chaque stratégie isolée (mock agent_fn)
- Test `RetryWithHintStrategy` : vérifie retry max, hint injection
- Test `PassAtKStrategy` : K candidats parallèles, premier valide
- Test `ChainedStrategy` : séquence retry → passk → markdown
- Test `NoFallbackStrategy` : fail immédiatement
- Integration test `run_agent_with_fallback` : wrapper + stratégie + métriques

**2.2. Logging et métriques (1h)**

**Tâches** :
1. Créer `src/agents/metrics.py` : 
   - `FallbackMetrics` (dataclass)
   - `RunMetric` (dataclass)
   - Méthodes : `log_success`, `log_failure`, `log_recovery`, `summary`, `export_json`
   - Méthode `to_evaluation_format()` : Compatible `./evaluations/schemas.py`

2. Intégrer dans `run_agent_with_fallback` : 
   - Appels `metrics.log_*` à chaque étape
   - Export JSON à la fin du run

**TDD** :
- Test `FallbackMetrics.summary()` : Agrégation correcte par agent
- Test `export_json()` : Format JSON valide
- Test `to_evaluation_format()` : Compatible `EvaluationResult` schema
- Mock plusieurs runs, vérifier calcul rates

**2.3. Défenses inputs + save (1-2h)**

**Tâches** :
1. Créer `src/dataprep/input_validation.py` : `validate_and_classify_input` (v2.2.1)
2. Ajouter `find_by_file_id()` dans `src/dataprep/knowledge_db.py`
3. Créer `src/agents/report_saver.py` : `save_report_programmatically()` (v2.2.1)
4. Intégrer validation dans `upload_files_to_vectorstore` (`src/dataprep/mcp_functions.py`)
5. Modifier managers (`agentic_manager.py`, `deep_research_manager.py`) :
   - Charger stratégies depuis config
   - Utiliser `run_agent_with_fallback` au lieu de `Runner.run` direct
   - Appeler `save_report_programmatically` après writer
   - Export `fallback_metrics.json` à la fin

**TDD** :
- Test `validate_and_classify_input` : file_id, URL, filename, path, path traversal
- Test `find_by_file_id` : lookup par file_id, retourne entry ou None
- Test `save_report_programmatically` : 
  - Rapport valide → fichiers .md + .json
  - Rapport vide → exception + metadata avec `_is_valid: false`
- Test intégration `upload_files_to_vectorstore` : 
  - Input file_id → lookup + réutilise
  - Input URL corrompu → reject
  - Input path traversal → reject

**Poetry test + Docker smoke + Spark smoke**

**Critère de succès** :
- ✅ Tests unitaires passent (>90% coverage stratégies + métriques + validations)
- ✅ Framework intégré dans au moins 1 manager (agentic ou deep)
- ✅ Smoke test génère `fallback_metrics.json` valide
- ✅ Issues #6 et #47 résolus (validation avec tests dédiés)

**Estimation** : 4-5h (incluant TDD complet + smoke tests)

---

### Phase 3 : UAT + Extraction Métriques (1-2h)

**Objectif** : Validation bout-en-bout + métriques pour évaluation modèles future.

**Tests de bout en bout** (critères opérationnels) :

Exécuter **4 queries** représentatives :
1. **Query simple** (smoke test) : "Explain Retrieval Augmented Generation"
2. **Query syllabus** (test prioritaire) : Générer syllabus de test complet (5+ sources)
   - **⚠️ PRIORITÉ UAT** : Vérifier génération syllabus qualitative et fiable
3. **Query URLs externes** (test Issue #47) : avec URLs non-syllabus
4. **Query file_id** (test Issue #6) : forcer usage file_id dans tools

**Critères de succès** (opérationnels, non métriques) :

✅ **Minimal** (Go/NoGo) :
- **Au moins 3/4 queries** complètent jusqu'au bout (rapport final généré)
- **Fichiers présents** : `research_report_*.md` + `metadata_*.json` pour chaque run réussi
- **Logs propres** : pas de troncature EOF, pas d'URLs corrompues (Issue #47)
- **Métriques JSON** : `fallback_metrics.json` généré et valide

✅ **Optimal** :
- **4/4 queries** complètent
- **Métadonnées `_is_valid: true`** pour tous les rapports
- **Save déterministe** : tous les rapports sauvegardés automatiquement (pas de skip)
- **Syllabus test** : Génération complète et qualitative (⚠️ priorité UAT)

✅ **Validation manuelle** (échantillon) :
- Lire 1 rapport : structure markdown correcte, contenu cohérent
- Vérifier metadata : `short_summary` non vide, `follow_up_questions` présentes
- **Syllabus** : Vérifier qualité, couverture sources, cohérence plan

**Extraction et analyse métriques** :

**Note** : Les commandes ci-dessous sont indicatives. Adapter les chemins et,
pour un fichier, utiliser `--syllabus` (approche volume) ou injecter son contenu
dans `--query` selon la CLI.

```bash
# Run UAT
cd /chemin/vers/agentic-research

# Test 1: Smoke simple
poetry run agentic-research --query "Explain RAG" --output-dir "uat_output/"

# Test 2: Syllabus (PRIORITÉ)
poetry run agentic-research --syllabus "test_files/syllabus_test.md" --output-dir "uat_output/"

# Test 3: URLs externes
poetry run agentic-research --query "test_files/query_urls_externes.md" --output-dir "uat_output/"

# Test 4: file_id
poetry run agentic-research --query "test_files/query_file_id.md" --output-dir "uat_output/"

# Vérifier résultats
ls -lh uat_output/  # Doit montrer 3-4 fichiers .md + .json + fallback_metrics.json
grep -l "_is_valid.*true" uat_output/metadata_*.json | wc -l  # Objectif: 3-4

# Analyser métriques fallback
cat uat_output/fallback_metrics.json | jq '.summary'
# Output attendu:
# {
#   "writer": {
#     "total_runs": 4,
#     "first_try_rate": 0.5,      # 50% first-try success
#     "final_success_rate": 1.0,  # 100% final success (avec fallback)
#     "recovery_rate": 0.5,       # 50% recovered by strategies
#     "recovered_by_strategy": {
#       "RetryWithHintStrategy": 1,
#       "PassAtKStrategy": 1
#     }
#   },
#   "search": {
#     "total_runs": 8,
#     "first_try_rate": 0.75,
#     "final_success_rate": 1.0,
#     "recovery_rate": 0.25,
#     "recovered_by_strategy": {
#       "PassAtKStrategy": 2
#     }
#   }
# }

# Générer rapport d'analyse (optionnel)
python scripts/analyze_fallback_metrics.py uat_output/fallback_metrics.json > uat_analysis.md
```

**Script d'analyse** (`scripts/analyze_fallback_metrics.py`, optionnel) :

```python
import json, sys
from pathlib import Path

def analyze_metrics(metrics_file: Path):
    with open(metrics_file) as f:
        data = json.load(f)
    
    summary = data["summary"]
    
    print("# Analyse Métriques Fallback\n")
    print(f"**Total runs**: {data['meta']['total_runs']}\n")
    
    for agent, stats in summary.items():
        print(f"## {agent.title()}\n")
        print(f"- First-try success: {stats['first_try_rate']:.1%}")
        print(f"- Final success: {stats['final_success_rate']:.1%}")
        print(f"- Recovery rate: {stats['recovery_rate']:.1%}")
        print(f"- Avg attempts: {stats['avg_attempts']:.1f}\n")
        
        if stats["recovered_by_strategy"]:
            print("**Stratégies de récupération** :")
            for strategy, count in stats["recovered_by_strategy"].items():
                print(f"- {strategy}: {count} récupérations")
            print()
    
    # Recommandations
    print("## Recommandations\n")
    writer_stats = summary.get("writer", {})
    if writer_stats.get("recovery_rate", 0) > 0.3:
        print("✅ Fallback framework efficace pour writer (>30% recovery)")
    if writer_stats.get("first_try_rate", 0) < 0.7:
        print("⚠️ First-try rate faible (<70%) → considérer grammars llama.cpp")

if __name__ == "__main__":
    analyze_metrics(Path(sys.argv[1]))
```

**Baseline pour évaluation future** :

Les métriques extraites servent de **baseline** pour :
- **Benchmark comparatif modèles** : gpt-oss-20b vs Qwen3-30b vs Ministral-14B vs cloud APIs
- **Mesure impact stratégies** : Retry vs Pass@K vs markdown fallback
- **Décisions optimisation** : Augmenter K ? Changer stratégie ? Changer modèle ?
- **Intégration `./evaluations/`** : Métriques compatibles pour `evaluate_trajectory`

**Intégration `./evaluations/`** (post-itération) :

```python
# evaluations/full_workflow_evaluator.py (future)
from src.agents.metrics import FallbackMetrics

def evaluate_with_fallback_metrics(run_output_dir: Path):
    """
    Combine fallback metrics avec trajectory validation.
    Compatible avec ./evaluations/schemas.py.
    """
    # Charger métriques fallback
    metrics = FallbackMetrics()
    metrics_file = run_output_dir / "fallback_metrics.json"
    
    with open(metrics_file) as f:
        metrics_data = json.load(f)
    
    # Convertir au format EvaluationResult
    eval_format = metrics.to_evaluation_format()
    
    # Combiner avec trajectory validation
    trajectory_result = validate_trajectory_spec(...)
    
    return {
        "fallback_metrics": eval_format,
        "trajectory": trajectory_result,
        "judgment": combine_judgments(eval_format["judgment"], trajectory_result["judgment"])
    }
```

**Estimation Phase 3** : 1-2h (UAT + extraction métriques + analyse)

---

## 7. Décisions techniques importantes

### 7.1. Pourquoi framework Strategy dès S4 (pas hard-codé d'abord)

**❌ Contre hard-codé** :
- Dette technique immédiate
- Refactor = risque régression
- Perd temps de test (2× tests : hard-codé + framework)
- Pas de métriques centralisées dès le début

**✅ Pour framework direct** :
- Pattern déjà défini → implémentation claire
- Tests unitaires isolés (stratégies indépendantes)
- Extensible sans toucher code (config YAML)
- **Logging intégré dès le début** → métriques dès run 1
- **Mesure fiabilité modèles** dès UAT (pas post-facto)

**Compromis KISS** :
- Seulement 4 stratégies de base (Retry, PassK, Markdown, None)
- Config simple (pas de nested complexity)
- Métriques basiques (counts, rates, pas ML)

### 7.2. Flags llama.cpp : pourquoi cette correction est critique

**Avant** (ambigu) :
```yaml
- "-n"
- "2048"
```

**Après** (explicite) :
```yaml
- "--ctx-size"
- "8192"
- "--n-predict"
- "4096"
```

**Impact** :
- Contexte clair : input + output = 8192 tokens max
- Limite sortie explicite : 4096 tokens max
- Pas de truncation silencieuse

### 7.3. Retry avec contexte vs nouvelle question

**Mauvais** :
```python
retry_prompt = f"L'erreur était : {error}. Réessaye."
result = await Runner.run(agent, retry_prompt)  # ❌ perd contexte
```

**Bon** :
```python
# Même task, mêmes inputs, + hint
messages.append({"role": "system", "content": f"Erreur validation : {error}. Corrige JSON minimal."})
result = await Runner.run(agent, context=research_info)  # ✅ garde contexte
```

### 7.4. Pass@K conditionnel vs systématique

**Coût Pass@K systématique** :
- Writer : 2000 tokens output × 3 candidats = 6000 tokens
- × Tous les runs → coût prohibitif

**Pass@K conditionnel** (via ChainedStrategy) :
- Uniquement si structured output + retry échouent
- Sur writer JSON uniquement (étape critique)
- Coût acceptable : rare + ciblé

**Pass@K pour search_agent** :
- Use case différent : **lancer 2 recherches en parallèle, prendre première**
- Pas de retry, juste redondance
- Augmente chances de trouver contenu pertinent

### 7.5. Grammars llama.cpp : quand reconsidérer

**Critère de reconsidération** :
- Après Phase 1-2 implémentées
- **Si** : Taux fallback markdown > 30% (depuis métriques)
- **Action** : Test pilote grammars JSON sur writer agent

**Avantage grammars** :
- Garantie syntaxe JSON à la source (pas repair a posteriori)
- Réduit retry/fallback

**Risque** :
- Peut impacter créativité/qualité contenu
- Nécessite tuning per-model

### 7.6. Métriques compatibles ./evaluations/

**Pourquoi c'est important** :
- `./evaluations/` = framework de benchmark comparatif modèles
- Métriques fallback doivent être **ingérables** par `evaluate_trajectory`
- Format cohérent : `to_evaluation_format()` → `EvaluationResult` schema

**Avantage** :
- Pas de duplication infrastructure évaluation
- Réutilise `Grades`, `Judgment`, `EvaluationResult` existants
- Combine fallback metrics + trajectory validation

---

## 8. Critères de succès

### Minimal (Go/NoGo itération)
- ✅ Config llama.cpp corrigée et validée (Phase 1)
- ✅ Smoke test complète 3/3 fois sans troncature EOF
- ✅ Framework fallback intégré dans au moins 1 manager
- ✅ `fallback_metrics.json` généré et valide

### Optimal (objectif 1j)
- ✅ Toutes les phases (1+2+3) implémentées
- ✅ UAT : 3/4 queries complètent + syllabus test réussi
- ✅ Issues #6 et #47 résolus
- ✅ Métriques exportées et analysées

### Stretch (si temps)
- ✅ 4/4 queries complètent (100% UAT)
- ✅ Script `analyze_fallback_metrics.py` implémenté
- ✅ Documentation technique mise à jour (README, ARCHITECTURE.md)

---

## Conclusion

Ce plan v2.3.1 se concentre sur **l'essentiel exécutable en 1 journée** avec **framework réutilisable et mesurable** :

1. **Phase 1 (bloquante)** : Corriger config llama.cpp (cause racine H1)
2. **Phase 2 (core)** : Framework fallback générique + défenses + métriques (4-5h)
3. **Phase 3 (validation)** : UAT syllabus test + extraction métriques baseline

**Prochaines étapes hors scope** :
- Évaluation comparative modèles (dense vs MoE, mono vs duo) via `./evaluations/`
- Optimisation stratégies (Pass@K=3 ? grammars llama.cpp ?)
- Frameworks long-running (Restate/Temporal)
- Context trimming (si ctx-size 8192 insuffisant)

**Go/NoGo** : Validation Phase 1 (smoke test 3/3) avant Phase 2-3.

**Différences clés v2.3.1 vs v2.2.1** :
- ✅ Framework Strategy générique (pas hard-coding retry)
- ✅ Logging/métriques pour évaluation modèles (compatible `./evaluations/`)
- ✅ Configuration YAML par agent (itération rapide)
- ✅ Baseline métriques dès UAT (pas post-facto)
- ❌ Context trimming écarté (hors scope)
