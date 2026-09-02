---
name: benchmark-campaign
description: >-
  Orchestre les campagnes du benchmark déterministe de CE repo (exercices
  Finance ai-capex-intensity et Conceptuel ai-engineering-syllabus) : pré-vol
  des services (ChromaDB, dataprep MCP, embeddings, vLLM), batteries de runs
  agentic-research (1 à n, défaut 5), correction (scorer déterministe + juge
  evidence-bound), SECONDE LECTURE obligatoire des verdicts, exceptions
  post-examen, et podium à deux dimensions (lettres de confiance +
  couverture). Utiliser ce skill pour lancer ou refaire une campagne de
  benchmark, re-noter des packs, vérifier des scores de campagne, comparer
  des modèles sur CES exercices ou compiler un tableau de résultats. NE PAS
  l'utiliser pour un simple test de connectivité, un smoke test d'API ou la
  mise au point d'une config de modèle hors benchmark.
---

# Benchmark Campaign

Workflow éprouvé sur la campagne de juillet 2026 (~90 packs, 8 modèles).
Ce dossier (`evaluations/campaign/`) est le package du skill au format Agent
Skills : ce SKILL.md est le point d'entrée, les `scripts/` et `references/`
vivent à côté. Le rapport `docs/benchmark-campaign-report.md` documente les
doctrines avec leurs exemples.

## Contrat : une campagne ne modifie JAMAIS le code base

Une campagne s'exécute avec le protocole et l'outillage existants — sans
coder, sans toucher à `src/`, aux évaluateurs, aux exercices ni aux gels.

- **Écritures normales d'une campagne** : `output/`, `benchmarks/`,
  collections Chroma, logs. Rien d'autre.
- **Écritures sur go explicite de l'utilisateur uniquement** (fichiers suivis
  par git) : une nouvelle config `configs/tests/` (via `new_model_config.py`
  — proposer, attendre le go, puis générer) ; une entrée d'exception dans
  `evaluations/adjustments.yaml` (proposer l'entrée complète, attendre le go).
- **Jamais pendant une campagne** : modifier l'évaluateur, un corpus gelé, un
  manifeste ou un answer_key. Un défaut découvert (faux positif, drift de
  corpus, bug d'outillage) se SIGNALE — issue ou exception proposée — et sa
  correction est une tâche de développement séparée (issue, branche, go).
- Les services (Chroma, dataprep, embeddings, vLLM) sont démarrés/arrêtés par
  l'utilisateur : proposer la commande et attendre (règle actée après incident).

## Vue d'ensemble d'une campagne pour UN modèle

```
0. Modèles        evaluations/campaign/scripts/list_models.py [--services] [--config <cfg>]
1. Pré-vol        evaluations/campaign/scripts/check_services.sh [--spark] [--config <cfg>]
2. Config         configs/tests/config-<modele>-chroma-decomposed.yaml
3. Batterie       evaluations/campaign/scripts/run_battery.sh <cfg> <tag> <finance|concept|both> [N]
4. Seconde lecture   references/doctrines.md — OBLIGATOIRE avant de publier
5. Exceptions     evaluations/adjustments.yaml (proposition → go utilisateur)
6. Tableau        evaluations/campaign/scripts/compile_table.py --models "Label=tag" ... [--flags]
```

Après toute modification de l'évaluateur (hors campagne, dans sa tâche de
dev) : `regrade.py` exécute la suite de tests ET le contrôle falsifié, puis
re-note les packs.

## 1. Pré-vol (services)

Toujours passer `--config` avec la config de campagne : le script vérifie
alors la CONFORMITÉ, pas seulement la disponibilité — modèle servi par vLLM,
endpoint d'embeddings de la config (cloud OpenAI = aucun service local), et
config d'embeddings portée par dataprep (best effort : bloquant si le
processus local est lisible et non conforme ; sinon anomalie loggée, à
vérifier manuellement). Le serveur dataprep porte sa config d'embeddings AU
DÉMARRAGE : s'il n'est pas conforme, l'utilisateur le relance avec la config
de campagne. vLLM ne sert qu'UN modèle à la fois ; les swaps sont faits par
l'utilisateur. Une collection Chroma est créée PAR RUN (nom = nom du run) :
jamais de réutilisation entre modèles d'embeddings différents (dimensions
incompatibles).

