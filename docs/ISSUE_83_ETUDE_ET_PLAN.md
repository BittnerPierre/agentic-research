# Issue 83 – MCP Server agentic-research : étude et plan d’action

**Date** : 2025-02-18  
**Contexte** : Reprise du travail après rebase de la branche `feature/83-mcp-server-agentic-research` sur `main`. Phase **étude et planification uniquement** (pas de développement).

---

## 1. Synthèse du besoin (relance)

### 1.1 Objectif (Issue 83)

- **Exposer agentic-research comme service MCP distant**, utilisable depuis des clients MCP (ChatGPT, Claude, Le Chat, Open-WebUI, etc.).
- Aujourd’hui : CLI (`poetry run agentic-research`) ou batch Docker ; pas d’accès “outil” pour un client MCP.

### 1.2 Périmètre fonctionnel

- **Mode query** : lancer une recherche à partir d’une requête texte (équivalent `--query`).
- **Mode syllabus** : lancer une recherche à partir d’un contenu type syllabus (équivalent `--syllabus` / fichier).
- **Transport** : Streamable HTTP (hébergement prévu sur DGX Spark, accès via Tailscale).
- **Intégration** : service dans le `docker-compose` existant, documentation client, tests d’intégration (MCP Inspector ou MCP Jam).

### 1.3 Exigence de déploiement (ajout)

Le serveur MCP agentic-research (comme dataprep) doit être déployable sur **deux cibles** en plus du local :

