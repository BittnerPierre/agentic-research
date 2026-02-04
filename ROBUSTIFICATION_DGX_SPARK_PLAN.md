# Plan de robustification du système agentic-research sur DGX Spark

**Version**: 2.0  
**Date**: 4 février 2026  
**Objectif**: Fiabiliser le workflow en 1/2 à 1 journée (UAT inclus)

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

Alternative (script Python minimal) :

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

### S4 : Retry intelligent avec hint d'erreur ⚠️ **ATTENTION CONTEXTE**

**Principe** : Si `ModelBehaviorError` → retry avec erreur Pydantic en hint.

**⚠️ Correction importante** (feedback reçu) :

Ne pas "perdre le contexte" au retry. Le retry doit :
- Garder **mêmes inputs structurants** (search results, plan, etc.)
- Ajouter **error hint** ("patch minimal")
- Ne pas créer "nouvelle question"

**Implémentation** : Encapsuler comme "same task, patch mode" dans le Runner.

**Séquence de récupération (ordre fixé)** :

Pour l'étape critique (writer JSON) :

1. **Génération initiale** (structured output)
2. **Validation** Pydantic
3. ❌ Si échec → **Retry patch-mode** (max 1) avec error hint
4. **Validation** Pydantic
5. ❌ Si échec → **Pass@K=2** (générer 2 candidats, prendre premier valide)
6. **Validation** Pydantic
7. ❌ Si échec → **Fallback markdown** (voir S5)

**Justification Pass@K conditionnel** :
- Coût acceptable car **rare + ciblé** (uniquement après échec retry)
- Uniquement sur writer JSON (étape critique)
- Alternative à l'échec total

### S5 : Markdown fallback pour writer

**Principe** : Si structured output échoue après retry, générer rapport en **markdown pur** puis parser.

**Contract of markdown output** :

```markdown
# [Titre du rapport]

## Executive Summary
[résumé en 2-3 paragraphes]

## [Sections du rapport]
...

## Follow-up Questions
1. Question 1
2. Question 2
3. Question 3
```

**Parser** (`src/agents/writer_fallback.py`) :

```python
import re
from src.agents.schemas import ReportData

def parse_markdown_report(markdown: str, research_topic: str) -> ReportData:
    """
    Parse markdown → ReportData avec validation.
    
    ⚠️ Impose titre : soit extrait du markdown, soit fallback sur research_topic.
    """
    # Extraire titre
    title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
    
    # Fallback titre si absent
    if title_match:
        title = title_match.group(1).strip()
    else:
        # Générer titre safe depuis research_topic
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

**Tests de parsing** :
- Sections manquantes
- Headings alternatifs
- Validation Pydantic post-parse

### S6 : Save programmatique (déterministe)

**Problème** : Writer agent peut skip `save_report` tool call (#7).

**Solution** : Appel programmatique après génération réussie :

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

**Intégration** : Manager appelle cette fonction directement après `writer_agent.run()` :

```python
try:
    report = writer_agent.run(...)
    filepath = save_report_programmatically(report, output_dir, timestamp)
    logger.info(f"Rapport sauvegardé: {filepath}")
except ValueError as e:
    logger.error(f"Rapport invalide mais metadata tracée: {e}")
    # Continuer ou lever selon politique
```

### S7 : Context trimming (conversations longues)

**Principe** : Réduire pression contextuelle via `call_model_input_filter` (Agents SDK).

**Périmètre d'application** :

- ✅ **Activé pour** : `writer_agent`, `planner_agent`
  - Conversations longues avec beaucoup de contexte accumulé
  - Trimming bénéfique pour la qualité (focus sur récent)
- ❌ **Désactivé pour** : `search_agent`, agents de tooling
  - Risque de perdre des références/citations critiques
  - Besoin de garder historique complet des résultats

```python
from openai.agents.filters import call_model_input_filter

