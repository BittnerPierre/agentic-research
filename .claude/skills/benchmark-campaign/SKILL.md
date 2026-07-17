---
name: benchmark-campaign
description: >-
  Orchestre le workflow complet du benchmark déterministe de ce repo :
  pré-vol des services (ChromaDB, dataprep MCP, embeddings Spark, vLLM),
  batteries de runs agentic-research (1 à n, défaut 5) sur les exercices
  Finance (ai-capex-intensity) et Conceptuel (ai-engineering-syllabus),
  correction complète (scorer déterministe + juge), SECONDE LECTURE des
  échecs (vrai défaut du candidat vs faux positif de l'évaluateur),
  re-notation des packs archivés, tableau d'exceptions post-examen, et
  compilation du podium à deux dimensions (lettres de confiance +
  couverture, durées, tokens). Utiliser ce skill dès que l'utilisateur veut
  lancer un benchmark, tester un modèle (Qwen, Mistral, MiniMax, GPT-x…),
  refaire une campagne, re-noter des runs, vérifier les scores, comparer
  des modèles ou compiler un tableau de résultats — même s'il ne prononce
  pas le mot « benchmark ».
---

# Benchmark Campaign

Workflow éprouvé sur la campagne de juillet 2026 (~80 packs, 7 modèles).
Le rapport de référence est `docs/benchmark-campaign-report.md` ; les
doctrines qui suivent y sont documentées avec leurs exemples.

## Vue d'ensemble d'une campagne pour UN modèle

```
1. Pré-vol        evaluations/campaign/scripts/check_services.sh [--spark]
2. Config         configs/tests/config-<modele>-chroma-decomposed.yaml
3. Batterie       evaluations/campaign/scripts/run_battery.sh <config> <tag> <finance|concept|both> [N]
4. Seconde lecture   (voir section dédiée — OBLIGATOIRE avant de publier)
5. Exceptions     evaluations/adjustments.yaml (décision utilisateur)
6. Tableau        evaluations/campaign/scripts/compile_table.py --models "Label=tag" ... [--flags]
```

> L'outillage vit dans `evaluations/campaign/` (il fait partie du projet et se
> distribue avec — sans lui le benchmark ne s'exécute pas) ; ce SKILL.md n'est
> que le déclencheur/mode d'emploi pour Claude Code.

Après toute MODIFICATION de l'évaluateur : `scripts/regrade.py` (qui exécute
d'abord la suite de tests ET le contrôle falsifié, puis re-note les packs).

## 1. Pré-vol (services)

```bash
evaluations/campaign/scripts/check_services.sh          # campagne cloud
evaluations/campaign/scripts/check_services.sh --spark  # modèle Spark
```

Règles :
- **Ne jamais démarrer/arrêter un service soi-même** : proposer la commande
  à l'utilisateur et attendre son go (règle actée après incident).
- Le serveur dataprep porte la config d'embeddings **au démarrage** : si la
  campagne change d'embeddings, il doit être relancé avec la bonne config
  (par l'utilisateur). Les modèles cloud et Spark doivent partager le même
  endpoint d'embeddings pour que le retrieval soit comparable.
- vLLM ne sert qu'UN modèle à la fois : vérifier lequel avant une batterie
  Spark (le script l'affiche). Les swaps de modèle sont faits par
  l'utilisateur.
- Une collection Chroma est créée PAR RUN (nom = nom du run) : jamais de
  réutilisation entre modèles d'embeddings différents (dimensions
  incompatibles, ex. 2560 Qwen vs 1536 OpenAI).

## 2. Configs

Une config par modèle dans `configs/tests/` (copier la plus proche) :
- Spark : `base_url: http://spark1:8000/v1`, `api_key: dummy` (Chat
  Completions par défaut), température selon modèle (Qwen 0.2, Mistral 0.1),
  `reasoning_effort` par profil si hybride (pattern Mistral : high sur
  planification/agenda/orchestration/chemin de fer, none sur
  recherche/rédaction).
- Communs : embeddings de campagne (`chroma_embedding_*`), `top_k: 12`,
  `client_timeout_seconds: 300` (l'indexation initiale dépasse 10 s).

## 3. Batterie

```bash
evaluations/campaign/scripts/run_battery.sh \
  configs/tests/config-<modele>.yaml camp-<modele> both 5
```

- N est libre (1 pour un smoke test, 5 pour la campagne officielle —
  médiane/min/max exigent N≥3, la variance comportementale rend N=5 robuste).
- Lancer en arrière-plan (les runs Spark prennent 5-12 min chacun).
- Le script résout les dossiers de run par `stats.json → output_dir`
  (autoritaire) — ne JAMAIS se fier au « dernier dossier créé » (collision
  observée entre deux batteries parallèles).
- Cloud + Spark peuvent tourner en parallèle (endpoints différents) ; deux
  batteries Spark, non (un seul vLLM).

## 4. Seconde lecture (OBLIGATOIRE avant publication)

AUCUN score n'est accepté sans lire ce qui l'a causé. La boucle, pour chaque
run non-A (`compile_table.py --flags` liste les items) :

1. **Lire** les items accusés (fabrications, WRONG) dans le résumé ou
   `det_grade.json`.
2. **Re-vérifier contre la vérité terrain À LA MAIN** : recalculer depuis
   `evaluations/exercises/*/corpus/key_metrics.csv` (sommes, croissances,
   ratios). Un chiffre accusé peut être exact (delta, ratio recalculé, somme).
3. **Classer** :
   - vrai défaut du candidat → on garde, on documente dans le rapport ;
   - faux positif de l'évaluateur → nouvelle famille : test ROUGE d'abord
     (le cas réel réduit en fixture), garde minimal dans l'évaluateur, puis
     `regrade.py` (qui vérifie suite + contrôle falsifié + re-note).
4. **Contre-test d'équité** : après un garde, vérifier que les vrais défauts
   des AUTRES modèles tiennent toujours (leurs 40 doivent rester des 40).

Familles de faux positifs déjà rencontrées (ne pas re-découvrir — voir
`evaluations/campaign/false-positive-catalog.md` pour le détail et les extraits) :
deltas loin des opérandes, ratios recalculés, signe moins binaire,
conventions d'arrondi, méta-discours sur les sources, tableaux guidance,
dates, synthèses multi-sociétés, localisateurs de citation, échelles
d'unité, seuils hedgés, fourchettes, vocabulaire guidance français.

Pièges CONNUS du filet anti-blanchiment (ils ont déjà mordu) : élargir une
excuse avec des tolérances larges ou des paires multi-sociétés blanchit des
chiffres inventés — le contrôle falsifié DOIT rester à 3/3 après chaque
changement, c'est non négociable.

## 5. Exceptions post-examen

Quand une réponse est VRAIE mais qu'aucune règle générale saine n'existerait
pour l'excuser (ex. somme multi-sociétés exacte) : on NE MODIFIE PAS
l'évaluateur. On propose à l'utilisateur une entrée dans
`evaluations/adjustments.yaml` (score ajusté, motif, vérification manuelle,
arbitre, date). L'évaluateur referait la même erreur : c'est assumé. Les
copies non contestées ne sont pas revues. `compile_table.py` applique les
ajustements automatiquement (marqués `*`).

## 6. Tableau et lecture des résultats

```bash
uv run python evaluations/campaign/scripts/compile_table.py \
  --models "gpt-5.6-sol=camp-56sol" "Mistral=camp-mistral" --flags
```

Présentation officielle (arbitrage utilisateur) : **séquence de lettres de
confiance + couverture médiane**, jamais un score unique. Sémantique :
A propre · C ≥1 chiffre faux (à relire) · D une invention (récupérable en
relecture attentive) · F inventions multiples (rapport mort). Les lettres ne
s'agrègent pas : on montre la séquence (la variance à l'œil nu). Podium trié
F > D > C > couverture. Le score 0-100 reste disponible en annexe.

Doctrines de comptage :
- **Casser sa chaîne de preuve = faute du candidat** (URL corrompue → 0.0
  compté ; doc_ids absents → items perdus). À reporter, pas à réparer.
- **Zèle** : un calcul hors consigne EXACT est excusé mécaniquement (les
  dérivations couvrent) ; un calcul hors consigne FAUX est flaggé. Rien à
  faire de spécial.
- Un run `evaluation_failed` pour panne de VALIDATION DE PREUVES est compté ;
  un `evaluation_failed` pour panne de protocole du juge se re-corrige
  (relancer la correction du pack suffit en général).

## Résultats de référence (calibration)

Ordres de grandeur attendus si tout va bien (campagne 07/2026) :
gpt-5.6-sol A×5 / cov 100 % (finance) et 87.5 % (concept) ; gpt-5.4-mini
A×5 / 85.7 et 68.8. Si une référence sort avec des lettres D/F, suspecter
d'abord une NOUVELLE famille de faux positifs (le modèle le plus fort frappe
le plus fort les angles morts de l'évaluateur), pas le modèle.

## Fichiers

- `evaluations/campaign/scripts/check_services.sh` — pré-vol
- `evaluations/campaign/scripts/run_battery.sh` — batterie N runs + correction
- `evaluations/campaign/scripts/regrade.py` — garde-fous (tests + contrôle falsifié) + re-notation
- `evaluations/campaign/scripts/compile_table.py` — tableau lettres+couverture (+ --flags)
- `evaluations/campaign/false-positive-catalog.md` — catalogue des familles connues
- `evaluations/controls/fabricated_report.md` + `host_run/` — le contrôle falsifié (3 chiffres plantés, hôte épinglé)
- `evaluations/adjustments.yaml` — registre des exceptions post-examen