## 2. Modèles et configs

Lister les modèles supportés — ne pas les deviner :

```bash
uv run python evaluations/campaign/scripts/list_models.py   # --services --config <cfg> : enchaîne le pré-vol
```

**Piège à éviter avant de payer un run** : un candidat qui partage la famille
d'un juge sémantique épinglé (`answer_key.yaml` de l'exercice) est REFUSÉ au
conceptuel par le garde anti-auto-notation — ex. gpt-5.4 nu est le juge, pas
un candidat ; sa variante mini passe. `list_models.py` et
`new_model_config.py` signalent ce cas.

Pour un NOUVEAU modèle : proposer la config à l'utilisateur, attendre son go,
puis la générer :

```bash
uv run python evaluations/campaign/scripts/new_model_config.py \
  --slug <slug> --model "openai/org/Modele" [--base-url http://spark1:8000/v1]
```

(`--base-url` omis = cloud OpenAI ; aligner ensuite temperature/top_p/
reasoning_effort sur la model card — le fichier généré le rappelle en tête.)

## 3. Batterie

```bash
evaluations/campaign/scripts/run_battery.sh configs/tests/config-<modele>.yaml camp-<modele> both 5
```

- Le script vérifie d'abord le CORPUS GELÉ (hashes du manifeste) et s'arrête
  avant tout appel modèle si un fichier a dérivé — un drift se répare par
  décision utilisateur (re-téléchargement ou re-gel), jamais en campagne.
- N est libre (1 = smoke, 5 = campagne officielle ; médiane/min/max exigent
  N≥3). Lancer en arrière-plan (runs Spark : 5-12 min chacun).
- Résolution des dossiers de run par `stats.json → output_dir` (autoritaire) —
  ne JAMAIS se fier au « dernier dossier créé ».
- Cloud + Spark en parallèle : OK (endpoints différents) ; deux batteries
  Spark, non (un seul vLLM).

## 4. Seconde lecture, exceptions, tableau

Lire `evaluations/campaign/references/doctrines.md` AVANT de publier quoi que
ce soit : boucle d'audit des verdicts (obligatoire, y compris pour les A
inattendus), conduite face à un faux positif (signaler, ne pas corriger),
exceptions post-examen, doctrines de comptage, sémantique des lettres
(A/C/D/F/E), calibration de référence. Présentation officielle : séquence de
lettres + couverture médiane, jamais un score unique.

```bash
uv run python evaluations/campaign/scripts/compile_table.py \
  --models "gpt-5.6-sol=camp-56sol" "Mistral=camp-mistral" --flags
```

## Fichiers

- `scripts/list_models.py` — modèles supportés (+ avertissement famille-juge, `--services`)
- `scripts/new_model_config.py` — génère la config d'un nouveau modèle (après go)
- `scripts/check_services.sh` — pré-vol disponibilité + conformité (`--config`)
- `scripts/verify_corpus.py` — contrôle du corpus gelé (appelé par run_battery)
- `scripts/run_battery.sh` — batterie N runs + correction
- `scripts/regrade.py` — garde-fous (tests + contrôle falsifié) + re-notation (hors campagne)
- `scripts/compile_table.py` — tableau lettres+couverture (+ `--flags`)
- `references/doctrines.md` — seconde lecture, exceptions, comptage, calibration
- `false-positive-catalog.md` — catalogue des familles connues
- `evaluations/controls/fabricated_report.md` + `host_run/` — le contrôle falsifié (3 chiffres plantés)
- `evaluations/adjustments.yaml` — registre des exceptions post-examen