def trim_old_messages(messages: list, keep_last_n: int = 10) -> list:
    """Garde system messages + N derniers messages."""
    system_msgs = [m for m in messages if m.get("role") == "system"]
    recent_msgs = [m for m in messages if m.get("role") != "system"][-keep_last_n:]
    return system_msgs + recent_msgs

# Configuration sélective par agent
writer_agent = Agent(
    model="...",
    call_model_input_filter=trim_old_messages,  # ✅ Activé
    ...
)

search_agent = Agent(
    model="...",
    # ❌ Pas de trimming (garde tout l'historique)
    ...
)
```

---

## 5. Solutions écartées (pour cette itération)

### E1 : Prompts spécifiques par modèle

**Justification** : Objectif = prompts agnostiques (cloud/local). Adaptation par modèle → Phase évaluation.

### E2 : Pass@K systématique

**Justification** : Coût élevé (double tokens, temps). **Alternative retenue** : Pass@K conditionnel (après échec retry).

### E3 : Frameworks long-running (Restate/Temporal)

**Justification** : Overhead architecture. Pas nécessaire si S1-S7 suffisent. **Reconsidération** : Si problèmes persistent après cette itération.

### E4 : Grammars llama.cpp

**Justification initiale** : Faisabilité inconnue, effort incertain.

**⚠️ Reconsidération** (feedback reçu) :
- Grammars attaquent **classe d'erreurs** (syntaxe JSON) à la source
- **Décision révisée** : Non prioritaire tant que S1 pas corrigé
- **Reconsidérer si** : Taux fallback markdown > 30% après S1-S7

### E5 : Changement moteur inférence (vllm)

**Justification** : Overhead migration. Tester llama.cpp optimisé d'abord.

---

## 6. Plan d'implémentation (1/2 à 1 journée)

### Phase 1 : Fix llama.cpp config (2-3h) ✅ **PRIORITÉ**

**Objectif** : Éliminer cause racine H1.

**Tâches** :
1. Corriger `docker-compose.dgx.yml` : `-n` → `--ctx-size`, ajouter `--n-predict`, `--batch-size`
2. Mettre à jour `models.env` avec nouvelles variables
3. Redémarrer services : `docker-compose -f docker-compose.dgx.yml up -d`
4. **Validation** : Smoke test (query → rapport complet) × 3 runs
5. Vérifier logs : pas de troncature EOF

**Critère de succès** : 3/3 runs complètent sans `ModelBehaviorError` JSON.

### Phase 2 : Quick wins défensifs (2-3h)

**Objectif** : Robustesse sur inputs fragiles + save déterministe.

**Tâches** :
1. Implémenter `validate_and_classify_input()` + tests unitaires
2. Ajouter `find_by_file_id()` dans `KnowledgeDBManager`
3. Intégrer validation dans `upload_files_to_vectorstore`
4. Implémenter `save_report_programmatically()`
5. Modifier manager pour appeler save programmatique
6. **Validation** : Tester Issue #6 (file_id), Issue #47 (URL corrompu)

**Critère de succès** : Issues #6 et #47 résolus, save déterministe fonctionne.

### Phase 3 : Fallbacks intelligents (optionnel, si temps) (2-3h)

**Objectif** : Filet de sécurité si structured output échoue encore.

**Tâches** :
1. Implémenter `parse_markdown_report()` + tests
2. Créer prompt `file_writer_agent_markdown.md`
3. Wrapper `run_writer_with_markdown_fallback()` (structured → retry → markdown)
4. Implémenter `trim_old_messages()` filter
5. Ajouter filter à agents (writer, planner)
6. **Validation** : Forcer échec structured → vérifier fallback markdown

**Critère de succès** : Fallback markdown génère rapport valide, context trimming réduit tokens.

### UAT (1-2h)

**Tests de bout en bout** (critères opérationnels) :

Exécuter **4 queries** représentatives :
1. **Query simple** (smoke test) : "Explain Retrieval Augmented Generation"
2. **Query complexe** (syllabus multi-topics) : syllabus avec 5+ sources
3. **Query URLs externes** (test Issue #47) : avec URLs non-syllabus
4. **Query file_id** (test Issue #6) : forcer usage file_id dans tools

**Critères de succès** (opérationnels, non métriques) :

✅ **Minimal** (Go/NoGo) :
- **Au moins 3/4 queries** complètent jusqu'au bout (rapport final généré)
- **Fichiers présents** : `research_report_*.md` + `metadata_*.json` pour chaque run réussi
- **Logs propres** : pas de troncature EOF, pas d'URLs corrompues (Issue #47)

✅ **Optimal** :
- **4/4 queries** complètent
- **Métadonnées `_is_valid: true`** pour tous les rapports
- **Save déterministe** : tous les rapports sauvegardés automatiquement (pas de skip)

✅ **Validation manuelle** (échantillon) :
- Lire 1 rapport : structure markdown correcte, contenu cohérent
- Vérifier metadata : `short_summary` non vide, `follow_up_questions` présentes

**Commandes de test** :

```bash
# Run UAT
for query in "query1.md" "query2.md" "query3.md" "query4.md"; do
  poetry run agentic-research --query "$query" --output-dir "uat_output/"
