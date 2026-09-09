# Note de décision — spike #235 : IA frontier + skill vs workflow orchestrant des modèles petits/moyens

*Brouillon en cours de rédaction : les sections marquées « à compléter » sont remplies à la fin du spike, après la campagne.*

## 1. Question

Une IA frontier dotée d'un bon harnais et d'un skill bien établi fait-elle mieux qu'un workflow agentique
orchestrant des modèles petits ou moyens, sans intervention humaine et avec une faible déviance, à l'échelle
(coût par livrable, débit) ? Grandeur mesurée : la dispersion sur N=5 (séquence de lettres, couverture min–max,
échecs, interventions humaines), pas la performance de pointe.

## 2. Dispositif

- **Skill** `document-research` (standard Agent Skills) : 8 étapes, un livrable par étape, main courante, extraits verbatim, arbitrages de la §9 du cadrage. Développé à l'aveugle des exercices du banc, testé sur un thème tiers (kéto).
- **Harnais** : Claude Code headless (`claude -p`), modèle Claude Fable 5.1, sous-agents autorisés, Bash et web interdits, lecture du dépôt refusée.
- **Bras A** : fonds = fichiers locaux (Read/Grep/Glob). **Bras B** : fonds = base de connaissances dataprep via MCP (acquisition, indexation, catalogue, `vector_search` ajouté par un serveur compagnon).
- **Adaptateur banc** : traduit le dossier de travail en pack notable ; le skill ne connaît pas le contrat.
- **Mesure** : une seule campagne en fin, N=5 × 2 exercices × 2 bras, évaluateur inchangé, seconde lecture ; coût par run à prix liste et débit (5 runs en parallèle).

## 3. Résultats — évaluation ouverte (thème tiers)

À compléter : lecture par grille, pièges d'honnêteté, dispersion entre runs.

## 4. Résultats — banc déterministe

À compléter : tableau lettres + couverture avec les lignes workflow existantes (§15/§25/§29), colonnes coût par run et débit.

## 5. Ce que le skill a appris au harnais (et l'inverse)

À compléter : retex des runs, ce qui vient « gratuitement » du harnais (sous-agents, replanification, relecture), ce qui a manqué (recherche vectorielle en MCP, contrat de pack, répétabilité).

## 6. Décision

À compléter : skills/MCP/harnais, workflows, ou hybride ; pourquoi ; avec les dispersions.

## 7. Limites et suites

À compléter.
