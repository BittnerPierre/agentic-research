# Plan d'évaluation Restate - POC Writer Agent

**Version**: 1.0.0  
**Date**: 6 février 2026  
**Objectif**: Évaluer la pertinence de Restate pour la robustification du système agentic-research  
**Scope**: Writer agent uniquement (fin de chaîne)  
**Timeline**: En parallèle du plan de robustification principal

---

## 1. Contexte et motivation

### Problème à valider

Le système agentic-research présente des échecs en cours d'exécution (issues #6, #7, #46, #47). Restate promet :

- **Durable Execution** : reprise automatique à la dernière étape réussie
- **Observabilité** : traçabilité fine de chaque LLM call et tool call
- **Retry automatique** : gestion des erreurs transitoires

### Hypothèse à tester

> "Restate apporte une valeur mesurable en termes de résilience et de debuggabilité pour le writer agent, justifiant l'overhead d'infrastructure."

### Pourquoi le Writer agent ?

1. **Fin de chaîne** : point critique où les échecs sont les plus visibles
2. **Complexité modérée** : pas de handoffs complexes, focus sur la génération
3. **Résultats mesurables** : succès/échec binaire (rapport généré ou non)
4. **Impact limité** : échec du POC n'affecte pas le plan principal

---

## 2. Objectifs du POC

### Objectifs primaires

1. **Comparer la résilience** : Writer avec/sans Restate face à des erreurs simulées
2. **Évaluer l'observabilité** : Restate UI vs logs actuels (LangSmith, OpenAI traces)
3. **Mesurer l'overhead** : Temps d'intégration, complexité du code, impact performance

### Objectifs secondaires

4. **Valider la compatibilité** : OpenAI Agents SDK + Restate + DGX Spark stack
5. **Identifier les limites** : Cas où Restate n'apporte pas de valeur

---

## 3. Architecture du POC

### Setup

```
┌─────────────────────────────────────────────────────────┐
│                    DGX Spark                             │
│                                                          │
│  ┌──────────────┐        ┌──────────────┐              │
│  │ llama.cpp    │        │ Restate      │              │
│  │ server       │        │ Server       │              │
│  │ (existant)   │        │ (nouveau)    │              │
│  └──────────────┘        └──────────────┘              │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │     agentic-research service                      │  │
│  │                                                    │  │
│  │  ┌──────────────┐     ┌──────────────────────┐   │  │
│  │  │ Writer Agent │     │ Writer Agent         │   │  │
│  │  │ (baseline)   │     │ (Restate-enabled)    │   │  │
│  │  │              │     │ + DurableRunner      │   │  │
│  │  └──────────────┘     └──────────────────────┘   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Composants

1. **Restate Server** : Binaire standalone, stockage local (SQLite ou RocksDB)
2. **Writer Agent baseline** : Code actuel, sans modification
3. **Writer Agent Restate** : Refactoré avec `DurableRunner`
4. **Test harness** : Script pour exécuter les deux variants et comparer

---

## 4. Plan d'implémentation

### Phase 1 : Setup infrastructure (1-2h)

**Tâches** :

- [ ] Installer Restate Server sur DGX Spark
  ```bash
  # Option 1 : Binaire
  curl -L https://restate.gateway.scarf.sh/latest/restate-server-x86_64-unknown-linux-musl.tar.xz | tar -xJ
  
  # Option 2 : Docker (si disponible sur DGX)
  docker run -p 8080:8080 -p 9070:9070 docker.restate.dev/restatedev/restate:latest
  ```

- [ ] Installer Restate Python SDK
  ```bash
  poetry add restate-sdk
  ```

- [ ] Valider connectivity : Restate Server accessible depuis le service

**Validation** :

- Restate UI accessible sur `http://localhost:9070`
- Service peut se connecter à Restate Server

**Temps estimé** : 1h  
**Bloquant** : Oui (sans setup, pas de POC)

---

### Phase 2 : Refactoring Writer Agent (2-3h)

**Branche** : `feat/restate-poc-writer`

**Tâches** :

