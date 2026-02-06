# Plan de robustification du système agentic-research sur DGX Spark

**Version**: 2.3.2 DRAFT  
**Date**: 6 février 2026  
**Objectif**: Fiabiliser le workflow en 1 journée (UAT inclus)

**⚠️ DRAFT v2.3.2** : Simplification YAGNI/KISS, focus tests et contrats stables.

**Amendements V2.3.2 (Simplification et tests)** :

- **Writer en markdown only** : pas de structured output pour le writer, pas de fallback qui change de format
- **S2-S6 simplifiés** : uniquement contrats stables + validation + save programmatique
- **Fallback minimal** :: vérification sortie + pas de chain/pass@k dans ce plan, options listées mais non prioritaires
- **Plan centré tests** : problème → valeur → test attendu → implémentation

**Amendements V2.3.1 (Architecture majeure)** :

- **Refonte S4-S8** : Framework fallback générique (Strategy pattern) dès S4 (pas de hard-coding)
- **Nouveau S6** : Logging et métriques pour évaluation modèles (compatible `./evaluations/`)
- **Context trimming** : Écarté de cette itération (hors scope robustification simple)
- **Phases restructurées** : Phase 2 groupée (framework + défenses + métriques, 4-5h avec TDD)
- **UAT renforcé** : Génération syllabus test bout-en-bout + extraction métriques JSON

**Amendements V2.3.0 (Architecture majeure)** :

- **Refonte S4-S8** : Framework fallback générique (Strategy pattern) dès S4 (pas de hard-coding)
- **Nouveau S6** : Logging et métriques pour évaluation modèles (compatible `./evaluations/`)
- **Context trimming** : Écarté de cette itération (hors scope robustification simple)
- **Phases restructurées** : Phase 2 groupée (framework + défenses + métriques, 4-5h avec TDD)
- **UAT renforcé** : Génération syllabus test bout-en-bout + extraction métriques JSON

**Amendements V2.2.1 (Codex)** :

- Clarification du contrat `validate_and_classify_input` et exemples d’usage alignés
- Durcissement du parsing markdown (fallback titre) + validation post-parse
- Clarification UAT en critères opératoires et ajout Go/NoGo

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

### H1 : Configuration llama.cpp sous-optimale ⚠️ **PRIORITÉ 1**

**Constat dans `docker-compose.dgx.yml`** :

- Flag `-n` ambigu
- Absence de `--n-predict` et `--batch-size`

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

- Test ctx saturation avant fix : output tronqué au niveau du ctx-size
- Test ctx saturation après fix : output atteint la limite prévue sans EOF

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

**Changements attendus** :

- Remplacer `-n` par `--ctx-size`
- Ajouter `--n-predict`
- Utiliser `--batch-size`
- Aligner les defaults entre `models.env` et `docker-compose.dgx.yml`

**Validation** :

- Smoke test complet (query simple → rapport final)
- Logs sans EOF
- Taux de complétion stable sur 3-5 runs

### S2 : Validations préventives d'entrée