done

# Vérifier résultats
ls -lh uat_output/  # Doit montrer 3-4 fichiers .md + .json
grep -l "_is_valid.*true" uat_output/metadata_*.json | wc -l  # Objectif: 3-4
```

---

## 7. Décisions techniques importantes

### 7.1. Flags llama.cpp : pourquoi cette correction est critique

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

### 7.2. Retry avec contexte vs nouvelle question

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

### 7.3. Pass@K conditionnel vs systématique

**Coût Pass@K systématique** :
- Writer : 2000 tokens output × 3 candidats = 6000 tokens
- × Tous les runs → coût prohibitif

**Pass@K conditionnel** (après échec) :
- Uniquement si structured output + retry échouent
- Sur writer JSON uniquement (étape critique)
- Coût acceptable : rare + ciblé

### 7.4. Grammars llama.cpp : quand reconsidérer

**Critère de reconsidération** :
- Après Phase 1-3 implémentées
- **Si** : Taux fallback markdown > 30%
- **Action** : Test pilote grammars JSON sur writer agent

**Avantage grammars** :
- Garantie syntaxe JSON à la source (pas repair a posteriori)
- Réduit retry/fallback

**Risque** :
- Peut impacter créativité/qualité contenu
- Nécessite tuning per-model

---

## 8. Critères de succès

### Minimal (Go/NoGo itération)
- ✅ Config llama.cpp corrigée et validée (Phase 1)
- ✅ Smoke test complète 3/3 fois sans troncature EOF
- ✅ Issues #6 et #47 résolus (Phase 2)

### Optimal (objectif 1j)
- ✅ Toutes les phases (1+2+3) implémentées
- ✅ Taux de complétion ≥80% sur UAT (4 queries)
- ✅ Markdown fallback opérationnel
- ✅ Save programmatique déterministe

### Stretch (si temps)
- ✅ Context trimming activé et testé
- ✅ Pass@K conditionnel implémenté
- ✅ Documentation technique mise à jour

---

## Conclusion

Ce plan se concentre sur **l'essentiel exécutable en 1/2 à 1 journée** :

1. **Phase 1 (bloquante)** : Corriger config llama.cpp (cause racine H1)
2. **Phase 2 (robustesse)** : Validations inputs + save déterministe
3. **Phase 3 (optionnel)** : Fallbacks markdown + context trimming

**Prochaines étapes hors scope** :
- Évaluation comparative modèles (dense vs MoE, mono vs duo)
- Optimisation prompts par modèle
- Frameworks long-running (Restate/Temporal)
- Grammars llama.cpp (si fallback markdown > 30%)

**Go/NoGo** : Validation Phase 1 (smoke test 3/3) avant de continuer Phase 2-3.
