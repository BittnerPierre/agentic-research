# feat(83): Itération 1 + 2 – MCP server agentic-research

**Issue** : #83  
**Branche** : feature/83-iteration-1-mcp-sync-uat

---

## Itération 1 (livrée)

Serveur MCP agentic-research utilisable en local (outils en mode synchrone), base de tests saine, UAT exécutable.

- [x] Suite de tests verte, test TDD `test_sync_call_returns_response_with_short_summary`
- [x] Script UAT `scripts/uat_mcp_agentic_research_client.py` (port 8008 par défaut)
- [x] Port **8008** pour le serveur MCP (conflit évité avec llm-instruct 8002 sur DGX)
- [x] Doc `MCP_SERVER.md` (Tests et UAT), override `agentic-research-mcp` dans `docker-compose.dgx.yml`
- [x] Aucun changement de comportement pour la CLI

Détail : `docs/ITERATION_1_PLAN.md`

---

## Itération 2 (en cours)

Conformité MCP 2025-11-25 : **Tasks**, **Cancellation**, **Ping**, **Progress**.

- [ ] Tasks : appels task-augmented, CreateTaskResult, tasks/list, get, result, cancel, capabilities
- [ ] Cancellation : tasks/cancel (+ notifications/cancelled si applicable)
- [ ] Ping : réponse à la requête ping
- [ ] Progress : progressToken + notifications/progress pendant l’exécution
- [ ] Tests : au moins un test task-augmented
- [ ] Doc : exemple client task-augmented dans MCP_SERVER.md

Détail : `docs/ITERATION_2_PLAN.md`

---

## Référence

- Plan global : `docs/ISSUE_83_ETUDE_ET_PLAN.md`
