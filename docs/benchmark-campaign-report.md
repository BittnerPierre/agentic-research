# Benchmark déterministe — rapport de campagne (en cours)

> Document vivant. Dernière mise à jour : 2026-07-16 (nuit du 15 au 16).
> Branche : `feat/201-evidence-bound-validator` — issues #196, #201, #202, #203.

## 1. Objectif et dispositif

Comparer des modèles medium (Spark/vLLM : Qwen3.6, MiniMax, Mistral, GLM…) et des
modèles cloud (GPT-5.4-mini, GPT-5.5/5.6) sur deux exercices fermés, avec une
évaluation **reproductible** et **ancrée aux preuves** :

- **Finance** (`ai-capex-intensity`) : data pack chiffré sur 6 sociétés, corpus gelé
  (5 fichiers, hashés). Scorer **déterministe** : couverture de 42 faits, exactitude,
  porte fabrication zéro-tolérance, whitelist corpus + dérivations (deltas, %),
  root-cause par étape (retrieval / writer / contrat).
- **Conceptuel** (`ai-engineering-syllabus`) : brief d'onboarding IA depuis 5 articles
  publics gelés. Grille fermée de 16 exigences jugées par **LLM-as-judge épinglé**
  (gpt-5.4-2026-03-05) en protocole juge → contradicteur, evidence-bound : un pass
  exige une citation dont les **chunks bruts archivés** entaillent l'explication.
- Chaque run produit un **pack de preuves** re-adjudicable : `report.md`,
  `stats.json` (timings + tokens par étape), `sources.json`, `chunks.json`
  (chunks bruts hashés, validés contre le manifeste gelé), `raw_sources/`.

### Principes actés (arbitrages Pierre)

| Principe | Traduction opérationnelle |
|---|---|
| Le déterministe juge les chiffres, le LLM juge le texte | Python ne fait plus AUCUNE vérification texte-contre-texte (citations verbatim, [Sx]-dans-la-citation → supprimées) ; il garde les ensembles fermés : hashes, IDs de chunks, provenance |
| « Les en-têtes peuvent aider, jamais accuser » | Tables : lignes canoniques identifiées par CONTENU = pleine autorité (accusations) ; lecture par en-têtes = crédit de couverture seulement |
| Un junior peut se tromper d'analyse, pas de chiffre | Prose : vérification d'EXISTENCE des chiffres dans le corpus + dérivations ; l'analyse revient au juge |
| Jamais de reasoning sur le juge | Validations niveau gpt-3.5 ; le reasoning asphyxiait le budget de sortie (troncatures observées) → `reasoning_effort: none` partout |
| Invariance du scoring | Prouvée par test automatique : 3 rescores du même rapport → JSON identiques |
| Variance = indicateur | **N=5 runs** par modèle et par exercice (arbitrage 2026-07-16 : 3 est fragile vu la variance comportementale et le bruit de juge ±6 pts), médiane/min/max ; temps + tokens par étape déjà dans stats.json |
| Fail-closed | Pas de clé API, juge tronqué, contrat non conforme → score 0 + `evaluation_failed`, jamais de qualification silencieuse |

## 2. Calibration finance (référence cloud, 2026-07-15)

Après la doctrine « option 2 » (commit `4a7d6f1`) :

| Rapport | Score | Couverture | Faux chiffres | Fabrications |
|---|---|---|---|---|
| gpt-5.4-mini r1 | 84.5 | 35/42 | 0 | 0 |
| gpt-5.4-mini r2 | 94.6 | 40/42 | 0 | 0 |
| gpt-5.4-mini r3 | 97.5 | 42/42 | 0 | 0 |
| gpt-5.4 full | 85.4 | 36/42 | 0 | 0 |
| qwen3.6 run8 | 93.3 | 42/42 | 0 | 0 |
| qwen3.6 run9 | 40.0 | 18/42 | 4 (réels, vérifiés) | 1 |
| qwen3.6 run10 | 40.0 | 42/42 | 0 | 2 (réelles) |
| contrôle falsifié | 40.0 | — | — | 2 → **bloqué** ✓ |

