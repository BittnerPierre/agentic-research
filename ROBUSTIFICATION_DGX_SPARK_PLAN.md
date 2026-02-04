---
name: Robustification DGX Spark
overview: Plan d'architecture pour fiabiliser le système agentic-research sur DGX Spark avec modèles locaux via llama.cpp, incluant analyse des problèmes, solutions envisagées, et implémentation TDD avec métriques de fiabilité.
todos:
  - id: phase0-tdd-infra
    content: "Phase 0: Infrastructure TDD - Créer tests reproduction bugs + WorkflowMetrics + baseline (1-2j)"
    status: pending
  - id: phase1-llama-config
    content: "Phase 1: Config llama.cpp - Augmenter n_ctx=8192, n_predict=4096, n_batch=512 + valider (0.5-1j)"
    status: pending
  - id: phase2-validations
    content: "Phase 2.1: Validations préventives - Input validation (file_id, URL, filename) (0.5j)"
    status: pending
  - id: phase2-fix-issue6
    content: "Phase 2.2: Fix Issue #6 - Support file_id dans upload_files_to_vectorstore (0.5j)"
    status: pending
  - id: phase2-retry
    content: "Phase 2.3: Retry intelligent - RetryHandler avec hint d'erreur Pydantic (1j)"
    status: pending
  - id: phase3-markdown-fallback
    content: "Phase 3.1: Markdown fallback - Writer markdown pur + parser regex (1j)"
    status: pending
  - id: phase3-save-programmatic
    content: "Phase 3.2: Save programmatique - Appel déterministe save_report (0.5j)"
    status: pending
  - id: phase4-context-trim
    content: "Phase 4: Context engineering - call_model_input_filter avec trimming (1j)"
    status: pending
  - id: phase5-eval-final
    content: "Phase 5: Évaluation finale - Benchmark complet + rapport + documentation (0.5j)"
    status: pending
isProject: false
---

# Plan de robustification du système agentic-research sur DGX Spark

**Document d'architecture technique**  
**Version**: 1.0  
**Date**: 4 février 2026  
**Auteur**: Équipe Applied AI - Deep Research

---

## Abstract

Ce document présente une stratégie complète de robustification du système multi-agent **agentic-research** pour son déploiement sur la workstation **NVIDIA DGX Spark** avec modèles d'inférence locaux servis par **llama.cpp**. Le système, initialement développé et validé avec des modèles cloud via API (OpenAI, Anthropic, Mistral), présente un taux d'échec significativement élevé en mode local, principalement dû à des erreurs de sorties structurées (`ModelBehaviorError`).

L'analyse identifie trois causes racines : (1) configuration sous-optimale de llama.cpp (context window et output limits), (2) fragilité des sorties structurées JSON avec modèles quantifiés de petite taille, et (3) pression contextuelle liée aux conversations multi-agents longues. Le plan propose une approche incrémentale en 5 phases avec validation TDD : configuration moteur d'inférence, validations préventives, fallbacks intelligents, context engineering, et infrastructure de métriques pour l'évaluation continue.

**Contraintes clés** : Système mono-utilisateur, zéro dépendance cloud (objectif AgentOS local), ressources GPU limitées (GB10, 128Go RAM).

---

## 1. Contexte et objectifs

### 1.1. Contexte du projet

Le système **agentic-research** est un framework multi-agent de recherche profonde (Deep Research) développé sur la base de l'**OpenAI Agents SDK** et du protocole **MCP (Model Context Protocol)**. Il permet de :

- Ingérer des sources de connaissances (URLs, documents)
- Orchestrer des agents spécialisés (planification, recherche, écriture)
- Générer des rapports de recherche complets et structurés

**Historique d'architecture** (référence : `Deep Research - How to Build a Multi-Agent Research Workflow That Actually Works.pdf`) :

- **Phase 1** : Architecture "Agentic Approach" avec agent superviseur ReACT
  - Problèmes : 42M+ tokens dev, coût élevé, qualité dégradée en fin de rapport, tool calls non fiables
- **Phase 2** : Évolution vers "DeepResearch Architecture" avec orchestration déterministe
  - Gains : Cost ↓, reliability ↑, parallélisation possible

**Déploiement cloud** (état actuel validé) :

- Modèles : gpt-4.1-mini, o3-mini, claude-3.7-sonnet, mistral-medium, magistral-medium
- Retrieval : OpenAI vector_store + Response API file_search
- Workflow stable, taux de complétion élevé
- Problèmes connus par modèle (ex : GPT-4 skip save_report, Claude sorties structurées fragiles)

### 1.2. Objectifs de migration DGX Spark

**Infrastructure cible** :