- [ ] Créer `src/agents/file_writer_agent_restate.py` (copie de l'existant)
- [ ] Intégrer `DurableRunner` :

```python
from restate_sdk.openai import DurableRunner
from restate_sdk import restate

# Agent existant (simplifié)
writer_agent = Agent(
    name="WriterAgent",
    instructions="You write research reports.",
    tools=[save_report_tool],  # Tool existant
)

# Service Restate
writer_service = restate.Service("WriterAgentRestate")

@writer_service.handler()
async def generate_report(
    ctx: restate.Context, 
    research_info: dict
) -> str:
    """Generate a research report with durable execution."""
    
    # Utiliser DurableRunner pour persister chaque LLM call
    result = await DurableRunner.run(
        writer_agent,
        input=research_info["prompt"],
        # Optionnel : retry config
        llm_retry_opts=LlmRetryOpts(
            max_attempts=3,
            initial_retry_interval=timedelta(seconds=2)
        )
    )
    
    return result.final_output
```

- [ ] Wrapper les tools avec `@durable_function_tool` :

```python
from restate_sdk.openai import durable_function_tool, restate_context

@durable_function_tool
async def save_report_tool(report_data: ReportData) -> str:
    """Save report with durable execution."""
    return await restate_context().run_typed(
        "save_report",
        save_report_to_disk,
        report_data=report_data
    )
```

- [ ] Créer endpoint HTTP pour servir le service Restate

**Validation** :

- Code compile sans erreur
- Agent peut être enregistré dans Restate
- UI Restate affiche le service "WriterAgentRestate"

**Temps estimé** : 2-3h  
**Bloquant** : Oui (cœur du POC)

---

### Phase 3 : Test harness (1-2h)

**Objectif** : Comparer baseline vs Restate de manière contrôlée.

**Tâches** :

- [ ] Créer `tests/integration/test_writer_restate_comparison.py`

```python
"""
Compare Writer Agent avec/sans Restate sur scénarios d'échec.
"""
import pytest
from src.agents.file_writer_agent import create_writer_agent
from src.agents.file_writer_agent_restate import writer_service

# Scénarios de test
SCENARIOS = [
    {
        "name": "nominal",
        "search_results": [...],  # Résultats valides
        "inject_error": None,
        "expected_success": True,
    },
    {
        "name": "llm_timeout",
        "search_results": [...],
        "inject_error": "timeout_on_second_call",
        "expected_success_baseline": False,
        "expected_success_restate": True,  # Devrait retry et réussir
    },
    {
        "name": "tool_call_error",
        "search_results": [...],
        "inject_error": "save_report_fails_once",
        "expected_success_baseline": False,
        "expected_success_restate": True,  # Devrait retry tool
    },
    {
        "name": "json_truncation",
        "search_results": [...],
        "inject_error": "truncate_json_output",
        "expected_success_baseline": False,
        "expected_success_restate": False,  # Même avec Restate, échec si pas de retry
    },
]

@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_writer_comparison(scenario):
    """Compare baseline vs Restate pour chaque scénario."""
    
    # Test baseline
    baseline_result = await run_baseline_writer(
        scenario["search_results"],
        inject_error=scenario["inject_error"]
    )
    
    # Test Restate
    restate_result = await run_restate_writer(
        scenario["search_results"],
        inject_error=scenario["inject_error"]
    )
    
    # Assertions
    assert baseline_result.success == scenario["expected_success_baseline"]
    assert restate_result.success == scenario["expected_success_restate"]
    
    # Comparer observabilité
    compare_traces(baseline_result, restate_result)
```

- [ ] Créer script d'injection d'erreurs contrôlées
- [ ] Implémenter `compare_traces()` pour évaluer l'observabilité

**Validation** :

- Tests passent
- Données de comparaison capturées (succès, temps, nombre de retries, etc.)

**Temps estimé** : 2h  
**Bloquant** : Non (peut commencer avec tests manuels)

---

### Phase 4 : Expérimentation (2-3h)

**Tâches** :

- [ ] Exécuter tests sur DGX Spark avec différents scénarios :
  1. **Nominal** : Pas d'erreur, mesurer l'overhead Restate
  2. **Erreurs transitoires** : Timeout, network glitch
  3. **Erreurs persistantes** : JSON malformé (comme issues #46, #47)
  4. **Process crash simulé** : Tuer le process et vérifier reprise

- [ ] Capturer métriques :
  - Taux de succès (baseline vs Restate)
  - Temps d'exécution (overhead)
  - Nombre de retries
  - Qualité des traces (subjective)

- [ ] Documenter observations dans `plannings/RESTATE_POC_RESULTS.md`

**Validation** :

- Au moins 3 runs par scénario
- Métriques capturées de manière reproductible

**Temps estimé** : 2-3h  
**Bloquant** : Non (peut itérer)

---

## 5. Critères de décision

### Restate vaut le coup SI :

✅ **Résilience** :
- Taux de succès Restate > Baseline d'au moins **20%** sur scénarios d'erreur
- Reprise après crash fonctionne (pas de perte de progression)

✅ **Observabilité** :
- Restate UI permet de debugger **plus vite** qu'avec logs actuels
- Chaque step LLM/tool est traçable sans instrumentation custom

✅ **Overhead acceptable** :
- Performance : Temps d'exécution nominal < **+10%** vs baseline
- Complexité code : Refactoring < **+50 LOC** par agent
- Infrastructure : Setup Restate < **30min** sur DGX

### Restate ne vaut PAS le coup SI :

❌ **Pas de gain résilience** :
- Taux de succès identique baseline vs Restate

❌ **Observabilité équivalente** :
- Logs actuels + LangSmith/OpenAI traces suffisants

❌ **Overhead prohibitif** :
- Performance dégradée > **+20%**
- Complexité opérationnelle trop élevée pour DGX mono-utilisateur

---

## 6. Livrables

### Documents

1. **RESTATE_POC_RESULTS.md** (plannings/) :
   - Résultats des tests
   - Métriques comparatives
   - Screenshots Restate UI
   - Recommandation Go/NoGo

2. **Architecture Decision Record** (docs/adr/) :
   - Décision d'adopter ou rejeter Restate
   - Justification basée sur données du POC

### Code

1. **Branche `feat/restate-poc-writer`** :
   - Writer agent Restate-enabled
   - Tests de comparaison
   - Script d'expérimentation

### Présentations

1. **Demo Restate UI** (optionnel) :
   - Vidéo/screenshots montrant la traçabilité
   - Comparaison avec logs actuels

---

## 7. Risques et mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Restate incompatible avec DGX | Bloquant | Faible | Tester setup en Phase 1 (1h max) |
| Refactoring trop complexe | Retard | Moyen | Limiter POC au writer uniquement |
| Pas de différence mesurable | Temps perdu | Moyen | Accepter le résultat négatif, c'est utile aussi |
| Overhead performance inacceptable | Rejet Restate | Faible | Mesurer dès les premiers tests |

---

## 8. Timeline et parallélisation

### Parallélisation avec plan principal

Le POC Restate peut progresser **en parallèle** du plan de robustification v2.3.2 :

```
Jour 1 (Plan principal)         | Jour 1 (POC Restate)
--------------------------------|--------------------------------
09:00 - Phase 1: Fix llama.cpp  | 09:00 - Phase 1: Setup Restate
11:00 - Phase 2: Writer MD only | 11:00 - Phase 2: Refactor Writer
14:00 - Phase 3: Validation     | 14:00 - Phase 3: Test harness
16:00 - Phase 4: Context trim   | 16:00 - Phase 4: Expérimentation
18:00 - UAT                     | 18:00 - Analyse résultats
```

### Points de synchronisation

- **Fin Phase 2 (plan principal)** : Writer agent stabilisé → bon moment pour tester Restate
- **Fin UAT (plan principal)** : Décision finale sur Restate basée sur résultats combinés

---

## 9. Décision finale

### Critères de décision

À la fin du POC, prendre la décision selon cette matrice :

| Résultats UAT v2.3.2 | Résultats POC Restate | Décision |
|----------------------|----------------------|----------|
| ✅ Succès (>75%)     | ✅ Gains mesurables  | **Adopter Restate** pour Phase 2 (évolution) |
| ✅ Succès (>75%)     | ❌ Pas de gains      | **Rejeter Restate**, système déjà stable |
| ❌ Échecs persistants | ✅ Gains mesurables  | **Adopter Restate** pour robustifier |
| ❌ Échecs persistants | ❌ Pas de gains      | **Rejeter Restate**, chercher autre solution |

### Next steps si adoption

1. Refactorer tous les agents (planning, search) avec Restate
2. Intégrer dans CI/CD (tests Restate automatisés)
3. Déployer Restate Server en production sur DGX
4. Documenter patterns Restate dans CLAUDE.md

### Next steps si rejet

1. Documenter pourquoi dans ADR
2. Focus sur alternatives (S4 du plan principal : fallback simple)
3. Réévaluer Restate dans 3-6 mois si nouveaux besoins

---

## 10. Références

### Documentation Restate

- Quickstart Python: https://docs.restate.dev/ai-quickstart#python-%2B-openai
- Tour OpenAI Agents: https://docs.restate.dev/tour/openai-agents
- Installation: https://docs.restate.dev/installation

### Contexte projet

- Plan principal: `plannings/ROBUSTIFICATION_DGX_SPARK_PLAN.md`
- Issues concernées: #6, #7, #46, #47
- Architecture: `CLAUDE.md`

### Comparables

- LangGraph checkpointing (alternative à évaluer si Restate rejeté)
- OpenAI Agents SDK native retry (déjà utilisé)

---

## Conclusion

Ce POC vise à **valider factuellement** si Restate apporte une valeur mesurable pour le système agentic-research dans le contexte DGX Spark.

**Principe YAGNI** : Si le plan de robustification v2.3.2 résout les problèmes, Restate n'est peut-être pas nécessaire maintenant.

**Principe de précaution** : Si Restate montre des gains clairs (résilience, observabilité), son adoption peut prévenir de futurs problèmes et faciliter l'évolution du système (multi-agents, human-in-the-loop).

**Durée totale estimée** : 6-10h (réparties sur 1-2 jours)

**Go/NoGo** : À décider après expérimentation et analyse des résultats.