- Zéro fausse accusation sur les rapports honnêtes (on partait de 9 sur gpt-5.4 full).
- La variance de la référence (84.5→97.5) est **entièrement expliquée par la
  couverture du retrieval** (35→40→42 faits remontés sur des runs identiques).
- Tolérance dérivation delta resserrée à quasi-exact (0.15 abs / 0.5 % rel) après
  qu'une paire fortuite du corpus (83.0−3.2≈79.8) a failli blanchir un 80.3 inventé.

## 3. « Le pompon » : l'ingestion censurait le sujet du corpus (2026-07-15)

**Découverte** : les modèles de pointe (gpt-5.4-mini 62.5, gpt-5.5 50.0) déclaraient
des « trous de source » sur few-shot, ChromaDB, function calling, error handling —
alors que le corpus les couvre. Cause : **trois filtres à mots-clés** introduits le
2026-02-13 (commit `6f8f7df`, ère du premier benchmark) pour purger des artefacts
d'agents qui avaient contaminé la base :

1. `clean_for_rag` supprimait **tous les blocs de code** → Building_Systems perdait
   87 % de son contenu (tout l'article est en exemples) ; les exemples Chroma et
   few-shot n'existaient que là.
2. `_ARTIFACT_RE` (indexation) et `_PROMPT_ARTIFACT_RE` (recherche) jetaient tout
   chunk contenant « system prompt », « You are a », « BEGIN », « END » (substring
   sans borne : « END » matche « RECOMMENDED ») → **censure du sujet même de
   l'exercice** (le prompting).
3. Les marqueurs de pied de page coupaient TOUT le document après un match
   n'importe où dans la ligne : un exemple de prompt « Primary categories:
   Billing… » tronquait 90 % de Building_Systems.

**Fix** (commit `6a90942`, tests de régression rouge→vert) : contenu des blocs de
code conservé, filtres artefacts supprimés (les critères structurels restent :
longueur, ratio symboles, spam de liens), marqueurs ancrés en début de ligne.

**Effet mesuré** : 109 → **275 chunks** indexés, zéro terme-clé perdu, ~97 % de
chaque document préservé. Référence gpt-5.5 : **50.0 → 81.2** (couverture 8/16 →
13/16) sur le même exercice.

**Leçon** : le contrat de notation conceptuel avait été gelé sans dry-run de
récupérabilité (même erreur que le finance). Contre-mesure désormais appliquée :
vérification concept-par-concept que chaque item du must_cover est récupérable en
top-k avant de geler un pipeline.

### Reclassement `few_shot` → piège d'honnêteté

Vérité terrain : le corpus ne DÉFINIT jamais le few-shot — il ne le montre que dans
des commentaires de code, hors de portée du retrieval (aucune requête plausible ne
les classe en top-12). Arbitrage : `few_shot` rejoint `zero_shot` en `source_gap` —
la bonne réponse est « les sources ne l'expliquent pas », les chunks de code sont
des **distracteurs assumés**, et fournir une définition de mémoire = échec.
Syllabus et sources inchangés.

## 4. Stabilité du juge (3 passes sur le même pack gpt-5.5)

| Item | P1 | P2 | P3 |
|---|---|---|---|
| 14 items / 16 | identiques sur les 3 passes | | |
| orchestration | needs_review | fail | fail |
| source_discipline | pass | fail | needs_review |

- Les pass nets et fails nets ne bougent **jamais**. Le bruit du juge se concentre
  sur les cas limites, surtout `source_discipline` (jugement « rapport entier »,
  le plus subjectif de la grille).
- Score selon la passe : 81.2 / 75.0 / 75.0. La règle « médiane sur N runs » absorbe (d'où N=5).
- Conséquence opérationnelle : un écart entre deux modèles porté uniquement par
  `source_discipline` est du bruit de juge, pas du signal.

## 5. Batterie Qwen3.6 (2026-07-15 soir — embeddings Qwen, pipeline corrigé)

### Finance ×3 : 91.9 / 95.0 / 40.0 — médiane **91.9**

- Runs 11-12 : 41-42/42, 0 faux chiffre, 0 fabrication. Excellent.
- Run 13 : le modèle a calculé des **agrégats non demandés** sur les 6 sociétés et
  s'est trompé : « OCF combiné 721,8 Md$ » (vraie somme : **731,8**), croissances
  capex « +58 %/+59 %/+45 % » (vraies valeurs agrégées : +20,6 % puis +49,4 %).
  Fabrications réelles, porte zéro-tolérance à raison.

### Conceptuel ×3 : 18.8 / 6.2 / 6.2 — effondrement révélateur

Le rapport **se lit bien** (Chroma, ReAct, checkpointing, erreurs composées…) mais :

1. **Les deux pièges d'honnêteté ont mordu** : zero-shot et few-shot définis de
   mémoire et attribués à [S1] dont les chunks ne contiennent rien de tel
   (blanchiment de citation).
2. **Discipline de citation défaillante** : les chunks des sources citées
   n'entaillent pas les affirmations (gpt-5.4-mini : 10/16 sur le même exercice
   en citant juste). C'est le cœur de ce que le benchmark mesure.
3. **Artefact d'interface (ouvert)** : la recherche S2 est revenue sans doc_ids
   (0 lien vers les 55 chunks valides du pack) → toute la section RAG inciteable.
   Fragilité de formatage petit-modèle, même famille que les shims v2.1.

### Comparatif conceptuel à date (pipeline corrigé)

| Modèle | Score | Couverture | Pièges d'honnêteté | Fabrication |
|---|---|---|---|---|
| gpt-5.5 (réf.) | 75.0–81.2 | 12-13/16 | zero-shot ✓ déclaré, few-shot ✗ défini de mémoire | 0 |
| gpt-5.4-mini | 62.5 | 10/16 | déclare PUIS définit quand même (blanchi) | 0 |
| qwen3.6 | 6.2–18.8 | 1-3/16 | les deux définis de mémoire | 0 |

## 6. Tweaks nécessaires pour Qwen3.6 (à documenter dans la campagne)

Empilés pour obtenir des runs complets (v2.1, commit `82d3f7f`) :
retrait `--async-scheduling` vLLM (bug xgrammar #29379), temperature 0.2,
ligne de prompt « URLs exactes, jamais un nom reconstruit », shim zéro-arg
`get_knowledge_entries_tool` (double-emballage `{"arguments": "{}"}`),
fallback décimales FR 3 chiffres dans le scorer.

## 7. Points ouverts

- [ ] `evaluation_failed` du run conceptuel qwen-1 (18.8) non diagnostiqué.
- [ ] doc_ids absents sur une recherche (S2, qwen) : shim ou perte assumée ? À trancher.
- [ ] Résidu « judge protocol validation failed » historique (qwen10 finance) — différé.
- [ ] Verdicts d'adéquation finance jamais relus systématiquement — différé post-campagne.
- [ ] Idée v-suivante : LLM-mappeur d'en-têtes de tableaux (#201).
- [ ] Warnings Pydantic (sérialisation des réponses SDK dans judge_io) — cosmétique.

## 8. Prochaines étapes (passe propre campagne)

Embeddings **identiques pour tous** (Qwen3-Embedding@spark1:8003, llama.cpp),
collection Chroma dédiée par run, pipeline gelé (commit `6a90942`), **N=5 par
exercice**, médiane/min/max + temps et tokens par étape :

- [ ] gpt-5.6-sol (nouvelle référence) — concept ×5 + finance ×5
- [ ] gpt-5.4-mini — concept ×5 + finance ×5
- [ ] MiniMax 2.7 (Spark, lancé par Pierre) — concept ×5 + finance ×5
- [ ] Qwen3.6 — compléter à 5 sur pipeline gelé
- [ ] Mistral Small 4 (au swap Spark), Qwen3.5-122B quand servi