| Étape | Cible | Détail |
|-------|--------|--------|
| 1 | **Local** | Fonctionnel en premier (Poetry + optionnellement `docker compose`). |
| 2 | **DGX Spark** | Conteneur Docker avec **`docker-compose.dgx.yml`** (fusionné avec `docker-compose.yml`). |
| 3 | **Alpic.ai** | Déploiement sur la plateforme [Alpic](https://docs.alpic.ai/guides/understanding-the-build-process), qui s’appuie sur des configs (build, install, start). |

- **Stack** : l’app utilise **FastMCP** (inclus dans le package `mcp`), pas le template Alpic brut ; le [template Python Alpic](https://github.com/alpic-ai/mcp-server-template-python) sert de référence, mais notre serveur reste basé sur FastMCP.
- **Alpic** : la plateforme détecte le transport (Streamable HTTP, SSE, stdio) en analysant le code (ex. `mcp.run()` / `mcp.http_app()` avec `transport="streamable-http"`). FastMCP appelle en interne l’API MCP ; il faut s’assurer que la détection Alpic fonctionne ou prévoir un fichier **`alpic.json`** (voir section 4.4).

### 1.4 Exigences MCP (protocole) – obligatoires

La génération de rapport agentic-research est une **opération longue** ; le protocole MCP (révision 2025-11-25) prévoit les **Tasks** pour ce cas, et Alpic supporte cette fonctionnalité. Les exigences suivantes sont **obligatoires** :

| Exigence | Spécification MCP | Rôle |
|----------|-------------------|------|
| **Tasks** | [Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks) | Appels d’outils (`tools/call`) en mode tâche : le serveur accepte la requête, retourne immédiatement un `CreateTaskResult` (taskId, status, pollInterval), le client poll via `tasks/get` et récupère le résultat via `tasks/result` une fois la tâche terminée. Évite de bloquer la connexion pendant toute la durée de la recherche. |
| **Cancellation** | [Cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation) | Pour les requêtes en cours : notification `notifications/cancelled` ; pour les tâches, utilisation de `tasks/cancel` (mécanisme dédié). |
| **Ping** | [Ping](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping) | Vérification que la connexion est vivante (requête `ping`, réponse vide). |
| **Progress** | [Progress](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress) | Suivi optionnel des opérations longues via `progressToken` dans la requête et `notifications/progress` ; pour les tâches, le `progressToken` reste valide pendant toute la durée de la tâche. |

- **Capabilities** : le serveur doit déclarer `tasks` (ex. `tasks.requests.tools.call`) et exposer pour les outils `research_query` / `research_syllabus` un `execution.taskSupport` à `"optional"` ou `"required"` selon le choix (recommandation : `"optional"` pour compatibilité clients anciens).
- **Implémentation** : l’implémentation actuelle fait un appel synchrone à `run_research_async()` et retourne le rapport directement ; il faut la faire évoluer vers des appels **task-augmented** (création de tâche, exécution en arrière-plan, `tasks/get` et `tasks/result`).

### 1.5 Hors périmètre (Issue 83)

- Refactor majeur des agents.
- Changement de fournisseurs LLM.
- **Elicitation** ([spécification](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)) : **hors périmètre pour cette phase**. L’elicitation (demande de feedback ou revue intermédiaire à l’utilisateur) n’est pas dans le workflow actuel d’agentic-research ; ce sera une étape ultérieure si on introduit des boucles de validation utilisateur.

### 1.6 Relation avec le POC Restate (issue #69, PR #84)

- **Issue [#69](https://github.com/BittnerPierre/agentic-research/issues/69)** : Restate POC – exécution durable, reprise après crash, pour le writer agent.
- **PR [#84](https://github.com/BittnerPierre/agentic-research/pull/84)** : implémentation POC (writer agent Restate, Docker, deep_manager avec `RESTATE_WRITER_ENABLED`).

Ce travail n’a pas encore été revu/mergé. Il est **potentiellement lié** à la gestion des tâches longues côté MCP : si on souhaite une exécution **durable** (reprise après crash du serveur MCP ou du client), Restate peut être une brique. Pour l’Issue 83, on vise d’abord la conformité MCP (Tasks, Cancellation, Ping, Progress) ; si l’exécution durable s’avère nécessaire, s’appuyer sur le POC Restate (issue #69, PR #84) et la doc dans `plannings/` et `docs/UAT_RESTATE.md`.

### 1.7 Critères d’acceptation (Issue 83)

- Un service MCP tourne via `docker compose` (Streamable HTTP).
- Les modes query et syllabus fonctionnent via un client MCP.
- **MCP Tasks** : les outils `research_query` et `research_syllabus` supportent les appels **task-augmented** (création de tâche, polling `tasks/get`, récupération du résultat via `tasks/result`). Capabilities `tasks` déclarées ; **Cancellation** (`tasks/cancel` pour les tâches), **Ping** et **Progress** implémentés conformément aux spécifications MCP 2025-11-25.
- **Déploiement** : le serveur MCP est déployable sur **DGX Spark** (conteneur avec `docker-compose.dgx.yml`) et sur **Alpic.ai** (config build/start, avec FastMCP ; Alpic supporte les Tasks).
- Tests d’intégration (locaux ou CI, ou procédure explicite).
- Documentation d’usage et de configuration à jour (dont DGX, Alpic, et usage des Tasks côté client).

---

## 2. État des lieux (implémentation existante)

### 2.1 Ce qui existe déjà sur la branche (avant rebase, réappliqué après stash)

| Élément | Fichier / lieu | Rôle |
|--------|-----------------|------|
| **Serveur MCP** | `src/mcp/agentic_research_server.py` | FastMCP avec 2 outils : `research_query`, `research_syllabus` ; Streamable HTTP ; `run_research_async()` comme moteur |
| **Moteur partagé** | `src/run_research.py` | `run_research_async()` : config, MCP FS + DataPrep, backend vector, manager, retour `ReportData \| None` |
| **CLI** | `src/main.py` | Utilise `run_research_async()` pour query / syllabus / interactif |
| **Managers** | `src/agentic_manager.py`, `src/deep_research_manager.py` | Signature `run(...) -> ReportData` (au lieu de `-> None`) pour retourner le rapport |
| **Compose** | `docker-compose.yml` | Service `agentic-research-mcp` (port 8002, commande `agentic_research_server`, MCP_DATAPREP_URL, etc.) |
| **Script Poetry** | `pyproject.toml` | `agentic_research_server = "src.mcp.agentic_research_server:main"` |
| **Doc** | `docs/MCP_SERVER.md` | Prérequis, démarrage local/Docker, outils, exemples client, config |
| **Tests** | `tests/test_agentic_research_server.py` | Création serveur, `research_query` / `research_syllabus` (mock `run_research_async`), gestion erreur |

### 2.2 Points forts de l’existant

- Séparation claire : **CLI** et **MCP** s’appuient sur le même `run_research_async()`, pas de duplication de logique.
- Deux outils MCP alignés sur les deux modes (query / syllabus).
- Intégration Docker déjà prévue (service, env, commande).
- Tests unitaires sur le serveur MCP (outils exposés, format de retour, erreurs).

### 2.3 Points à clarifier ou à compléter (analyse)

- **Appels synchrones actuels** : les outils MCP `research_query` et `research_syllabus` appellent `run_research_async()` et attendent le résultat avant de répondre. Il faut les faire évoluer vers le modèle **Tasks** : accepter la requête avec `task` dans les params, retourner immédiatement un `CreateTaskResult`, exécuter la recherche en arrière-plan, exposer `tasks/list`, `tasks/get`, `tasks/result`, `tasks/cancel` ; déclarer les capabilities et `execution.taskSupport` sur les outils.
- **Cancellation, Ping, Progress** : non implémentés aujourd’hui ; à ajouter conformément aux specs MCP 2025-11-25.
- **Imports dans `run_research.py`** : `from agents import ...` et `from agents.mcp import ...` supposent que le répertoire de travail est la racine du projet (ou que `agents` est le package openai-agents). À confirmer en exécution (CLI, Docker, MCP).
- **Pas de timeouts / limites** côté MCP : une recherche longue peut bloquer le client tant que Tasks n’est pas en place ; pas de limite de taille sur `query` / `syllabus_content` (garde-fous mentionnés dans l’issue).
- **Pas de healthcheck** sur le service `agentic-research-mcp` dans le compose.
- **Tests d’intégration** : pas de test réel avec un client MCP (Streamable HTTP) ou de procédure documentée pour MCP Inspector / MCP Jam.
- **Variables / sécurité** : questions ouvertes dans l’issue (ports, auth, ACL Tailscale, token MCP) non traitées dans l’implémentation actuelle.

---

## 3. Analyse d’impact

### 3.1 Fichiers et composants impactés

| Composant | Impact | Commentaire |
|-----------|--------|-------------|
| **src/run_research.py** | Nouveau (partagé CLI + MCP) | Cœur de l’exécution ; déjà utilisé par `main.py` et `agentic_research_server.py`. |
| **src/main.py** | Modifié | Délègue à `run_research_async()` au lieu de dupliquer la logique. |
| **src/agentic_manager.py** | Modifié | `run()` retourne `ReportData` pour que le MCP puisse formater le rapport. |
| **src/deep_research_manager.py** | Modifié | Idem. |
| **src/mcp/agentic_research_server.py** | Nouveau | Serveur MCP uniquement. |
| **src/config.py** | Inchangé pour l’instant | MCP DataPrep déjà configuré (`MCPConfig`, `server_host`, `server_port`). |
| **docker-compose.yml** | Modifié | Nouveau service `agentic-research-mcp`. |
| **pyproject.toml** | Modifié | Script `agentic_research_server`. |
| **tests** | Modifié / nouveau | `test_cli_main_config.py` adapté à `run_research` ; `test_agentic_research_server.py` nouveau. |

### 3.2 Impact sur les flux existants

- **CLI** : inchangé côté utilisateur ; en interne, même chemin d’exécution via `run_research_async()`. Risque de régression limité si les tests CLI et les tests du serveur MCP passent.
- **Batch Docker (agentic-research)** : pas de changement de comportement (image et commande inchangées).
- **DataPrep MCP** : inchangé ; le serveur agentic-research est un **client** de DataPrep (via `MCP_DATAPREP_URL`).
- **Evaluations / benchmarks** : pas de modification des entrées/sorties ; ils utilisent les managers comme avant.

### 3.3 Dépendances

- **DataPrep** : le service MCP agentic-research **dépend** du service dataprep (vector store, base de connaissances). Démarrage ordonné ou documentation claire nécessaire (déjà décrit dans `MCP_SERVER.md`).
- **OpenAI / LiteLLM** : inchangées (config existante).
- **FastMCP / MCP** : déjà en dépendances (`pyproject.toml`) pour le dataprep ; réutilisées pour le serveur agentic-research.

---

## 4. Étude d’architecture

### 4.1 Positionnement du serveur MCP agentic-research

```
[Client MCP: ChatGPT / Claude / Le Chat / Open-WebUI / script]
        │
        │ Streamable HTTP (port 8002, path /mcp)
        ▼
[Agentic Research MCP Server]  (FastMCP)
        │
        │ research_query(q) / research_syllabus(s)
        ▼
[run_research_async(query, ...)]
        │
        ├── Config (YAML, env)
        ├── MCP FS (stdio) → répertoire temporaire
        ├── MCP DataPrep (SSE) → URL (ex. http://dataprep:8001/sse)
        ├── Vector backend (OpenAI ou Chroma selon config)
        └── Manager (agentic_manager / deep_manager)
                │
                └── Rapport → ReportData → format texte pour l’outil MCP
```

- Le serveur MCP **n’est pas** un agent : il expose des **outils** qui, lorsqu’ils sont appelés, lancent une recherche complète (planning, search, report) et retournent le rapport.
- **Avec MCP Tasks** (exigence 1.4) : une invocation d’outil en mode tâche → le serveur retourne immédiatement un `CreateTaskResult` (taskId, status `working`, pollInterval), exécute `run_research_async()` en arrière-plan ; le client poll via `tasks/get` et récupère le résultat via `tasks/result`. Sans tâche (client legacy), le comportement peut rester synchrone si `execution.taskSupport` est `"optional"`.

### 4.2 Choix déjà actés

- **Transport** : Streamable HTTP (aligné avec l’issue et l’hébergement DGX Spark).
- **API outils** : 2 outils, un par mode (query / syllabus), entrée chaîne, sortie chaîne (rapport formaté ou message d’erreur). Les outils **doivent** supporter les appels **task-augmented** (MCP 2025-11-25).
- **Réutilisation** : pas de nouveau “runner” ; `run_research_async()` est le point d’entrée unique pour une exécution (CLI ou MCP).
- **Spec MCP** : révision [2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks) (Tasks, Cancellation, Ping, Progress).

### 4.3 Options laissées ouvertes (issue / doc)

- **Timeouts** : timeout par appel d’outil côté serveur (et éventuellement côté client) pour éviter des blocages longs.
- **Limites** : taille max de `query` et `syllabus_content` pour éviter abus et surcharge.
- **Healthcheck** : endpoint ou mécanisme pour le compose / orchestration.
- **Sécurité** : auth (token MCP, API key), ACL Tailscale (opérationnel, pas forcément dans le code).
- **Client de test** : MCP Inspector vs MCP Jam vs script Python documenté.

### 4.4 Déploiement : DGX Spark et Alpic

**DGX Spark (`docker-compose.dgx.yml`)**

- Le script `scripts/start-docker-dgx.sh` lance la stack avec `docker compose -f docker-compose.yml -f docker-compose.dgx.yml`. Les services de `docker-compose.yml` (dont `agentic-research-mcp`) sont donc présents après fusion.
- **À prévoir** : dans `docker-compose.dgx.yml`, ajouter un override pour le service **agentic-research-mcp** afin qu’il utilise la config DGX (`configs/config-docker-dgx.yaml`), la bonne `MCP_DATAPREP_URL` (dataprep dans le même compose) et, si besoin, `depends_on: [dataprep, chromadb]`. Sans override, le service utilise la définition de `docker-compose.yml` (port 8002, commande par défaut) ; avec override, on aligne le comportement sur l’environnement DGX (LLM locaux, Chroma, etc.).

**Alpic.ai**

- Référence : [Understanding the Build Process](https://docs.alpic.ai/guides/understanding-the-build-process). Alpic détecte le framework MCP, la commande de build et le **transport** en analysant le dépôt.
- **Détection du transport (Python)** : Alpic cherche des appels `mcp.run()` ou `mcp.http_app()` avec un paramètre explicite, par ex. `transport="streamable-http"` → streamable-http. Notre serveur utilise **FastMCP** : `server.run(transport="streamable-http", host=..., port=..., path=path)`. FastMCP s’appuie sur le SDK MCP ; il faut **vérifier** en déployant (ou en lisant le code FastMCP) que cette forme est reconnue par Alpic. Si ce n’est pas le cas, l’erreur « No MCP transport found » impose soit d’ajouter un fichier **`xmcp.config.ts`** (projets TypeScript), soit de fournir une **commande de démarrage explicite** via **`alpic.json`**.
- **Fichier `alpic.json`** (racine du projet) : permet de surcharger les commandes détectées, par ex. :
  - `installCommand` : `poetry install` (ou `pip install -e .` selon le choix de packaging).
  - `startCommand` : `poetry run agentic_research_server --host 0.0.0.0 --port ${PORT:-8002} --transport streamable-http --path /mcp` (Alpic peut injecter `PORT`).
  - Optionnel : `buildCommand` si un build est nécessaire.
- **Spécificité agentic-research** : le serveur MCP **dépend d’un service DataPrep** (vector store, base de connaissances). Sur Alpic, DataPrep n’est pas dans le même conteneur. Il faudra soit (1) déployer aussi DataPrep sur Alpic (deux déploiements / deux services) et configurer `MCP_DATAPREP_URL` vers l’URL du DataPrep Alpic, soit (2) documenter que le déploiement Alpic “agentic-research” suppose un DataPrep déjà disponible (URL en variable d’environnement). Même contrainte que pour DGX : l’ordre logique reste Local → DGX (compose avec dataprep) → Alpic (config DataPrep à définir).

---

## 5. Plan d’action proposé

### Phase 1 – Local : stabilisation et validation (priorité haute)

1. **Rebase et état du repo**
   - Rebase sur `main` : fait.
   - Réappliquer le travail (stash pop) : fait.
   - Décider : soit committer l’état actuel sur la branche, soit garder en WIP jusqu’à validation du plan.

2. **Vérification de l’existant (local)**
   - Exécuter la suite de tests (`pytest`) et corriger les éventuelles régressions (imports, chemins).
   - Vérifier en local : `poetry run agentic_research_server ...` puis test manuel avec un client MCP (ex. script Python de `MCP_SERVER.md` ou MCP Inspector).
   - Vérifier le compose : `docker compose up -d dataprep agentic-research-mcp` puis test client vers `http://localhost:8002/mcp`.

3. **Petits correctifs si besoin**
   - Corriger les imports dans `run_research.py` si des erreurs apparaissent (contexte d’exécution CLI vs MCP vs Docker).
   - S’assurer que `agentic_manager` et `deep_manager` retournent bien un `ReportData` dans tous les chemins (déjà le cas avec les patchs actuels).

### Phase 2 – MCP Tasks, Cancellation, Ping, Progress (priorité haute)

4. **Implémentation MCP Tasks**
   - Faire évoluer le serveur pour accepter les appels `tools/call` avec paramètre `task` (optionnel ou requis selon `execution.taskSupport`).
   - Retourner un `CreateTaskResult` (taskId, status `working`, ttl, pollInterval) dès l’acceptation ; lancer `run_research_async()` en arrière-plan (thread, asyncio task, ou file d’exécution).
   - Implémenter `tasks/list`, `tasks/get`, `tasks/result`, `tasks/cancel` ; stocker l’état des tâches (taskId → statut, résultat ou erreur) avec TTL et nettoyage.
   - Déclarer les capabilities `tasks` (ex. `tasks.requests.tools.call`) et, pour chaque outil, `execution.taskSupport: "optional"` (recommandé) ou `"required"`.
   - Vérifier la compatibilité SDK/FastMCP avec la spec MCP 2025-11-25 (Tasks) ; si FastMCP ne supporte pas encore les Tasks, évaluer une couche personnalisée ou une mise à jour de dépendances.

5. **Cancellation, Ping, Progress**
   - **Cancellation** : pour les requêtes non tâche, gérer `notifications/cancelled` ; pour les tâches, implémenter `tasks/cancel` (passer la tâche en `cancelled`, arrêter l’exécution si possible, ex. via un flag ou un mécanisme d’annulation asynchrone).
   - **Ping** : répondre à la requête `ping` par une réponse vide (vérifier si FastMCP le fait déjà).
   - **Progress** : pour les tâches, accepter `progressToken` dans la requête initiale et envoyer `notifications/progress` pendant l’exécution (ex. étapes : planning, search, writing) ; le token reste valide pendant toute la durée de la tâche (spec Progress).

6. **Tests et doc**
   - Tests unitaires ou d’intégration pour création de tâche, polling, résultat, annulation.
   - Mettre à jour `MCP_SERVER.md` : exemple client avec appel task-augmented, polling, `tasks/result`.

### Phase 3 – DGX Spark : déploiement conteneur (priorité haute)

7. **Intégration dans `docker-compose.dgx.yml`**
   - Ajouter un bloc de surcharge pour le service **agentic-research-mcp** : `command` avec `--config configs/config-docker-dgx.yaml`, `MCP_DATAPREP_URL` pointant vers le service dataprep (ex. `http://dataprep:8001/sse`), et si pertinent `depends_on: [dataprep, chromadb]`.
   - Vérifier que la stack DGX démarre avec `scripts/start-docker-dgx.sh` (ou équivalent) en incluant `agentic-research-mcp` dans les services lancés, et tester un appel client MCP (avec Tasks) vers le serveur (Tailscale ou accès direct au host).

8. **Documentation**
   - Mettre à jour `MCP_SERVER.md` (et si besoin `docs/README_DOCKER.md`) : démarrage sur DGX avec `docker-compose.dgx.yml`, URL Tailscale, variables d’environnement.

### Phase 4 – Alpic.ai : déploiement plateforme (étape 3, après local + DGX)

9. **Compatibilité Alpic**
   - Vérifier que Alpic détecte le transport Streamable HTTP (FastMCP avec `server.run(transport="streamable-http", ...)`). En cas d’échec « No MCP transport found », ajouter à la racine un **`alpic.json`** avec au minimum `startCommand` et `installCommand`.
   - Alpic supporte les Tasks ; vérifier que le déploiement expose bien les capabilities et les outils en mode tâche.
   - Documenter la dépendance à DataPrep : sur Alpic, configurer `MCP_DATAPREP_URL` vers l’URL du serveur DataPrep (déployé séparément sur Alpic ou accessible ailleurs).

10. **Tests d’intégration et critères d’acceptation**
   - Procédure reproductible (MCP Inspector ou script client) pour les modes query et syllabus (avec Tasks), documentée dans `MCP_SERVER.md`.
   - Optionnel : test automatisé avec client MCP (Streamable HTTP + task-augmented call) en environnement contrôlé.

### Phase 5 – Renforcement (priorité moyenne, selon temps et besoin)

11. **Garde-fous**
   - Timeout configurable par tâche (ttl max), limite de taille sur `query` et `syllabus_content` (refus propre avec message d’erreur).

12. **Docker / opérations**
   - Ajouter un healthcheck pour le service `agentic-research-mcp` (ex. HTTP sur le path Streamable HTTP ou endpoint dédié si FastMCP le permet).

13. **Sécurité / déploiement**
   - Traiter les questions ouvertes de l’issue (ports, auth, ACL) : au minimum les documenter (recommandations Tailscale, token MCP si applicable).
   - **Exécution durable** : si reprise après crash s’avère nécessaire, s’appuyer sur le POC Restate (issue [#69](https://github.com/BittnerPierre/agentic-research/issues/69), PR [#84](https://github.com/BittnerPierre/agentic-research/pull/84)).

### Phase 6 – Clôture (priorité haute)

14. **PR et merge**
   - Commits propres, message de commit et PR qui référencent l’issue 83.
   - Vérifier que les critères d’acceptation de l’issue sont couverts (checklist dans la PR).
   - Après review : merge selon les règles du projet (branch protection, CI).

---

## 6. Résumé

- **Besoin** : Exposer agentic-research comme service MCP (modes query + syllabus, Streamable HTTP, Docker, doc et tests), avec déploiement possible sur **DGX Spark** (conteneur, `docker-compose.dgx.yml`) et sur **Alpic.ai** (config build/start). **Alpic supporte les MCP Tasks.**
- **Exigences MCP (obligatoires)** : **Tasks** (outils en mode task-augmented : `CreateTaskResult`, `tasks/get`, `tasks/result`, `tasks/cancel`), **Cancellation**, **Ping**, **Progress** (spec MCP 2025-11-25). **Elicitation** : hors périmètre pour cette phase (étape ultérieure si feedback utilisateur dans le workflow).
- **Exigence de déploiement** : ordre **1. Local (working)** → **2. DGX Spark** → **3. Alpic**. Stack : FastMCP (package `mcp`).
- **Lien Restate** : Issue [#69](https://github.com/BittnerPierre/agentic-research/issues/69), PR [#84](https://github.com/BittnerPierre/agentic-research/pull/84) (POC writer durable) : non mergé ; si exécution durable (reprise après crash) est requise, s’appuyer sur ce POC.
- **État** : Implémentation actuelle en appels synchrones ; à faire évoluer vers Tasks + Cancellation + Ping + Progress.
- **Plan** : Phase 1 Local → Phase 2 **MCP Tasks, Cancellation, Ping, Progress** → Phase 3 DGX → Phase 4 Alpic → Phase 5 Renforcement → Phase 6 Clôture.

---

*Document rédigé dans le cadre de la reprise de l’Issue 83, phase étude et planification uniquement.*
