# Restate POC Results - Writer agent

Status: DRAFT  
Version: 0.1.0  
Date: 9 fevrier 2026  
Issue: https://github.com/BittnerPierre/agentic-research/issues/69

---

## 1. Contexte

Objectif: comparer le Writer agent baseline avec une version Restate-enabled
sur resilience, observabilite, et overhead.

---

## 2. Environnement et configuration

- Machine: Mac local (test manuel) + DGX Spark (a venir)
- Restate Server: 1.6.0 (binaire local), stockage par defaut
- SDK Restate: 0.14.2
- Modeles LLM: gpt-oss-20b-mxfp4.gguf via gx10-957b:8002
- Config agentic-research: configs/tests/config-dgx-remote.yaml

---

## 3. Scenarios executes

| Scenario | Description | Runs | Baseline succes | Restate succes |
| --- | --- | --- | --- | --- |
| Nominal | Aucune erreur | 1 (local) | n/a | succes (sortie generee) |
| Timeout LLM | Timeout sur 2e call | TBD | TBD | TBD |
| Tool error | save_report echoue 1 fois | TBD | TBD | TBD |
| JSON truncation | sortie invalide | TBD | TBD | TBD |
| Crash process | kill pendant execution | 1 (local) | n/a | succes (reprise) |

Notes:
- Chaque scenario doit avoir >= 3 runs.
- Indiquer les seed si pertinent.

---

## 4. Metriques minimales

Resilience:
- Taux de succes par scenario (baseline vs Restate).
- Nombre de retries par run.

Overhead:
- Temps total par run (ms).
- Delta moyen (Restate - baseline).

Observabilite:
- Qualite des traces (notes qualitatives).
- Temps moyen pour diagnostiquer un incident.

---

## 5. Resultats (a remplir)

### 5.1 Resilience
- Baseline succes: TBD
- Restate succes: 1/1 (local smoke test)
- Gain relatif: TBD

### 5.2 Overhead
- Temps nominal baseline: TBD
- Temps nominal Restate: TBD
- Delta: TBD

### 5.3 Observabilite
- Resume comparatif (Restate UI vs logs actuels): n/a (local smoke test)
- Exemples de traces utiles (captures si possible): a collecter

### 5.4 Notes test manuel local
- Restate en container (ports 8080/9070), writer expose en local et enregistre via IP host.
- Invocation Restate OK (HTTP ingress 8080, handler `run`).
- Sortie LLM generee mais demande des fichiers de recherche (search_results vide).
- Test utile pour valider l integration Restate + DGX, pas la qualite du writer.
- Crash test: invocation asynchrone lancee, service arrete puis relance, invocation terminee avec succes.

---

## 6. Risques et mitigations

| Risque | Impact | Probabilite | Mitigation |
| --- | --- | --- | --- |
| Restate incompatible DGX | Bloquant | Faible | Tester le setup en phase 1 |
| Refactor trop complexe | Retard | Moyen | Limiter au writer agent |
| Pas de gain mesurable | Temps perdu | Moyen | Accepter resultat negatif |
| Overhead inacceptable | Rejet | Faible | Mesurer des les premiers tests |

---

## 7. Decision Go/NoGo

### Criteres de decision
- Resilience: Restate > baseline de 20% sur scenarios d erreur.
- Observabilite: debug plus rapide via Restate UI.
- Overhead: +10% max temps nominal, refactor <= +50 LOC.

### Decision
- Decision: TBD (Go / NoGo)
- Justification: TBD

---

## 8. Prochaines etapes

- Si Go: planifier l extension Restate aux autres agents.
- Si NoGo: documenter l ADR et alternatives.

---

## 9. Resume pour issue 69 (brouillon)

Etat:
- Execution planifiee ou executee: TBD
- Resultats captures: TBD
- Decision: TBD

Message propose:

Restate POC (Writer agent) - point d etape

Execution:
- Phases 1-4: TBD
- Scenarios executes: TBD
- Metriques capturees: TBD

Resultats:
- Resilience: TBD
- Observabilite: TBD
- Overhead: TBD

Decision:
- Go/NoGo: TBD
- Next steps: TBD
