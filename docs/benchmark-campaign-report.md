# Benchmark déterministe — rapport de campagne (en cours)

> Document vivant. Dernière mise à jour : 2026-07-16 (après-midi).
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
- [ ] Post-campagne : basculer les endpoints Spark en Responses API (`api: "responses"`
  par endpoint, déjà supporté — ajouté pour gpt-oss/harmony). Historique : Qwen et GLM
  testés OK sur Responses à l'époque, Mistral incompatible, bugs de parsing connus
  (gist d074ae2a421292a07c68667a26b8aa41). Aujourd'hui tous les modèles Spark sont en
  Chat Completions (défaut base_url, issue #158) — cohérent entre eux, on ne change
  rien en cours de campagne.
- [ ] Post-campagne : réutiliser une collection Chroma par couple (corpus × modèle
  d'embeddings) au lieu d'une par run — le corpus gelé est ré-embeddé à chaque run
  (~275 chunks), ce qui sature llama.cpp pendant les batteries parallèles. L'isolation
  des preuves resterait garantie par les hashes de chunks du pack.
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


## 9. Passe propre N=5 (2026-07-16 matin) — résultats après durcissement complet

Embeddings Qwen pour tous, collection dédiée par run, correction ré-exécutée sur
packs archivés après chaque fix (les packs sont re-corrigeables sans relancer les
candidats — la propriété clé du dispositif).

### La revue Codex et l'itération de durcissement

Codex (revue statique, PR #197) a confirmé les fausses fabrications et trouvé
deux bloquants supplémentaires, tous corrigés dans la foulée (tests rouge→vert à
chaque fois) :

| Faux positif | Cas réel observé | Garde ajouté |
|---|---|---|
| Juge finance sans preuves | fichiers runtime renommés vs manifeste canonique → 0 chunk sur les items d'adéquation | nom canonique propagé aux chunks résolus |
| Deltas de synthèse loin des opérandes | « Amazon (+91,7 Md$), devant Alphabet (+69,1)… » | dérivation vérifiée contre les valeurs corpus de la société nommée (quasi-exact) |
| Ratios recalculés | « les Capex/OCF recalculés sont respectivement de 94,5 %… » (aucune société dans le paragraphe) | recomputation précise d'un fait ratio DÉJÀ publié (double condition anti-fortuite) |
| Signe moins binaire | « 131,8 − 40,1 » lu comme −40,1 | moins précédé d'un chiffre = opérateur |
| Convention de précision | « montants arrondis/présentés à 0,1 Md$ » | valeurs ≤1 + vocabulaire d'arrondi |
| Note d'incohérence documentaire | « [S3] indique X indisponible, tandis que les données donnent 133,1 » | une clause qui MONTRE la valeur n'affirme pas une indisponibilité |
| Tableau guidance | « Alphabet, Environ 75, 4 fév. 2025 » accusé contre l'actual 91,4 | en-tête guidance = aucune autorité d'accusation |

À chaque élargissement d'excuse, le filet anti-blanchiment a été re-testé : deux
tentatives d'élargissement ont été retoquées par les tests (un 73 % inventé excusé
par paires fortuites, 4/6 taux inventés par ratios multi-sociétés) et resserrées.
Le contrôle falsifié reste bloqué à 2/2 fabrications attrapées.

### Tableau de campagne (médiane / min / max sur N=5, sauf qwen N=3)

| Modèle | Conceptuel | Finance | Durée méd./run |
|---|---|---|---|
| gpt-5.6-sol (référence) | **81.2** (75.0–87.5) | **95.0** (60.0–97.5) | 202 s / 167 s |
| gpt-5.4-mini | **68.8** (62.5–81.2) | **87.9** (81.8–96.5) | 74 s / 58 s |
| Qwen3.6 (Spark) | **6.2** (6.2–18.8, N=3, 15/07) | **91.9** (40.0–95.0, N=3) | ~150 s / ~160 s |
| MiniMax M2.7 (Spark) | **50.0** (0.0–62.5) | **40.0** (40.0–88.3) | ~550 s / ~650 s |

Lecture :
- **Finance** : qwen3.6 rivalise avec les références quand il reste sobre ; ses 40
  et ceux de MiniMax sont de VRAIES fabrications (agrégats faux, vérifiés à la main
  contre le corpus). MiniMax fabrique dans 3 runs sur 5 — c'est un signal modèle.
- **Conceptuel** : hiérarchie nette 5.6-sol > mini > MiniMax >> qwen3.6. Les échecs
  qwen sont dominés par la discipline de citation (blanchiment, pièges d'honnêteté
  mordus) — le rapport se lit bien mais n'est pas ancré aux preuves.
- Le WRONG résiduel 56sol-capex-3 (2) et les fabs MiniMax méritent une lecture de
  confirmation avant publication.

## 10. Décisions en attente (Pierre)

1. **Politique `evaluation_failed` dans les médianes** (Codex #3) : retry ciblé
   avec feedback de protocole, re-correction, ou exclusion explicite. La doc
   disait « score 0 » ; le code garde un score diagnostique + `qualified=false`.
   Cas observés : erreurs de protocole du juge (chunks non rattachés à la source
   citée) sur ~2 runs conceptuels sur 10.
2. **Contestation few-shot** (Codex #4) : la vérité terrain doit-elle se juger sur
   le contenu brut (Codex) ou sur ce que le pipeline peut récupérer (arbitrage en
   vigueur) ? Statu quo maintenu sauf contre-ordre.
3. **Traçabilité stats.json** (Codex #5) : SHA git, hash de config, nom de
   collection, endpoint embeddings — additif, recommandé avant la campagne large.
4. mm27-concept-1 à 0.0 (`evaluation_failed` + 1 fab conceptuelle) non diagnostiqué.


## 11. Compléments du 16/07 après-midi — Qwen N=5, doctrine « chaîne de preuve », Mistral lancé

### Arbitrages Pierre (définitifs)

- **few_shot** : arbitrage confirmé par lecture de la source primaire (pas de
  définition, un commentaire de code avec une phrase vague — « pas de quoi
  faire un paragraphe ») ; la contestation Codex est close.
- **Le juge est un outil, pas un décideur** : il désigne les chunks qui l'ont
  convaincu ; le CODE possède la table chunk→source et résout l'appariement
  déterministiquement. La classe d'erreur de protocole « chunks non rattachés
  à la source citée » (2 runs/10) est supprimée par construction.
- **Casser sa chaîne de preuve = faute du candidat** : mm27-concept-1 (0.0)
  est COMPTÉ dans la médiane — le 404 venait d'une URL recopiée avec des
  caractères perdus par MiniMax (`…6b0bc6755799` → `…6b6755799`), pas d'un
  incident Medium. Même doctrine pour les doc_ids absents de Qwen (1-2
  recherches sur ~6 dans CHAQUE run conceptuel qwen, systémique) : les items
  concernés sont invérifiables donc perdus — à reporter, pas à réparer.
- **Fallback d'échelle d'unité** : un rapport qui définit sa propre
  abréviation (« milliards de dollars (M$) ») puis écrit « 131,8 M$ » n'invente
  pas un chiffre — le numéral écrit existe dans le corpus. Accepté à ×1000
  quasi exact uniquement (les variantes tolérantes ont été retoquées par les
  tests anti-blanchiment : 4.2x excusé par un 4202 sans rapport).
- Vocabulaire guidance : ajout du français « guide(s) » (« guides initiaux de
  Capex » accusé à tort).

### Qwen3.6 — N=5 définitif

| Exercice | Runs | Médiane |
|---|---|---|
| Conceptuel | 18.8 / 6.2 / 6.2 / 0.0 / 12.5 | **6.2** |
| Finance | 91.9 / 95.0 / 40.0 / 40.0 / 76.9 | **76.9** |

Pattern confirmé 3× en finance : quand Qwen sort du cadre, il invente des
**agrégats approximatifs** (somme OCF « 733,3 » vs 731,8 réel ; « 721,8 » vs
731,8 ; FCF « 359,9 » vs 358,4) — des erreurs d'arithmétique à 1-2 Md$ près,
attrapées par la porte zéro-tolérance. Ses runs sobres valent 76.9-95.

MiniMax conceptuel (0.0 compté) : médiane **50.0**.

### Canal d'influence documenté : le LLM du dataprep

Le serveur dataprep utilise gpt-4.1-mini (API OpenAI) pour extraire mots-clés
et résumé de chaque article AU TÉLÉCHARGEMENT (stockés en base de
connaissances). Pendant la campagne il ne tourne quasiment pas (sources déjà
en base), mais `get_knowledge_entries_tool` expose ces titres/mots-clés/résumés
aux candidats lors du choix des fichiers : ingrédient cloud partagé, identique
pour tous, non indexé dans Chroma. Déclaré ici au titre de la provenance.

### En cours

- Mistral Small 4 (119B, NVFP4) : batterie ×5+×5 lancée — config du spike
  (deux profils : reasoning high sur planification/agenda/orchestration/
  chemin de fer, instruct sur recherche/rédaction ; température 0.1, Chat
  Completions). À surveiller : reproduit-il les pertes de doc_ids de Qwen ?


## 12. Tableau d'exceptions post-examen (arbitrage Pierre, 16/07)

Nouveau mécanisme, inspiré de la contestation de copie : quand la relecture
humaine établit qu'une réponse acceptée a été mal notée, **l'évaluateur n'est
pas modifié** (il est figé, reproductible, et referait la même erreur — c'est
assumé). La note est ajustée à la main dans `evaluations/adjustments.yaml`
(motif, vérification, arbitre, date), et les tableaux de campagne l'appliquent
avec un renvoi. On n'implémente pas de règle pour une exception ; les copies
non contestées ne sont pas revues.

Première entrée : camp-mm27-capex-5, 40.0 → 88.3* — « plus de $357B combinés »
est vrai (357,5 exact, vérifié à la main) mais les sommes de sociétés restent
volontairement hors du catalogue de dérivations (surface de blanchiment) ;
les seuils de bucketing (« capex > 50 % de l'OCF ») excusés de même.

### Classement à jour (médianes N=5, * = ajustement appliqué)

| Rang | Conceptuel | Finance |
|---|---|---|
| 1 | gpt-5.6-sol **81.2** | gpt-5.6-sol **95.0** |
| 2 | gpt-5.4-mini **68.8** | gpt-5.4-mini **87.9** |
| 3 | MiniMax **50.0** | MiniMax **79.2*** (79.2/60.0/88.3/40.0/88.3*) |
| 4 | Qwen3.6 **6.2** | Qwen3.6 **76.9** |

Signature comportementale (marqueurs par 5 rapports finance — réconciliation /
méta-discours / agrégats / conventions de précision / énumérations) :
gpt-5.6-sol 25/2/0/28/4 · MiniMax 21/1/2/1/11 · Qwen 7/0/7/1/13 ·
gpt-5.4-mini 1/0/0/0/1. Lecture : MiniMax écrit comme un gpt-5.x (riche
méta-analyse, d'où sa sensibilité aux mêmes angles morts de l'évaluateur que
la référence) mais « hypothétise » des chiffres (capex-4 : $73.3B/$141.2B
introuvables — vraie faute maintenue) ; Qwen écrit plat, restitue des chiffres
justes quand il reste dans le cadre, invente des agrégats quand il en sort, et
casse sa chaîne de preuve en conceptuel. gpt-4.1 (ancrage bas) en cours pour
positionner chaque open-weight entre les générations.


### Ressources par run (médiane N=5 ; tokens = total toutes phases)

| Modèle | Concept : durée / tokens (in+out) | Finance : durée / tokens (in+out) |
|---|---|---|
| gpt-5.6-sol | 202 s / 300 k (270+30) | 166 s / 613 k (574+37) |
| gpt-5.4-mini | 74 s / 416 k (389+25) | 58 s / 612 k (585+28) |
| MiniMax M2.7 | 519 s / 374 k (324+50) | 637 s / 604 k (550+62) |
| Qwen3.6 | 140 s / 340 k (317+22) | 165 s / 526 k (497+29) — outlier 1406 s (run 14, agrégats inventés) |

Lectures : volumes de tokens proches entre modèles et dominés ~90 % par
l'input (le retrieval coûte, pas la génération — le pipeline égalise bien) ;
la SORTIE trahit le style (MiniMax 50-62 k = verbosité frontier, cohérent avec
sa signature réconciliation) ; gpt-5.6-sol consomme MOINS que mini en
conceptuel (recherches plus efficaces).
