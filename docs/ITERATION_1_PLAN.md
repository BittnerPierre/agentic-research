# Itération 1 – Serveur MCP synchrone + UAT

**Issue** : #83  
**Objectif** : Serveur MCP agentic-research utilisable en local (outils en mode synchrone), base de tests saine, UAT exécutable.

---

## Périmètre

- Consolider l’existant : tests verts, serveur démarrable, outils `research_query` et `research_syllabus` en **appel synchrone**.
- Ajouter un **test explicite** (TDD) : appel synchrone → réponse contient au moins `short_summary` (ou marqueur du rapport) ; mock de `run_research_async` pour rester rapide.
- **UAT** : script client MCP qui se connecte au serveur (Streamable HTTP), appelle `research_query` avec une requête courte, affiche le résultat (au moins `short_summary`). Exécutable avec `poetry run python scripts/uat_mcp_agentic_research_client.py` (serveur + dataprep démarrés).
- **Doc** : rappel dans `MCP_SERVER.md` que MCP Inspector / MCP Jam peuvent servir pour un test manuel (optionnel pour valider l’itération).

## Hors périmètre (itération 1)

- MCP Tasks, Cancellation, Ping, Progress (itération 2).
- Déploiement DGX / Alpic.
- Open WebUI (UAT possible plus tard).

---

## Checklist implémentation

- [ ] Suite de tests existante verte (`pytest`), corrections si besoin (imports, chemins).
- [ ] Nouveau test (TDD) : appel synchrone à un outil → réponse contient le format attendu (ex. `short_summary`) ; mock de `run_research_async`.
- [ ] Script UAT `scripts/uat_mcp_agentic_research_client.py` : connexion Streamable HTTP, appel `research_query`, affichage du résultat ; URL configurable (env ou défaut `http://localhost:8008/mcp`).
- [ ] Doc : dans `MCP_SERVER.md`, section ou phrase sur test manuel avec MCP Inspector / MCP Jam (optionnel).
- [ ] Aucun changement de comportement pour la CLI.

---

## Critères de revue

- Les tests passent en local.
- Le serveur démarre avec `poetry run agentic_research_server ...` (et dataprep dans un autre terminal).
- L’UAT script s’exécute et affiche un résumé/rapport (ou une erreur explicite si serveur/dataprep indisponible).
- La description du plan est dans cette PR (ou dans `docs/ITERATION_1_PLAN.md`).

---

## Référence

- Plan détaillé global : `docs/ISSUE_83_ETUDE_ET_PLAN.md`