**Problème** : Agent passe `file-xxx` au lieu de filename (#6), ou URLs corrompues (#47).

**Solution** : Validation stricte + classification d’entrée (file_id, URL, filename, path).

**Contrat** :

- Retourner type + erreur (si invalide)
- Rejeter URL non ASCII et path traversal

**Tests attendus** :

- file_id valide → accepté
- URL non ASCII → rejetée
- filename strict → accepté
- path traversal → rejeté

### S3 : Support file_id dans upload_files_to_vectorstore

**Problème** : file_id passé au lieu d’un filename.

**Solution** : Lookup dans `KnowledgeDBManager` par file_id.

**Tests attendus** :

- file_id connu → réutilisé
- file_id inconnu → erreur claire

### S4 : Gestion d’erreurs de sortie (fallback)

**Problème** : Sorties invalides ou incomplètes en fin de chaîne.

**Solution** :

- Vérification stricte de la sortie.
- **Retry unique avec hint** si la sortie est invalide.
- Si nouvel échec, **retourner un JSON vide** avec un **code/message d’erreur** dans le format de retour (pas d’exception).
- Le manager (LLM) détecte l’échec via la réponse structurée vide et décide de relancer.

**Référence** : voir `plannings/ROBUSTIFICATION_PROPOSAL_FALLBACK_STRATEGY.md` (proposition d’implémentation).

**Tests attendus** :

- Sortie invalide → retry avec hint, pas de crash
- Deuxième échec → JSON vide + code/message d’erreur renseignés
- Sortie valide → pas de fallback, pas de modification du flux

### S5 : Writer markdown only (contrat de sortie)

**Principe** : Le writer retourne **uniquement du markdown**. Pas de structured output JSON pour le writer.

**Objectif** : Contrat de sortie stable pour la fin de chaîne.

**Contrat minimal** :

- Titre en H1
- Executive Summary
- Sections principales
- Follow-up Questions (1-3)

**Tests attendus** :

- Test contrat markdown : sections obligatoires présentes
- Test cohérence : contenu non vide, taille minimale

### S6 : Save programmatique (déterministe)

**Problème** : Writer peut skip le tool call `save_report`.

**Solution** : Sauvegarde déterministe côté manager, sans tool call.

**Valeur** : Traçabilité et persistence garanties, même en cas d’échec partiel.

**Tests attendus** :

- Test success : création `research_report_*.md` + `metadata_*.json`
- Test failure : si rapport vide, metadata écrite avec flag d’invalidité

---

## 5. Solutions écartées pour cette itération (liste non ordonnée)

### E1 : Prompts spécifiques par modèle (ne pas faire)

**Justification** : Objectif = prompts agnostiques (cloud/local). Adaptation par modèle → phase d’évaluation.

### E2 : Pass@K et chainage de stratégies

**Justification** : Sur‑engineering pour cette itération. À considérer **en évolution future** si les tests montrent un taux d’échec élevé malgré S1–S6.

### E3 : Fallback markdown (ne pas faire)

**Justification** : Un fallback qui change de format n’aide pas la chaîne.

### E4 : Framework métriques complet

**Justification** : À traiter après stabilisation. Ici, focus sur contrats et tests.
**Proposition de Références**" : ROBUSTIFICATION_PROPOSAL_METRICS.md

### E5 : Grammars llama.cpp (ne pas faire)

**Justification** : Utile potentiellement, mais priorité après correction S1 et validation UAT.

### E6 : Changement moteur inférence (vllm)

**Justification** : Overhead migration. Tester llama.cpp optimisé d’abord.

### E7 : Context trimming

**Principe** : Réduire le contexte **uniquement** si les tests montrent une saturation persistante.

**Valeur** : Améliorer stabilité sur runs longs sans casser les agents de search.

**Tests attendus** :

- Test “messages trimmed” : seules les N dernières entrées non-system
- Test “search untouched” : aucune perte pour search agent

---

## 6. Plan d’implémentation (1 journée, orienté tests)

### Workflow TDD (rappel)

Pour chaque étape :

1. Problème → valeur attendue
2. Test d’acceptance (Given/When/Then)
3. Implémentation minimale

---

### Phase 1 : Fix llama.cpp config (2-3h) ✅ **PRIORITÉ BLOQUANTE**

**Problème** : Troncature JSON (EOF).

**Valeur** : Contexte maîtrisé, sorties stables.

**Tests attendus** :

- Test ctx saturation avant/après fix
- Smoke test 3 runs complets sans `ModelBehaviorError`

---

### Phase 2 : Writer markdown only + Save déterministe (2-3h)

**Problème** : Format de sortie instable + save non garanti.

**Valeur** : Contrat de sortie stable et persistence garantie.

**Tests attendus** :

- Test contrat markdown (sections obligatoires)
- Test save programmatique (rapport + metadata)
- Test rapport vide → metadata invalide

---

### Phase 3 : Validation d’entrées (1-2h)

**Problème** : Inputs fragiles (file_id, URL corrompue, path traversal).

**Valeur** : Ingestion fiable.

**Tests attendus** :

- file_id valide accepté
- URL non ASCII rejetée
- filename strict accepté
- path traversal rejeté

---

### Phase 4 : Context trimming (conditionnel, 1-2h)

**Problème** : Saturation contextuelle persistante.

**Valeur** : Stabilité sur runs longs sans casser search.

**Tests attendus** :

- Trim uniquement pour writer/planner
- Aucun trimming pour search

---

### UAT (1-2h)

**Objectif** : Validation bout‑en‑bout.

**Critères Go/NoGo** :

- 3/4 queries complètent jusqu’au rapport final
- Pas de troncature EOF
- Les fichiers `research_report_*.md` + `metadata_*.json` existent

---

## 7. Décisions techniques importantes

### 7.1. Writer markdown only

**Raison** : Le writer est la fin de chaîne. Un format unique simplifie tout.

### 7.2. Fallback simple

**Raison** : Pas de chainage / Pass@K dans ce plan. Si échec, produire une erreur parsable (option future) et laisser le manager décider.

---

## 8. Critères de succès

### Minimal (Go/NoGo)

- Config llama.cpp corrigée et validée
- 3/3 smoke tests sans EOF
- Writer markdown only opérationnel
- Save programmatique écrit rapport + metadata

### Optimal

- 4/4 UAT complètent
- Issues #6 et #47 résolues
- Context trimming validé si nécessaire

---

## Conclusion

Cette v2.3.2 remet la **simplicité et les tests** au centre :

1. Corriger la cause racine (llama.cpp)
2. Stabiliser le contrat writer (markdown only)
3. Garantir la persistence (save programmatique)
4. Valider l’ingestion (inputs)
5. Ajouter du trimming **seulement si les tests le justifient**

**Évolutions futures possibles** :

- Pass@K
- Chainage de stratégies
- Framework métriques complet
- Grammars llama.cpp
