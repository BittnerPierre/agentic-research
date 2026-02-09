# Plan d execution POC Restate - Writer agent

Version: 1.0.0  
Date: 9 fevrier 2026  
Scope: Writer agent uniquement  
Issue: https://github.com/BittnerPierre/agentic-research/issues/69

---

## 1. Resume du plan existant

### Objectifs primaires
1. Comparer la resilience du Writer avec et sans Restate face a des erreurs simulees.
2. Evaluer l observabilite (Restate UI vs logs actuels).
3. Mesurer l overhead (integration, complexite, perf).

### Objectifs secondaires
4. Valider la compatibilite OpenAI Agents SDK + Restate + DGX Spark.
5. Identifier les limites d usage ou d utilite.

### Criteres de decision (Go/NoGo)
- Resilience: taux de succes Restate > baseline de 20% sur scenarios d erreur.
- Observabilite: debug plus rapide via Restate UI que logs actuels.
- Overhead: +10% max en temps nominal, refactor <= +50 LOC, setup <= 30 min.

---

## 2. Dependances et prerequis

- Acces a une machine DGX Spark avec le service agentic-research operationnel.
- Restate Server installable (binaire ou Docker).
- SDK Restate Python installe via Poetry.
- Acces aux logs actuels (LangSmith, OpenAI traces).
- Scenarios de test deterministes pour la comparaison.

---

## 3. Execution detaillee

### Phase 1: Setup infrastructure (1-2h)

Objectif: Restate Server disponible et accessible depuis le service.

Taches:
- [ ] Installer Restate Server (binaire ou Docker).
- [ ] Installer le SDK Restate via Poetry.
- [ ] Verifier la connectivite et l acces a la UI Restate.

Entrees:
- Acces DGX Spark + droits d installation.

Sorties:
- Restate Server en fonctionnement.
- SDK installe et importable.

Validation:
- UI Restate accessible.
- Le service se connecte au serveur Restate.

---

### Phase 2: Refactor Writer agent (2-3h)

Objectif: creer un writer Restate-enabled en parallele du baseline.

Taches:
- [ ] Creer un agent Restate base sur `src/agents/file_writer_agent.py`.
- [ ] Integrer DurableRunner pour les appels LLM.
- [ ] Wrapper les tools critiques avec durable_function_tool.
- [ ] Exposer le service Restate (handler).

Points d integration:
- `src/agents/file_writer_agent.py` (baseline).
- Nouveau fichier attendu: `src/agents/file_writer_agent_restate.py`.

Sorties:
- Writer Restate fonctionnel et enregistrable.

Validation:
- Le code importe sans erreur.
- Le service apparait dans la UI Restate.

---

### Phase 3: Test harness de comparaison (1-2h)

Objectif: comparer baseline vs Restate sur scenarios controles.

Taches:
- [ ] Creer un test d integration (ex: `tests/integration/test_writer_restate_comparison.py`).
- [ ] Implementer l injection d erreurs controlees.
- [ ] Capturer les traces et metrics (temps, retries, succes).

Sorties:
- Tests de comparaison reproductibles.

Validation:
- Au moins un scenario nominal et un scenario d erreur passent.
- Traces disponibles pour comparaison.

---

### Phase 4: Experimentation et capture des resultats (2-3h)

Objectif: executer les scenarios et capturer les donnees.

Taches:
- [ ] Lancer 3 runs par scenario (nominal, transitoires, persistantes, crash).
- [ ] Capturer succes, latence, retries, qualite des traces.
- [ ] Documenter les observations et metrics.

Sorties:
- Resultats consolides dans `plannings/RESTATE_POC_RESULTS.md`.

Validation:
- Donnees completes pour chaque scenario.
- Comparaison baseline vs Restate possible.

---

## 4. Livrables attendus

1. `plannings/RESTATE_POC_RESULTS.md` (resultats et decision).
2. ADR (si decision finale prise).
3. Notes de comparaison (traces, captures).

---

## 5. Calendrier propose

- Jour 1: Phases 1-2 (setup + refactor).
- Jour 2: Phases 3-4 (tests + experimentation).

---

## 6. Critere de cloture issue 69

- Plan d evaluation execute ou planifie avec etapes claires.
- Resultats documentes et liees a l issue #69.
