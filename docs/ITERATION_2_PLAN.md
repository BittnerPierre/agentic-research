# Itération 2 – MCP Tasks, Cancellation, Ping, Progress

**Issue** : #83  
**Branche** : feature/83-iteration-1-mcp-sync-uat (suite itération 1)  
**Objectif** : Conformité MCP 2025-11-25 pour opérations longues (Tasks) et utilitaires (Cancellation, Ping, Progress).

---

## Périmètre

- **Tasks** : les outils `research_query` et `research_syllabus` acceptent les appels **task-augmented** ; le serveur retourne immédiatement un `CreateTaskResult` (taskId, status `working`, pollInterval), exécute la recherche en arrière-plan ; implémentation de `tasks/list`, `tasks/get`, `tasks/result`, `tasks/cancel` ; déclaration des capabilities `tasks` et `execution.taskSupport` (recommandé : `"optional"`) sur les outils.
- **Cancellation** : prise en charge de `tasks/cancel` pour les tâches ; pour les requêtes non-tâche, gestion de `notifications/cancelled` si le transport l’expose.
- **Ping** : répondre à la requête `ping` (vérifier si FastMCP le fait déjà).
- **Progress** : accepter `progressToken` dans la requête initiale et envoyer `notifications/progress` pendant l’exécution (ex. étapes : planning, search, writing).
- **Tests** : au moins un test pour appel task-augmented (création de tâche, poll, récupération du résultat).
- **Doc** : mettre à jour `MCP_SERVER.md` (exemple client avec task-augmented, polling, `tasks/result`).

## Hors périmètre (itération 2)

- Elicitation.
- Exécution durable (Restate) – phase ultérieure si besoin.

---

## Étapes prévues

1. **Vérifier le support Tasks** dans FastMCP / SDK MCP (capabilities, CreateTaskResult, handlers). Si absent, évaluer couche adaptatrice ou mise à jour de dépendances.
2. **TDD** : test qu’un appel task-augmented retourne un CreateTaskResult puis que `tasks/result` renvoie le rapport une fois la tâche terminée.
3. **Implémentation** : exécution en arrière-plan (asyncio Task ou thread), stockage des tâches (taskId → état, résultat), endpoints tasks/list, get, result, cancel.
4. **Cancellation, Ping, Progress** : implémenter ou déléguer selon la spec.
5. **Doc et UAT** : exemple client task-augmented dans MCP_SERVER.md ; optionnel : étendre le script UAT pour tester le mode tâche.

---

## Références

- Spec MCP Tasks : https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks  
- Cancellation : https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation  
- Ping : https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping  
- Progress : https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress  
- Plan global : `docs/ISSUE_83_ETUDE_ET_PLAN.md`