- Workstation NVIDIA DGX Spark
- GPU : GB10 avec 128Go RAM unifié CPU/GPU
- Modèles locaux servis via **llama.cpp** (pas d'API cloud)

**Setup actuel DGX** :

- **Embedding** : Qwen3-Embedding-4B-Q8_0 (4B params, quantized 8-bit)
- **LLM Instruct** : gpt-oss-20b-mxfp4 (20B params, quantized mxfp4)
- **LLM Reasoning** : Ministral-3-14B-Reasoning-2512-Q8_0 (14B params, quantized 8-bit)
- **Vector store** : ChromaDB local (remplacement OpenAI vector_store)
- **DataPrep** : MCP server custom (remplacement OpenAI file_search)

**Managers disponibles** :

- `deep_manager` : Reasoning → plan, puis Instruct séquentiel (search + write)
- `agentic_manager` : Agent superviseur actif tout au long du workflow

**Contrainte critique** : Système mono-utilisateur, zéro dépendance externe (objectif AgentOS autonome)

### 1.3. Objectif de cette itération

**Primaire** : Fiabiliser le système pour permettre la phase d'évaluation comparative des modèles (benchmarking).

**Secondaires** :

- Réduire le taux de `ModelBehaviorError` (JSON invalide)
- Améliorer la robustesse via fallbacks et retry intelligents
- Implémenter des métriques de fiabilité pour mesurer les régressions
- Préparer le terrain pour l'évaluation systématique des modèles locaux

**Hors scope** :

- Recherche du meilleur combo reasoning/instruct (phase évaluation ultérieure)
- Refonte du framework d'évaluation
- Déploiement multi-utilisateurs

---

## 2. État des lieux : Constats

### 2.1. Symptômes observés

**Issue #46 : JSON invalide (structured output)**

```
ModelBehaviorError: Invalid JSON when parsing ...
EOF while parsing a string at line 1 column 6639
```

**Exemple concret** (`test_files/writer_error.txt`) :

- Writer agent génère ~6.6KB de JSON valide
- Génération stoppée brutalement mid-string
- Pydantic rejette : `"...or resource scheduling,` (guillemet jamais fermé)

**Issue #47 : URLs corrompues/hallucinées**

```
ValueError: Unable to download content from: https://medium.com/@...??..??..??..
UnicodeEncodeError: 'ascii' codec can't encode character '\u2026'
```

**Exemple** :

```
https://medium.com/@callumjmac/advanced-retrieval-..??????????????????????..?…?..
```

**Observations additionnelles** :

- Smoke test technique passe (système opérationnel)
- Workflow va jusqu'au bout dans certains cas
- Taux d'échec beaucoup plus élevé qu'en cloud API
- Texte généré parfois "cryptique" ou incohérent

### 2.2. Métriques observées

**Mode cloud (baseline)** :

- Taux de complétion : ~85-90%
- Erreurs structurées : <5% (selon le modèle)
- Problèmes connus mais identifiés

**Mode DGX Spark** :

- Taux de complétion : ~30-40% (estimation)
- `ModelBehaviorError` : majorité des échecs
- URLs corrompues : fréquent
- Comportement non déterministe

### 2.3. Configuration actuelle llama.cpp

**Extrait `docker-compose.dgx.yml**` :

```yaml
llm-instruct:
  command:
    - "-m"
    - "${LLM_INSTRUCT_MODEL_PATH}"
    - "-n"
    - "${LLM_INSTRUCT_N_CTX:-2048}" # ⚠️ Context window
    - "--n-gpu-layers"
    - "${LLM_INSTRUCT_N_GPU_LAYERS:-70}"
    # ❌ MANQUE: --n-predict (max output tokens)
    # ❌ MANQUE: --n-batch (batch size)

llm-reasoning:
  command:
    - "-m"
    - "${LLM_REASONING_MODEL_PATH}"
    - "-n"
    - "${LLM_REASONING_N_CTX:-2048}" # ⚠️ Context window
    - "--n-gpu-layers"
    - "${LLM_REASONING_N_GPU_LAYERS:-999}"
    # ❌ MANQUE: --n-predict
    # ❌ MANQUE: --n-batch
```

**Paramètres critiques manquants** :

- `--n-predict` : Max tokens en sortie (default llama.cpp : 128-512 selon version)
- `--n-batch` : Batch size pour traitement prompt

---

## 3. Analyse des problèmes : Hypothèses

### 3.1. Hypothèse H1 : Configuration llama.cpp sous-optimale

**Analyse** :

**Context window (n_ctx = 2048)** :

- Prompt système + search results + historique conversation ≈ 1500 tokens
- Reste pour output : ~550 tokens
- Writer essaye de générer ~2000 tokens (6.6KB) → **impossible, overflow**

**Output limit (n_predict non spécifié)** :

- Default llama.cpp : 128, 256 ou 512 tokens selon version
- Génération stoppée à 6639 chars ≈ 1500-1800 tokens
- **Cohérent avec n_predict default entre 1500-2000**

**Conséquence** :

- Génération tronquée mid-string → JSON invalide
- Context overflow → comportement imprévisible
- Mémoire GPU sous pression → "partir en vrille"

**Probabilité** : **Très élevée** (90%)  
**Impact** : **Critique** (bloque majorité des workflows)

### 3.2. Hypothèse H2 : Fragilité modèles quantifiés petite taille

**Analyse** :

**gpt-oss-20b-mxfp4** (20B params, quantized mxfp4) :

- Quantization agressive (mxfp4 ≈ 4-bit mixed precision)
- Perte de précision sur génération structurée
- Hallucinations : URLs avec caractères Unicode, non-respect syllabus

**Comparaison cloud** :

- gpt-4.1-mini (propriétaire, non quantifié) : stable structured output
- claude-3.7-sonnet : problèmes structured output **aussi** (connu)
- mistral-medium : fiable structured output

**Constat** : Les modèles quantifiés de 20B params ou moins ont du mal avec :

- JSON long et complexe
- Contraintes strictes (syllabus-only)
- Consistency sur longues générations

**Probabilité** : **Moyenne-Élevée** (70%)  
**Impact** : **Élevé** (limite choix de modèles)

**Note** : Ministral-3-14B-Q8_0 (reasoning) en Q8 (8-bit) devrait être plus stable que mxfp4.

### 3.3. Hypothèse H3 : Pression contextuelle multi-agents

**Analyse** :

**Référence** : Document Deep Research, slides 10-12

> "Large token usage and extended contexts impact the quality and consistency of text generation"
> "Final sections — quality noticeably degrades"

**Workflow multi-agent** :

1. Supervisor agent → Planning agent (full prompt)
2. Planning agent → File search agents parallèles (context + plan)
3. File search agents → Writer agent (context + plan + search results)
4. Writer agent : context total = système + historique + inputs

**À chaque handoff** : Context s'accumule

- Messages système de chaque agent
- Historique des tool calls
- Résultats intermédiaires

**Avec n_ctx=2048**, le context est **saturé** avant même le writer.

**Solutions connues** (document Deep Research, slide 13) :

- MCP Filesystem : cache intermediate results
- Context compaction : résumer entre agents
- Sessions persistantes : gérer historique intelligent

**Probabilité** : **Élevée** (80%)  
**Impact** : **Moyen-Élevé** (dégrade qualité, pas bloquant)

### 3.4. Hypothèse H4 : Tool calling non fiable

**Analyse** :

**Issue #6** : Agent passe `file-xxx` au lieu de filename

- MCP tool attend filename ou URL
- Agent "hallucine" un file_id OpenAI (héritage mode cloud ?)

**Issue #7** : Writer agent loop sur file paths incorrects

- Agent essaye `/Users/.../file.txt` au lieu de `/tmp/.../file.txt`
- MCP rejette (hors allowed directories)
- Agent boucle 18 turns jusqu'à max_turns exceeded

**Issue #47** : Agent génère URLs corrompues

- Au lieu de prendre URL du syllabus, génère nouvelle URL avec junk

**Constat** : Les modèles locaux (gpt-oss-20b) ont du mal à :

- Suivre les instructions de format précis
- Construire les paths/arguments corrects
- Respecter les contraintes (syllabus-only)

**Probabilité** : **Élevée** (85%)  
**Impact** : **Moyen** (contournable via validations)

---

## 4. Solutions envisagées

### 4.1. Solutions retenues (à implémenter)

#### S1 : Augmenter configuration llama.cpp

**Objectif** : Éliminer H1 (configuration sous-optimale)

**Changements** :

```yaml
# Context window: 2048 → 8192
LLM_INSTRUCT_N_CTX: 8192
LLM_REASONING_N_CTX: 8192

# NEW: Max output tokens
LLM_INSTRUCT_N_PREDICT: 4096
LLM_REASONING_N_PREDICT: 4096

# NEW: Batch size
LLM_INSTRUCT_N_BATCH: 512
LLM_REASONING_N_BATCH: 512
```

**Justification** :

- Résout directement la troncation à 6.6KB
- Permet génération complète des rapports
- Cost marginal en mémoire GPU (context scaling linéaire)

**Risques** :

- OOM GPU si context trop grand
- Latence augmentée (plus de tokens à traiter)

**Mitigation** :

- Tester d'abord avec n_ctx=8192, réduire à 4096 si OOM
- Monitorer VRAM usage

**Priorité** : **P0** (critique, quick win potentiel)

#### S2 : Validations d'entrée préventives

**Objectif** : Bloquer H4 (tool calling non fiable) tôt

**Implémentation** :

```python
def validate_and_classify_input(input_item: str) -> tuple[InputType, str]:
    # Détecter file_id
    if input_item.startswith("file-"):
        if not re.match(r"^file-[A-Za-z0-9]+$", input_item):
            raise ValidationError(f"Malformed file_id: {input_item}")
        return (InputType.FILE_ID, input_item)

    # Détecter URL corrompue
    elif input_item.startswith(("http://", "https://")):
        if any(char in input_item for char in ["…", "\u2026", "?"*3]):
            raise ValidationError(f"Corrupted URL: {input_item}")
        return (InputType.URL, input_item)

    # Filename
    else:
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", input_item):
            raise ValidationError(f"Invalid filename: {input_item}")
        return (InputType.FILENAME, input_item)
```

**Avantages** :

- Erreur levée immédiatement (fail fast)
- Message clair pour debugging
- Évite appels MCP inutiles

**Priorité** : **P1** (important, effort faible)

#### S3 : Fix Issue #6 (support file_id)

**Objectif** : Permettre agent de passer file_id si déjà récupéré

**Implémentation** :

```python
class KnowledgeDBManager:
    def find_by_file_id(self, file_id: str) -> Optional[KnowledgeEntry]:
        """Trouve entrée par OpenAI file_id."""
        with self._lock_and_load() as entries:
            for entry in entries:
                if entry.openai_file_id == file_id:
                    return entry
        return None

# Dans upload_files_to_vectorstore:
input_type, validated = validate_and_classify_input(input_item)
if input_type == InputType.FILE_ID:
    entry = db_manager.find_by_file_id(validated)
elif input_type == InputType.URL:
    entry = db_manager.lookup_url(validated)
else:
    entry = db_manager.find_by_name(validated)
```

**Priorité** : **P1** (bug documenté, effort faible)

#### S4 : Retry intelligent avec hint d'erreur

**Objectif** : Récupérer des échecs `ModelBehaviorError` via retry avec contexte

**Implémentation** :

```python
async def run_with_retry(agent, input_data, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            if attempt == 0:
                result = await Runner.run(agent, input_data)
            else:
                retry_prompt = f"""Your previous attempt failed:
Error: {last_error}

Please fix:
- Ensure JSON is properly closed (quotes, brackets, braces)
- Stay within output limits
- Follow the exact schema
"""
                result = await Runner.run(agent, retry_prompt)
            return result
        except ModelBehaviorError as e:
            last_error = str(e)
            if attempt == max_retries:
                raise
    raise RuntimeError("Max retries exceeded")
```

**Avantages sur Pass@K** (écarté) :

- Payé uniquement si erreur (vs systématique)
- Utilise l'erreur Pydantic comme hint
- Plus économique en tokens et latence

**Priorité** : **P1** (impact élevé, effort moyen)

#### S5 : Writer markdown pur + post-processing

**Objectif** : Fallback si structured output échoue persistance

**Implémentation** :

```python
async def run_writer_with_fallback(search_results, research_info, metrics):
    try:
        # Essayer structured output
        result = await Runner.run(
            writer_agent,
            output_type=ReportData
        )
        return result
    except ModelBehaviorError as e:
        metrics.fallback_to_markdown += 1

        # Fallback: markdown pur
        result = await Runner.run(writer_agent_markdown)

        # Parser avec regex
        return parse_markdown_report(result.final_output)

def parse_markdown_report(markdown: str) -> ReportData:
    # Extract: title, summary, main report, follow-up questions
    title = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE).group(1)
    summary = re.search(r'##\s+Executive Summary\s+(.+?)(?=##|\Z)', markdown, re.DOTALL).group(1)
    # ... etc
```

**Justification** :

- LLMs excellent en markdown (format naturel)
- Regex parsing plus robuste que strict JSON
- Degré de structure suffisant pour rapport final

**Priorité** : **P2** (fallback robustesse, après S4)

#### S6 : Save programmatique (pas tool calling)

**Objectif** : Éviter Issue "save_final_report non appelé"

**Implémentation** :

```python
# Dans agentic_manager.py
report_data = await run_writer_with_fallback(...)

# Save programmatique (déterministe)
report_path = save_report_programmatically(
    report_data=report_data,
    output_dir=research_info.output_dir
)
logger.info(f"Report saved: {report_path}")
```

**Référence** : Document Deep Research, slide 13

> "Enforce Function Call - Key functions explicitly called to ensure structured progression"

**Approche "code execution MCP"** (Anthropic blog) :

- Au lieu de demander au LLM d'appeler tool `save_file`
- LLM génère le contenu, orchestrateur appelle save

**Priorité** : **P2** (amélioration fiabilité, effort faible)

#### S7 : Context trimming (call_model_input_filter)

**Objectif** : Réduire pression contextuelle (H3)

**Implémentation** :

```python
def trim_old_messages(data: CallModelData, keep_last: int = 10) -> ModelInputData:
    """Garde system message + N derniers messages."""
    messages = data.model_data.input

    system_msgs = [m for m in messages if m.get("role") == "system"]
    recent_msgs = [m for m in messages if m.get("role") != "system"][-keep_last:]

    return ModelInputData(
        input=system_msgs + recent_msgs,
        instructions=data.model_data.instructions
    )

# Usage:
result = await Runner.run(
    agent,
    input_data,
    run_config=RunConfig(
        call_model_input_filter=trim_old_messages
    )
)
```

**Priorité** : **P2** (amélioration qualité, après S1)

### 4.2. Solutions écartées (avec justifications)

#### E1 : Pass@K systématique (K=2 ou 3)

**Principe** : Générer K candidats, prendre le premier valide

**Raison écart** :

- **Coût prohibitif** : 2x ou 3x tokens + latence
- Payé même si première tentative OK
- Pas adapté aux ressources limitées DGX Spark

**Alternative retenue** : Retry intelligent avec hint (S4) - payé uniquement si erreur

**Réévaluation** : Possible en phase évaluation pour mesurer Valid@K

#### E2 : Modification prompts spécifiques par modèle

**Principe** : Adapter prompts pour gpt-oss-20b vs Ministral vs autres

**Raison écart** :

- **Perte d'agnosticité** : objectif = prompts universels
- Difficulté maintenance (N modèles → N prompts)
- Contradictoire avec phase évaluation (comparer modèles équitablement)

**Alternative retenue** : Améliorer prompts génériques + fallbacks robustes

#### E3 : Grammars llama.cpp (guided decoding)

**Principe** : Forcer structure JSON via grammar constraints

**Raison écart** :

- **Faisabilité inconnue** : pas testé sur DGX Spark
- Nécessite recompilation llama.cpp avec grammars support
- Overhead d'implémentation incertain

**Statut** : **Remis à plus tard** (long-term solution, section 5)

**Conditions réévaluation** :

- Si S1-S7 ne suffisent pas
- Après validation que grammars supportées par version llama.cpp actuelle

#### E4 : Changement moteur d'inférence (vllm)

**Principe** : Remplacer llama.cpp par vllm (guided decoding natif)

**Raison écart** :

- **Effort élevé** : refonte complète infrastructure
- Incertitude compatibilité DGX Spark
- Pas de garantie que ça résout les problèmes

**Statut** : **Remis à plus tard** (long-term solution)

**Conditions réévaluation** :

- Si llama.cpp montre limites structurelles
- Phase benchmark moteurs d'inférence dédiée

#### E5 : Long-running framework (Restate/Temporal)

**Principe** : Durabilité, reprise sur erreur, human-in-the-loop

**Raison écart** :

- **Hors scope itération** : focus fiabilisation basique d'abord
- Complexité infra élevée
- Dépendances externes (contradictoire avec AgentOS local pour Restate potentiellement)

**Statut** : **Remis à plus tard** (phase suivante)

**Conditions réévaluation** :

- Après système stable (S1-S7 implémentées)
- Besoin human-in-the-loop identifié
- Préférence Restate (mono-host) vs Temporal (distributed)

### 4.3. Solutions long-term (post-itération)

#### LT1 : Context compaction avec LLM

**Principe** : Résumer search results avant writer agent

**Implémentation** :

```python
class ContextCompactor:
    async def compact_search_results(self, results: list[str]) -> str:
        """Résume N résultats en synthèse compacte."""
        all_content = [Path(f).read_text() for f in results]

        prompt = f"""Synthesize these {len(results)} search results.
Keep only essential facts. Max 500 words.
{chr(10).join(all_content)}
"""
        summary = await Runner.run(summarizer_agent, prompt)
        return summary
```

**Référence** : Document Deep Research, slide 13

> "MCP Filesystem - Caches intermediate results, reducing context size"

**Priorité LT** : **Haute** (amélioration qualité significative)

#### LT2 : Sessions persistantes SQLite

**Principe** : Agents SDK SQLiteSession pour gérer historique intelligent

**Implémentation** :

```python
from agents import SQLiteSession

session = SQLiteSession(
    session_id=f"research_{vector_store_name}",
    db_path="data/sessions.db"
)

result = await Runner.run(
    agent,
    input_data,
    session=session  # Context auto-géré
)
```

**Avantages** :

- Reprise workflow après crash
- Historique persisté entre runs
- Memory management automatique

**Priorité LT** : **Moyenne** (nice-to-have, complexité modérée)

#### LT3 : Grammars llama.cpp + guided decoding

**Principe** : Forcer JSON valide via grammar constraints

**Avantages** :

- Garantit structured output valide
- Pas de post-parsing nécessaire
- Performance native

**Conditions** :

- Valider support dans llama.cpp version actuelle
- Tester overhead performance
- Implémenter grammars pour schémas Pydantic

**Priorité LT** : **Haute** (si S5 markdown fallback insuffisant)

#### LT4 : Evaluator agent (pre/post execution)

**Principe** : Agent dédié qui valide inputs/outputs

**Référence** : Document Deep Research, slide 21 "What's Next"

> "Evaluator Agent (Pre & post execution review)"

**Implémentation** :

```python
# Pre-execution
validated_plan = await evaluator_agent.validate_plan(search_plan)

# Post-execution
quality_score = await evaluator_agent.evaluate_report(report_data)
```

**Priorité LT** : **Moyenne-Haute** (amélioration qualité, effort moyen)

---

## 5. Infrastructure de mesure (TDD + Métriques)

### 5.1. Principe : Test-Driven Reliability

**Objectif** : Mesurer les régressions à chaque changement

**Approche** :

1. **Reproduire bugs** avec tests unitaires
2. **Implémenter solutions** S1-S7
3. **Valider amélioration** via tests
4. **Mesurer métriques** de fiabilité

### 5.2. Tests de reproduction

```python
# tests/test_reliability/test_structured_output_failures.py

def test_writer_json_truncation_issue_46():
    """Reproduit Issue #46: JSON tronqué à 6.6KB."""
    # Mock gpt-oss-20b avec n_ctx=2048, n_predict=512
    # Générer rapport long
    # Assert: ModelBehaviorError levée
    # Assert: Erreur contient "EOF while parsing"

def test_writer_url_corruption_issue_47():
    """Reproduit Issue #47: URLs avec Unicode corrompu."""
    # Mock agent qui génère URLs avec "…"
    # Assert: ValidationError levée
    # Assert: URL rejetée avant appel MCP

def test_upload_file_id_issue_6():
    """Reproduit Issue #6: file_id au lieu de filename."""
    # Mock agent passe "file-xxx"
    # Assert: ValueError levée (avant fix)
    # Assert: Lookup réussit (après fix S3)
```

### 5.3. Métriques de fiabilité

```python
@dataclass
class WorkflowMetrics:
    """Métriques collectées par run."""

    # Erreurs
    model_behavior_errors: int = 0
    validation_errors: int = 0
    tool_call_errors: int = 0

    # Récupération
    retry_count: int = 0
    fallback_to_reasoning: int = 0
    fallback_to_markdown: int = 0

    # Performance
    total_tokens: int = 0
    execution_time_seconds: float = 0

    # Qualité
    output_valid: bool = False
    report_length_chars: int = 0

    # KPIs
    def success_rate(self) -> float:
        """Succès première tentative."""
        return 1.0 if self.output_valid and self.retry_count == 0 else 0.0

    def robustness_score(self) -> float:
        """Succès final (avec fallbacks)."""
        return 1.0 if self.output_valid else 0.0
```

### 5.4. Évaluation comparative

```python
# scripts/run_reliability_benchmark.py

async def benchmark_reliability(test_queries: list[str]) -> pd.DataFrame:
    """Compare métriques avant/après changements."""

    results = []
    for query in test_queries:
        manager = AgenticResearchManager()

        try:
            report = await manager.run(query, research_info)
            metrics = {
                "query": query,
                "success": True,
                "retries": manager.metrics.retry_count,
                "fallbacks": manager.metrics.fallback_to_markdown,
                "errors": manager.metrics.model_behavior_errors,
                "tokens": manager.metrics.total_tokens,
                "time_s": manager.metrics.execution_time_seconds
            }
        except Exception as e:
            metrics = {"query": query, "success": False, "error": str(e)}

        results.append(metrics)

    df = pd.DataFrame(results)

    # Stats
    stats = {
        "success_rate": df["success"].mean(),
        "avg_retries": df["retries"].mean(),
        "avg_tokens": df["tokens"].mean(),
        "avg_time_s": df["time_s"].mean()
    }

    return df, stats
```

**Validation** :

- Baseline (avant S1-S7) : collecter métriques
- Après chaque solution (S1, S2, etc.) : re-collecter
- Comparer : success_rate, avg_retries, avg_errors
- **Critère succès** : success_rate > 80%, avg_retries < 1

---

## 6. Plan d'implémentation détaillé

### Phase 0 : Infrastructure TDD (1-2 jours)

**Objectif** : Capacité à mesurer avant/après

**Tâches** :

1. Créer `tests/test_reliability/` directory
2. Implémenter tests reproduction (Issue #46, #47, #6)
3. Implémenter `WorkflowMetrics` dataclass
4. Instrumenter `AgenticResearchManager` avec metrics
5. Créer script `run_reliability_benchmark.py`
6. Collecter **baseline** : 5-10 queries test

- Exemple : "Smoke test dgx", "AI engineer fundamentals", "RAG"

**Validation** :

```bash
pytest tests/test_reliability/ -v
# Expected: Tests FAIL (bugs pas encore fixés)

python scripts/run_reliability_benchmark.py
# Expected: baseline metrics saved to output/baseline.csv
```

**Livrables** :

- Suite de tests (rouge)
- Métriques baseline
- Infrastructure de mesure opérationnelle

---

### Phase 1 : Configuration llama.cpp (0.5-1 jour)

**Objectif** : Éliminer H1 (configuration sous-optimale)

**Tâches** :

1. **Modifier `docker-compose.dgx.yml**`

Ajouter paramètres :

```yaml
llm-instruct:
  command:
    - "-n"
    - "${LLM_INSTRUCT_N_CTX:-8192}" # 2048 → 8192
    - "--n-predict"
    - "${LLM_INSTRUCT_N_PREDICT:-4096}" # NEW
    - "--n-batch"
    - "${LLM_INSTRUCT_N_BATCH:-512}" # NEW
    - "--n-gpu-layers"
    - "${LLM_INSTRUCT_N_GPU_LAYERS:-70}"

llm-reasoning:
  command:
    - "-n"
    - "${LLM_REASONING_N_CTX:-8192}" # 2048 → 8192
    - "--n-predict"
    - "${LLM_REASONING_N_PREDICT:-4096}" # NEW
    - "--n-batch"
    - "${LLM_REASONING_N_BATCH:-512}" # NEW
    - "--n-gpu-layers"
    - "${LLM_REASONING_N_GPU_LAYERS:-999}"
```

1. **Créer `models.env` overrides**

Ajouter variables :

```bash
# Context windows
LLM_INSTRUCT_N_CTX=8192
LLM_REASONING_N_CTX=8192

# Output limits
LLM_INSTRUCT_N_PREDICT=4096
LLM_REASONING_N_PREDICT=4096

# Batch sizes
LLM_INSTRUCT_N_BATCH=512
LLM_REASONING_N_BATCH=512
```

1. **Tester VRAM usage**

```bash
# Rebuild et restart
docker-compose -f docker-compose.dgx.yml build
docker-compose -f docker-compose.dgx.yml up -d

# Monitor GPU
nvidia-smi --query-gpu=memory.used --format=csv -l 1

# Test génération longue
curl -X POST http://llm-instruct:8002/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Write a 2000-word essay on AI"}], "max_tokens": 4096}'
```

**Si OOM** : Réduire progressivement

- n_ctx: 8192 → 6144 → 4096
- n_predict: 4096 → 3072 → 2048
- n_gpu_layers: 70 → 50 → 30

1. **Re-exécuter benchmark**

```bash
python scripts/run_reliability_benchmark.py --output phase1.csv
# Compare avec baseline.csv
```

**Critère succès Phase 1** :

- ✅ Tests Issue #46 passent (JSON complet généré)
- ✅ `model_behavior_errors` ↓ de 50%+ vs baseline
- ✅ Pas de OOM GPU

**Si échec** : Ajuster config, itérer

---

### Phase 2 : Validations + Fix bugs (1-2 jours)

**Objectif** : Solutions S2, S3, S4

#### Tâche 2.1 : Validations préventives (S2)

**Fichiers** :

- `src/dataprep/input_validation.py` (nouveau)

**Implémentation** :

```python
class InputType(Enum):
    FILE_ID = "file_id"
    URL = "url"
    FILENAME = "filename"

def validate_and_classify_input(input_item: str) -> tuple[InputType, str]:
    # Détecter file_id
    if input_item.startswith("file-"):
        if not re.match(r"^file-[A-Za-z0-9]+$", input_item):
            raise ValidationError(f"Malformed file_id: {input_item}")
        return (InputType.FILE_ID, input_item)

    # Détecter URL corrompue
    elif input_item.startswith(("http://", "https://")):
        if "…" in input_item or "\u2026" in input_item or "?"*3 in input_item:
            raise ValidationError(f"Corrupted URL: {input_item}")

        parsed = urlparse(input_item)
        if not parsed.netloc:
            raise ValidationError(f"Invalid URL: {input_item}")

        return (InputType.URL, input_item)

    # Filename
    else:
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", input_item):
            raise ValidationError(f"Invalid filename: {input_item}")

        return (InputType.FILENAME, input_item)
```

**Tests** :

```python
# tests/test_input_validation.py

def test_validate_file_id():
    type_, val = validate_and_classify_input("file-abc123")
    assert type_ == InputType.FILE_ID
    assert val == "file-abc123"

def test_validate_corrupted_url():
    with pytest.raises(ValidationError, match="Corrupted URL"):
        validate_and_classify_input("https://example.com/…test")

def test_validate_invalid_filename():
    with pytest.raises(ValidationError, match="Invalid filename"):
        validate_and_classify_input("file with spaces.txt")
```

#### Tâche 2.2 : Fix Issue #6 (S3)

**Fichiers** :

- `src/dataprep/knowledge_db.py` (modifier)
- `src/dataprep/mcp_functions.py` (modifier)

**Implémentation** :

```python
# knowledge_db.py
class KnowledgeDBManager:
    def find_by_file_id(self, file_id: str) -> Optional[KnowledgeEntry]:
        """Trouve entrée par OpenAI file_id."""
        with self._lock_and_load() as entries:
            for entry in entries:
                if entry.openai_file_id == file_id:
                    return entry
        return None

# mcp_functions.py
async def upload_files_to_vectorstore(inputs, vectorstore_name):
    entries_to_upload = []

    for input_item in inputs:
        # Validation + classification
        input_type, validated = validate_and_classify_input(input_item)

        # Lookup selon type
        if input_type == InputType.FILE_ID:
            entry = db_manager.find_by_file_id(validated)
        elif input_type == InputType.URL:
            entry = db_manager.lookup_url(validated)
        else:
            entry = db_manager.find_by_name(validated)

        if not entry:
            raise ValueError(f"Not found ({input_type.value}): {validated}")

        entries_to_upload.append(entry)

    # ... upload logic
```

**Tests** :

```python
def test_upload_with_file_id():
    # Setup: knowledge_db avec entry ayant openai_file_id="file-test123"
    result = upload_files_to_vectorstore(
        inputs=["file-test123"],
        vectorstore_name="test"
    )
    assert result.success
```

#### Tâche 2.3 : Retry intelligent (S4)

**Fichiers** :

- `src/agents/retry_handler.py` (nouveau)
- `src/agentic_manager.py` (intégrer)

**Implémentation** :

```python
# retry_handler.py
class RetryHandler:
    def __init__(self, metrics: WorkflowMetrics):
        self.metrics = metrics

    async def run_with_retry(
        self,
        agent: Agent,
        input_data: str,
        max_retries: int = 2
    ):
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                if attempt == 0:
                    result = await Runner.run(agent, input_data)
                else:
                    retry_prompt = f"""Previous attempt failed with error:

{last_error}

Please fix and retry. Focus on:
- Proper JSON closing (quotes, brackets, braces)
- Staying within output limits
- Following exact schema
"""
                    result = await Runner.run(agent, retry_prompt)

                # Succès
                self.metrics.retry_count = attempt
                return result

            except ModelBehaviorError as e:
                last_error = str(e)
                self.metrics.model_behavior_errors += 1

                if attempt == max_retries:
                    raise

                logger.warning(f"Retry {attempt+1}/{max_retries}: {e}")

        raise RuntimeError("Max retries exceeded")

# agentic_manager.py
async def _run_writer(self, search_results, research_info):
    retry_handler = RetryHandler(self.metrics)

    result = await retry_handler.run_with_retry(
        agent=writer_agent,
        input_data=prepare_writer_input(search_results),
        max_retries=2
    )

    return result
```

**Tests** :

```python
def test_retry_success_second_attempt(mocker):
    # Mock: première tentative fail, deuxième OK
    mock_run = mocker.patch("agents.Runner.run")
    mock_run.side_effect = [
        ModelBehaviorError("JSON invalid"),
        ReportData(...)  # Success
    ]

    result = await retry_handler.run_with_retry(agent, input_data)

    assert result is not None
    assert metrics.retry_count == 1
    assert metrics.model_behavior_errors == 1
```

**Validation Phase 2** :

```bash
pytest tests/test_reliability/ -v
# Expected: Issue #6 test PASS, Issue #46 improved

python scripts/run_reliability_benchmark.py --output phase2.csv
```

**Critère succès Phase 2** :

- ✅ Tests Issue #6, #47 passent
- ✅ `validation_errors` détectées tôt
- ✅ `retry_count` > 0 mais `output_valid` = True
- ✅ `model_behavior_errors` ↓ 20%+ vs Phase 1

---

### Phase 3 : Fallbacks robustes (1-2 jours)

**Objectif** : Solutions S5, S6

#### Tâche 3.1 : Writer markdown fallback (S5)

**Fichiers** :

- `src/agents/prompts/file_writer_agent_markdown.md` (nouveau)
- `src/agents/writer_fallback.py` (nouveau)
- `src/agentic_manager.py` (intégrer)

**Prompt markdown** :

```markdown
# file_writer_agent_markdown.md

You are a research writer agent.

Generate a comprehensive research report in **markdown format only**.

Required structure:

# [Report Title]

## Executive Summary

[2-3 concise sentences summarizing key findings]

## Main Report

[Full detailed content with sections, subsections as needed]

## Key Findings

- Finding 1
- Finding 2
- Finding 3

## Follow-up Questions

- Question 1?
- Question 2?
- Question 3?

CRITICAL:

- Generate ONLY markdown, no JSON
- Do NOT call any tools
- Report will be saved automatically
```

**Parser** :

```python
# writer_fallback.py
def parse_markdown_report(markdown: str) -> ReportData:
    """Parse markdown vers structured ReportData."""

    # Titre
    title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
    title = title_match.group(1) if title_match else "Untitled"

    # Summary
    summary_match = re.search(
        r'##\s+Executive Summary\s+(.+?)(?=##|\Z)',
        markdown,
        re.DOTALL
    )
    summary = summary_match.group(1).strip() if summary_match else ""

    # Follow-up questions
    questions_match = re.search(
        r'##\s+Follow-up Questions\s+(.+?)(?=##|\Z)',
        markdown,
        re.DOTALL
    )
    questions_text = questions_match.group(1).strip() if questions_match else ""
    questions = [
        q.strip().lstrip('-').strip()
        for q in questions_text.split('\n')
        if q.strip() and q.strip().startswith('-')
    ]

    return ReportData(
        file_name=slugify(title),
        research_topic=title,
        markdown_report=markdown,
        short_summary=summary,
        follow_up_questions=questions
    )


async def run_writer_with_markdown_fallback(
    search_results,
    research_info,
    metrics,
    retry_handler
):
    """Writer avec fallback markdown."""

    try:
        # Essayer structured output (avec retry)
        result = await retry_handler.run_with_retry(
            agent=writer_agent,
            input_data=prepare_input(search_results),
            max_retries=2
        )
        return result

    except ModelBehaviorError as e:
        logger.warning(f"Structured output failed after retries, fallback markdown: {e}")
        metrics.fallback_to_markdown += 1

        # Fallback: markdown pur
        result = await Runner.run(
            writer_agent_markdown,
            prepare_input(search_results)
        )

        # Parser
        report_data = parse_markdown_report(result.final_output)

        return report_data
```

**Tests** :

```python
def test_parse_markdown_report():
    markdown = """
# AI Research Report

## Executive Summary
This report covers AI fundamentals.

## Main Report
[Content here]

## Follow-up Questions
- What is next?
- How to scale?
"""

    report = parse_markdown_report(markdown)

    assert report.research_topic == "AI Research Report"
    assert "AI fundamentals" in report.short_summary
    assert len(report.follow_up_questions) == 2

def test_markdown_fallback_triggered(mocker):
    # Mock structured output échoue
    mock_structured = mocker.patch("Runner.run")
    mock_structured.side_effect = ModelBehaviorError("JSON invalid")

    # Mock markdown réussit
    mock_markdown = mocker.patch("Runner.run")
    mock_markdown.return_value = MagicMock(final_output="# Report\n...")

    result = await run_writer_with_markdown_fallback(...)

    assert metrics.fallback_to_markdown == 1
    assert result.markdown_report is not None
```

#### Tâche 3.2 : Save programmatique (S6)

**Fichiers** :

- `src/agents/report_saver.py` (nouveau)
- `src/agentic_manager.py` (intégrer)

**Implémentation** :

```python
# report_saver.py
def save_report_programmatically(
    report_data: ReportData,
    output_dir: str
) -> Path:
    """Sauvegarde rapport sans tool calling."""

    output_path = Path(output_dir) / f"{report_data.file_name}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Rapport markdown
    output_path.write_text(
        report_data.markdown_report,
        encoding="utf-8"
    )

    # Metadata JSON
    metadata = {
        "title": report_data.research_topic,
        "summary": report_data.short_summary,
        "follow_up_questions": report_data.follow_up_questions,
        "generated_at": datetime.now().isoformat(),
        "file_name": report_data.file_name
    }

    metadata_path = output_path.with_suffix('.json')
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8"
    )

    logger.info(f"Report saved: {output_path}")
    logger.info(f"Metadata saved: {metadata_path}")

    return output_path

# agentic_manager.py
async def _agentic_research(self, query, research_info):
    # ... recherche, planification ...

    # Writer (avec fallback)
    report_data = await run_writer_with_markdown_fallback(
        search_results=research_info.search_results,
        research_info=research_info,
        metrics=self.metrics,
        retry_handler=RetryHandler(self.metrics)
    )

    # Save programmatique (déterministe)
    report_path = save_report_programmatically(
        report_data=report_data,
        output_dir=research_info.output_dir
    )

    return report_data
```

**Tests** :

```python
def test_save_report_programmatically(tmp_path):
    report_data = ReportData(
        file_name="test_report",
        research_topic="Test",
        markdown_report="# Test Report\nContent",
        short_summary="Summary",
        follow_up_questions=["Q1?", "Q2?"]
    )

    report_path = save_report_programmatically(report_data, str(tmp_path))

    assert report_path.exists()
    assert report_path.read_text() == "# Test Report\nContent"

    metadata_path = report_path.with_suffix('.json')
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["title"] == "Test"
```

**Validation Phase 3** :

```bash
pytest tests/test_reliability/ -v

python scripts/run_reliability_benchmark.py --output phase3.csv
```

**Critère succès Phase 3** :

- ✅ Fallback markdown fonctionne (parsing correct)
- ✅ Rapport sauvegardé même si structured output échoue
- ✅ `robustness_score` > 90% (succès final avec fallbacks)
- ✅ `fallback_to_markdown` < 30% des runs

---

### Phase 4 : Context engineering (1 jour)

**Objectif** : Solution S7

#### Tâche 4.1 : Context trimming

**Fichiers** :

- `src/agents/context_management.py` (nouveau)
- `src/agentic_manager.py` (intégrer)

**Implémentation** :

```python
# context_management.py
def trim_old_messages(
    data: CallModelData,
    keep_last: int = 10
) -> ModelInputData:
    """Garde system + N derniers messages."""

    messages = data.model_data.input

    # Séparer system vs autres
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    # Garder N derniers
    trimmed_others = other_msgs[-keep_last:] if len(other_msgs) > keep_last else other_msgs

    trimmed_messages = system_msgs + trimmed_others

    logger.debug(f"Trimmed context: {len(messages)} → {len(trimmed_messages)} messages")

    return ModelInputData(
        input=trimmed_messages,
        instructions=data.model_data.instructions
    )

# agentic_manager.py
async def _run_with_context_management(self, agent, input_data):
    result = await Runner.run(
        agent,
        input_data,
        run_config=RunConfig(
            call_model_input_filter=lambda data: trim_old_messages(data, keep_last=10)
        )
    )
    return result
```

**Tests** :

```python
def test_trim_old_messages():
    # Setup: 20 messages (1 system + 19 user/assistant)
    messages = [{"role": "system", "content": "System"}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Msg {i}"}
        for i in range(19)
    ]

    data = CallModelData(
        model_data=ModelInputData(input=messages, instructions="")
    )

    result = trim_old_messages(data, keep_last=10)

    # 1 system + 10 derniers = 11 total
    assert len(result.input) == 11
    assert result.input[0]["role"] == "system"
    assert result.input[-1]["content"] == "Msg 18"
```

**Validation Phase 4** :

```bash
pytest tests/test_context_management.py -v

python scripts/run_reliability_benchmark.py --output phase4.csv
```

**Critère succès Phase 4** :

- ✅ Context réduit sans perte info critique
- ✅ Qualité rapport maintenue ou améliorée
- ✅ `total_tokens` ↓ 15-30% vs Phase 3

---

### Phase 5 : Évaluation finale (0.5 jour)

**Objectif** : Valider gains cumulés

#### Tâche 5.1 : Benchmark complet

**Corpus test** :

```python
TEST_QUERIES = [
    "Smoke test: dgx docker stack",
    "AI engineer foundational concepts and principles",
    "Retrieval Augmented Generation techniques",
    "Multi-agent orchestration with LangGraph",
    "Vector databases comparison (ChromaDB, Pinecone, Weaviate)"
]
```

**Exécution** :

```bash
python scripts/run_reliability_benchmark.py \
  --queries test_queries.txt \
  --runs 3 \
  --output final_evaluation.csv
```

**Analyse** :

```python
# scripts/analyze_results.py
import pandas as pd

baseline = pd.read_csv("output/baseline.csv")
final = pd.read_csv("output/final_evaluation.csv")

comparison = pd.DataFrame({
    "metric": ["success_rate", "avg_retries", "avg_errors", "avg_tokens"],
    "baseline": [
        baseline["success"].mean(),
        baseline["retries"].mean(),
        baseline["errors"].mean(),
        baseline["tokens"].mean()
    ],
    "final": [
        final["success"].mean(),
        final["retries"].mean(),
        final["errors"].mean(),
        final["tokens"].mean()
    ]
})

comparison["improvement_%"] = (
    (comparison["final"] - comparison["baseline"]) / comparison["baseline"] * 100
)

print(comparison)
```

**Rapport final** :

```markdown
# Rapport d'évaluation - Robustification DGX Spark

## Résumé

| Métrique         | Baseline | Phase 5 | Amélioration     |
| ---------------- | -------- | ------- | ---------------- |
| Success Rate     | 35%      | 85%     | +143%            |
| Avg Retries      | 0.2      | 0.8     | +300% (expected) |
| Avg Errors       | 2.1      | 0.3     | -86%             |
| Avg Tokens       | 15,000   | 12,000  | -20%             |
| Robustness Score | 40%      | 92%     | +130%            |

## Gains par phase

- **Phase 1** (llama.cpp config): -50% errors
- **Phase 2** (validations + retry): -20% errors
- **Phase 3** (markdown fallback): +50% robustness
- **Phase 4** (context trim): -20% tokens

## Issues résolues

- ✅ Issue #46: JSON truncation (config n_predict)
- ✅ Issue #47: URLs corrompues (validation preventive)
- ✅ Issue #6: file_id support (lookup added)
- ✅ Save report fiable (programmatic save)

## Recommandations

- Garder retry max=2 (balance coût/robustesse)
- Monitorer fallback_to_markdown (si >40%, investiguer)
- Évaluer long-term solutions (context compaction, grammars)
```

#### Tâche 5.2 : Documentation

**Fichiers à créer** :

- `docs/ROBUSTNESS_IMPROVEMENTS.md` : Ce document
- `docs/METRICS_GUIDE.md` : Guide métriques
- `CHANGELOG.md` : Historique changements

**Critère succès final** :

- ✅ `success_rate` > 80%
- ✅ `robustness_score` > 90%
- ✅ `avg_errors` < 0.5 par run
- ✅ Tous tests passent

---

## 7. Risques et mitigations

### R1 : OOM GPU avec n_ctx=8192

**Probabilité** : Moyenne (40%)  
**Impact** : Bloquant

**Mitigation** :

- Tester progressivement (4096 → 6144 → 8192)
- Monitorer VRAM avec nvidia-smi
- Fallback: réduire n_gpu_layers si nécessaire
- Alternative: n_ctx=6144 (compromis)

### R2 : Markdown fallback dégrade qualité

**Probabilité** : Faible (20%)  
**Impact** : Moyen

**Mitigation** :

- Parser markdown robuste avec tests complets
- Validation schema après parsing
- Logs détaillés pour debugging
- Option: forcer structured output pour certains modèles (Ministral)

### R3 : Context trimming perd info critique

**Probabilité** : Faible-Moyenne (30%)  
**Impact** : Moyen

**Mitigation** :

- Paramètre `keep_last` tunable (default 10)
- Garder TOUS les system messages
- Tests qualité avant/après trimming
- Alternative: context compaction (LT1) au lieu de trimming

### R4 : Retry augmente latence significativement

**Probabilité** : Moyenne (50%)  
**Impact** : Faible

**Mitigation** :

- Limiter max_retries=2 (éviter retry loops)
- Monitorer `execution_time_seconds`
- Si >50% queries retry → investiguer cause racine
- Alternative: augmenter n_predict si retries fréquents

### R5 : gpt-oss-20b reste instable malgré fixes

**Probabilité** : Moyenne-Élevée (60%)  
**Impact** : Élevé

**Mitigation** :

- **Plan B** : Tester modèles alternatifs
  - Qwen3-Next-30B (MoE, mais 30B total)
  - gpt-oss-120b (si RAM suffit)
  - Ministral-3-14B en Q8 (plus stable que mxfp4)
- Documenter "modèles supportés" vs "modèles expérimentaux"
- Phase benchmark modèles dédiée (post-robustification)

---

## 8. Agenda et timeline

### Vue d'ensemble

| Phase     | Durée      | Dépendances | Validation             |
| --------- | ---------- | ----------- | ---------------------- |
| Phase 0   | 1-2j       | -           | Tests rouge + baseline |
| Phase 1   | 0.5-1j     | Phase 0     | Errors ↓ 50%           |
| Phase 2   | 1-2j       | Phase 1     | Issues #6,#47 fixées   |
| Phase 3   | 1-2j       | Phase 2     | Robustness >90%        |
| Phase 4   | 1j         | Phase 3     | Tokens ↓ 20%           |
| Phase 5   | 0.5j       | Phase 4     | Success >80%           |
| **Total** | **5-8.5j** |             | **Système fiabilisé**  |

### Jalons clés

**J1-J2** : Infrastructure TDD opérationnelle

- Tests reproduction bugs
- Métriques baseline
- Scripts benchmark

**J3** : Configuration llama.cpp validée

- n_ctx, n_predict, n_batch optimisés
- Pas d'OOM GPU
- Amélioration 50% errors

**J4-J5** : Validations + retry déployés

- Input validation active
- file_id support
- Retry intelligent

**J6-J7** : Fallbacks robustes

- Markdown fallback opérationnel
- Save programmatique
- Robustness >90%

**J8** : Context engineering

- Trimming actif
- Tokens optimisés

**J9** : Validation finale

- Benchmark complet
- Documentation
- Go/NoGo phase évaluation

---

## 9. Critères de succès

### Succès minimal (Go phase évaluation)

- ✅ Success rate > 75%
- ✅ Robustness score > 85%
- ✅ Model behavior errors < 1 par run
- ✅ Issues #46, #47, #6 résolues
- ✅ Tous tests passent

### Succès optimal

- ✅ Success rate > 85%
- ✅ Robustness score > 95%
- ✅ Avg retries < 0.5
- ✅ Fallback markdown < 20% runs
- ✅ Tokens ↓ 25% vs baseline

### Succès exceptionnel

- ✅ Success rate > 90%
- ✅ Zero ModelBehaviorError sans fallback
- ✅ Qualité rapports = cloud baseline
- ✅ Latence < 2x cloud

---

## 10. Références

### Documents internes

1. **Deep Research - How to Build a Multi-Agent Research Workflow That Actually Works** (PDF)

- Slides 9-12: Problèmes architecture agentic (cost, quality, reliability)
- Slide 13: Solutions (MCP filesystem, enforce function calls, evaluation)
- Slides 17-19: Architecture DeepResearch (orchestration déterministe)
- Slide 21: Roadmap (short/long memory, evaluator agent)

1. **AGENTS.md** - Repository guidelines

- Architecture multi-agent (supervisor, handoffs)
- OpenAI Agents SDK best practices
- MCP DataPrep architecture

1. **CLAUDE.md** - Cursor AI agent context

- Model compatibility (tool filtering)
- Tracing and observability
- Agent handoffs and context

### Articles externes

1. **Anthropic - Code execution with MCP** (Nov 2025)

- [https://www.anthropic.com/engineering/code-execution-with-mcp](https://www.anthropic.com/engineering/code-execution-with-mcp)
- "Agents scale better by writing code to call tools instead"
- Pattern: enforce function calls programmatically

1. **OpenAI Agents SDK - Running agents documentation**

- [https://openai.github.io/openai-agents-python/running_agents/](https://openai.github.io/openai-agents-python/running_agents/)
- Long running agents & human-in-the-loop
- Restate and Temporal integrations

1. **llama.cpp documentation**

- Context window (`-n`, `--n-ctx`)
- Output limits (`--n-predict`)
- Batch processing (`--n-batch`)
- GPU layers (`--n-gpu-layers`)

### Issues GitHub référencées

1. **Issue #46** : gpt-oss-20b renvoie du JSON invalide (structured output)
2. **Issue #47** : gpt-oss-20b génère des URLs corrompues/non-syllabus
3. **Issue #6** : upload_files_to_vectorstore fails when agent passes OpenAI file_id
4. **Issue #7** : Max turns exceeded - writer_agent stuck in file path loop

### Standards et frameworks

1. **Model Context Protocol (MCP)** - Model Context Protocol specification
2. **OpenAI Agents SDK** - Multi-agent orchestration framework
3. **Pydantic** - Data validation using Python type annotations
4. **ChromaDB** - Open-source embedding database

---

## Annexes

### Annexe A : Configuration llama.cpp détaillée

**Paramètres critiques** :

| Paramètre        | Description                  | Default | Recommandé DGX                 |
| ---------------- | ---------------------------- | ------- | ------------------------------ |
| `-n`, `--n-ctx`  | Context window (tokens)      | 2048    | 8192                           |
| `--n-predict`    | Max output tokens            | 128-512 | 4096                           |
| `--n-batch`      | Batch size prompt processing | 512     | 512                            |
| `--n-gpu-layers` | Layers on GPU                | 0       | 70 (instruct), 999 (reasoning) |
| `-ngl`           | Alias for n-gpu-layers       | -       | -                              |

**Calcul VRAM approximatif** :

```
VRAM ≈ (model_size_GB + context_size_MB + kv_cache_MB)

gpt-oss-20b-mxfp4:
- Model: ~10GB (mxfp4 quantization)
- Context (8192): ~512MB
- KV cache: ~1GB
Total: ~11.5GB

Ministral-3-14B-Q8_0:
- Model: ~14GB (Q8 quantization)
- Context (8192): ~512MB
- KV cache: ~1GB
Total: ~15.5GB
```

**DGX Spark budget** : 128GB RAM (shared CPU/GPU)

- 2 modèles simultanés : ~27GB
- Marge : ~101GB (safe)

### Annexe B : Exemples de métriques

**Baseline (avant fixes)** :

```json
{
  "query": "Smoke test: dgx docker stack",
  "success": false,
  "model_behavior_errors": 1,
  "validation_errors": 0,
  "retry_count": 0,
  "fallback_to_markdown": 0,
  "total_tokens": 14523,
  "execution_time_seconds": 87.3,
  "error": "Invalid JSON: EOF while parsing at column 6639"
}
```

**Après Phase 5 (avec fixes)** :

```json
{
  "query": "Smoke test: dgx docker stack",
  "success": true,
  "model_behavior_errors": 0,
  "validation_errors": 0,
  "retry_count": 1,
  "fallback_to_markdown": 0,
  "total_tokens": 11245,
  "execution_time_seconds": 93.7,
  "report_length_chars": 8942,
  "success_rate": 0.0,
  "robustness_score": 1.0
}
```

### Annexe C : Diagramme de flux décisionnel

```
[User Query]
     ↓
[Phase 0: Collect Metrics]
     ↓
[Phase 1: Try with n_ctx=8192, n_predict=4096]
     ↓
[ModelBehaviorError?] → Yes → [Phase 2: Retry with hint (max 2)]
     ↓ No                            ↓
[Success]                    [Still Error?] → Yes → [Phase 3: Fallback markdown]
     ↓                                                      ↓
[Phase 4: Trim context]                            [Parse markdown]
     ↓                                                      ↓
[Phase 6: Save programmatically] ← ← ← ← ← ← ← ← ← ← [Success]
     ↓
[Log Metrics]
     ↓
[Report Generated]
```

---

**Fin du document**

**Version** : 1.0  
**Dernière mise à jour** : 4 février 2026  
**Prochaine revue** : Après Phase 5 (validation finale)

**Contacts** :

- Architecture : Équipe Applied AI
- Implémentation : Équipe Deep Research
- Validation : Solution Engineers
