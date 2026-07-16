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


## 13. Addendum méthodologie — la notation à trois couches et la seconde lecture

Le benchmark précédent reposait sur un LLM-as-judge « classique » : un modèle
notait librement les rapports, personne ne challengeait ses notes, et la
campagne avait fini par mesurer surtout les artefacts du juge (cf. mémoire du
spike : gpt-4.1-mini « 0.95 » vs gpt-4.1 « 0.40 » sur fabrication non
détectée). La méthodologie actuelle superpose trois couches, chacune couvrant
l'angle mort de la précédente.

### Couche 1 — le scorer déterministe (les chiffres)

Python ne juge que des ensembles fermés : hashes de chunks, IDs, provenance
des fichiers, existence des nombres dans le corpus gelé, dérivations
quasi-exactes bornées (deltas/croissances/ratios de la société nommée,
recomputation de faits publiés). Invariance prouvée par test (3 rescores →
JSON identiques). Il est rapide, reproductible — et aveugle au sens : seul,
il sur-accuse le texte libre.

### Couche 2 — le LLM-as-judge « outil » (le texte)

Un bistouri, pas un couteau suisse : juge épinglé (gpt-5.4-2026-03-05, jamais
de reasoning), verdicts catégoriels sur une grille fermée, evidence-bound (un
pass exige des chunks bruts qui entaillent l'explication), protocole
juge→contradicteur, appariements chunk→source résolus par le code (le juge
désigne, il ne comptabilise pas), fail-closed sur tout imprévu. Stabilité
mesurée : 14/16 verdicts identiques sur 3 passes du même pack, le bruit
concentré sur les items « rapport entier ».

### Couche 3 — la seconde lecture frontier (la cohérence)

C'est la couche nouvelle, tenue pendant cette campagne par un modèle frontier
(Claude « Fable ») : après chaque batterie, AUCUN score n'est accepté sans
lecture de ce qui l'a causé. La boucle, appliquée mécaniquement :

1. **Lire les items accusés** de chaque pack (jamais le chiffre seul).
2. **Re-vérifier contre la vérité terrain à la main** — recalculs jetables
   depuis le corpus : « 86,9 % est-il la vraie croissance du capex Meta ? »
   (oui) ; « la somme fait-elle 357,5 ? » (oui) ; « 77,0 existe-t-il ? » (non).
3. **Classer** : vraie faute du candidat (gardée, documentée) vs faux positif
   de l'évaluateur (nouvelle famille).
4. **Durcir sous triple verrou** : test rouge d'abord (le cas réel en
   fixture), garde minimal, puis (a) suite complète, (b) **contrôle falsifié**
   — un rapport piégé qui doit rester bloqué à exactement 2 fabrications ; il
   a retoqué DEUX élargissements trop généreux dans la journée —, (c)
   contre-test d'équité (les vraies fautes des autres modèles doivent tenir).
5. **Re-noter les packs archivés** (jamais relancer les candidats) et pousser.

Quand le cas est légitime mais qu'aucune règle générale saine n'existe
(« plus de 357 Md$ combinés », vrai mais les sommes multi-sociétés sont une
surface de blanchiment), la couche 3 ne code pas : elle escalade à
**l'arbitre humain** via le tableau d'exceptions post-examen (§12) — la
contestation de copie, l'évaluateur restant figé.

### Ce que la seconde lecture a produit sur cette campagne (16/07)

Une quinzaine de familles de faux positifs découvertes et corrigées, chacune
révélée par un modèle différent — preuve que le texte libre a une traîne de
formes sans fin et qu'aucune calibration préalable ne l'épuise :

| Révélée par | Famille (extrait réel) |
|---|---|
| gpt-5.6-sol | deltas de synthèse loin des opérandes (« Amazon (+91,7 Md$), devant Alphabet (+69,1)… ») ; ratios recalculés (« respectivement de 94,5 %… ») ; « arrondis à 0,1 Md$ » ; « [S7] marks all Apple metrics as unavailable, while… retained » ; tableau guidance (« Environ 75 ») accusé contre l'actual 91,4 |
| gpt-4.1 | dates (« 30 juin 2025 » → 30 flaggé) ; synthèses à contrastes (« disponibles pour Alphabet, Meta…, manquantes pour Amazon » → 36 faux WRONG d'un coup) |
| Qwen3.6 | « 131,8 M$ » avec abréviation définie (M$ = milliards) ; « guides initiaux de Capex » (vocabulaire guidance français) |
| MiniMax | « $139.5B − $131.8B » (moins après lettre d'unité) ; « exceeding 50 % » (seuils hedgés anglais) |
| Mistral | « [S1:22,25] » lu 22,25 et « [S1:9,30,53] » lu 93053 (localisateurs de citation) ; « hausses respectives de 86,9 % et 74,1 % » (énumération multi-sociétés) ; « inférieurs à 15 % » (seuil multiple de 5) |

Chaque famille est ancrée par un test de non-régression écrit rouge d'abord
(74 tests au total) ; le contrôle falsifié a été re-vérifié après chaque
changement. Constat central : **plus le modèle est fort, plus il frappe les
angles morts de l'évaluateur** (le méta-texte riche de gpt-5.6-sol l'avait
mis SOUS gpt-5.4-mini avant seconde lecture : pire run 60,0 → 86,4 après).
Sans cette couche, le classement publié aurait été faux — non pas à cause des
modèles, mais de l'évaluateur.

### Résumé de la pile de garanties

| Risque | Couvert par |
|---|---|
| Chiffre inventé | scorer déterministe (porte zéro-tolérance) + contrôle falsifié |
| Texte non ancré aux preuves | juge evidence-bound + contradicteur |
| Juge qui divague | grille fermée, pas de reasoning, appariements résolus par le code, fail-closed |
| Évaluateur qui sur-accuse | seconde lecture frontier (lecture des items + re-vérification terrain) |
| Excuse trop généreuse (blanchiment) | tests rouge-d'abord + contrôle falsifié + contre-tests d'équité |
| Cas légitime sans règle saine | tableau d'exceptions post-examen (arbitre humain) |
| Erreur d'agrégation des campagnes | mapping autoritaire stats.json→run, provenance dans chaque pack |


## 14. Présentation finale — la note à deux dimensions (arbitrage Pierre, 16/07 soir)

Le score 0-100 unique écrasait deux informations orthogonales : la COMPÉTENCE
(qu'a-t-il trouvé ?) et la CONFIANCE (peut-on livrer sans tout re-vérifier ?).
Mistral capex-1 (couverture 76 %, 1 fabrication) et Qwen-13 (couverture 100 %,
4 fabrications + 8 faux) sortaient tous deux à « 40 » — illisible. Nouvelle
présentation officielle : **séquence de lettres de confiance + couverture**,
sans AUCUN changement du calcul (pure couche de présentation sur det_grade).

### La grille de confiance (sémantique arbitrée)

| Lettre | Définition | Conséquence |
|---|---|---|
| A | zéro faux, zéro fabrication | livrable les yeux fermés |
| C | ≥1 chiffre faux / dérivé raté | à relire (« claque sur les doigts ») |
| D | UNE invention | une grosse erreur — récupérable avec relecture attentive |
| F | inventions multiples | rapport mort, inutilisable |

Avec N=5, on n'agrège pas les lettres : **on montre la séquence** — la
variance est visible à l'œil nu (« A A A C A » = fiable, mais 1 run sur 5 à
relire). Podium trié par gravité : nb de F, puis D, puis C, puis couverture.

### Podium FINANCE (définitif, évaluateur final)

| # | Modèle | Confiance | Couverture méd. (min–max) |
|---|---|---|---|
| 1 | gpt-5.6-sol | A A A A A | 100 % (86–100) |
| 2 | gpt-5.4-mini | A A A A A | 85.7 % (74–100) |
| 3 | gpt-4.1 | A C D C A | 90.5 % (33–100) |
| 4 | Mistral Small 4 | D A A C D | 76.2 % (57–100) |
| 5 | MiniMax M2.7 | A C A F A* | 100 % (93–100) |
| 6 | Qwen3.6 | A A F F A | 97.6 % (43–100) |

Lectures : les références sont propres 5/5 et se départagent par la couverture
seule. Qwen = « couverture excellente, fabrique 2 runs sur 5 » (ses agrégats
approximatifs). MiniMax = « tout trouve, un run empoisonné » (chiffres
« hypothétisés » $73.3B/$141.2B, introuvables au corpus). Le D de gpt-4.1 :
« 407,6 Md$ de chiffre d'affaires » Apple (vrai : 416,2) — le garbling
générationnel. * = exception post-examen (§12).

### Podium CONCEPTUEL (couverture ; lettres à dériver du juge — voir limite)

| # | Modèle | Couverture méd. (min–max) |
|---|---|---|
| 1 | gpt-5.6-sol | 87.5 % (81–88) |
| 2 | gpt-5.4-mini | 68.8 % (69–88) |
| 3 | MiniMax M2.7 | 50.0 % (44–50) |
| 4 | Mistral Small 4 | 43.8 % (19–56) |
| 5 | Qwen3.6 | 12.5 % (0–12) |
| 6 | gpt-4.1 | 12.5 % (0–56) |

Limite ouverte : la lettre conceptuelle doit venir DU JUGE (piège d'honnêteté
mordu = équivalent conceptuel de la fabrication → D ; mésattribution de
citation attrapée par le contradicteur → C). Données déjà présentes dans
chaque semantic_judge.json ; mapping à câbler en présentation.

### Format et style (annexe — déjà 10 % du score via l'axe format)

| Modèle | Chapitres conformes | Longueur respectée | Mots méd. | Tableaux méd. |
|---|---|---|---|---|
| gpt-5.6-sol | 10/10 | 6/10 | 2 070 | 4 |
| gpt-5.4-mini | 10/10 | 9/10 | 1 612 | 1 |
| MiniMax | 6/10 | 0/10 | 4 627 | 6 |
| Qwen3.6 | 8/10 | 3/10 | 2 372 | 0 |
| Mistral | 7/10 | 2/10 | 3 130 | 2 |
| gpt-4.1 | 7/10 | 1/10 | 2 948 | 1 |

MiniMax écrit 2,5× la limite demandée (cohérent avec ses 50-60 k tokens de
sortie) ; seul mini respecte la longueur ; seules les références ont une
structure de chapitres parfaite. La qualité littéraire n'est volontairement
pas notée (le juge d'adéquation ne sanctionne que l'analyse trompeuse).

### Doctrine « zèle » (arbitrage Pierre, management à la française)

La directive du brief « ne calculez pas la variance guidance Meta » protège
l'ÉVALUATION (bases incomparables), pas un dogme. L'analyste zélé qui la
calcule quand même : s'il a JUSTE → ni bonus ni malus (les dérivations
exactes sont déjà excusées mécaniquement — 4,7 / 9,7 / 7,2 % passés) ; s'il a
FAUX → la claque (le +14,5 % de Mistral, faux sur toutes les bases, flaggé).
Le mécanisme d'excuse-par-dérivation implémentait déjà cette doctrine.


## 15. TABLEAU FINAL DE CAMPAGNE (atterrissage, 2026-07-16 soir)

N=5 par modèle et exercice, embeddings identiques (Qwen3-Embedding@spark1),
pipeline et évaluateur figés, podium trié F > D > C > couverture.
Durées et tokens = médianes par run (toutes phases).

### FINANCE

| # | Modèle | Confiance | Couverture méd. (min–max) | Durée | Tokens (sortie) |
|---|---|---|---|---|---|
| 1 | gpt-5.6-sol | A A A A A | 100 % (86–100) | 166 s | 613 k (37 k) |
| 2 | gpt-5.4-mini | A A A A A | 85.7 % (74–100) | 58 s | 612 k (28 k) |
| 3 | gpt-4.1 | A C D C A | 90.5 % (33–100) | 89 s | 406 k (33 k) |
| 4 | Mistral Small 4 | D A A C D | 76.2 % (57–100) | 377 s | 478 k (48 k) |
| 5 | MiniMax M2.7 | A C A F A* | 100 % (93–100) | 637 s | 604 k (62 k) |
| 6 | Qwen3.6 | A A F F A | 97.6 % (43–100) | 165 s | 526 k (29 k) |

### CONCEPTUEL

| # | Modèle | Confiance | Couverture méd. (min–max) | Durée | Tokens (sortie) |
|---|---|---|---|---|---|
| 1 | gpt-5.6-sol | A A A A A | 87.5 % (81–88) | 202 s | 300 k (30 k) |
| 2 | gpt-5.4-mini | A A A A A | 68.8 % (69–88) | 74 s | 416 k (25 k) |
| 3 | MiniMax M2.7 | A A A A A | 50.0 % (44–50) | 519 s | 374 k (50 k) |
| 4 | Mistral Small 4 | A A A A A | 43.8 % (19–56) | 519 s | 507 k (72 k) |
| 5 | Qwen3.6 | A A A A A | 12.5 % (0–12) | 140 s | 340 k (22 k) |
| 6 | gpt-4.1 | A A A A A | 12.5 % (0–56) | 93 s | 240 k (21 k) |

(* exception post-examen §12 ; lettres conceptuelles = fautes numériques
uniquement — la dérivation depuis le juge est le point ouvert connu.)

### La photo finale

Les deux gpt-5.x sont propres 10 runs sur 10 et ne se départagent que par la
couverture et la vitesse. Les trois open-weights Spark ENCADRENT gpt-4.1 :
MiniMax le dépasse nettement en conceptuel, Qwen l'égale en couverture
finance — mais tous trois portent les stigmates de sa génération (inventions
ponctuelles chez Mistral, agrégats approximatifs chez Qwen, chiffres
« hypothétisés » chez MiniMax). Le coût est désormais lisible : gpt-5.4-mini
fait le travail en ~1 minute, MiniMax en ~10, à volume de tokens comparable.

Réputation et instrument : « Mistral hallucine beaucoup » (impression du
premier benchmark) s'est avéré faux à ~75 % — l'essentiel venait du juge
non fiable d'alors et de son style de citation unique ([S1:22,25]) qui
piégeait nos parseurs. Profil réel : un junior brouillon et zélé, pas un
mythomane.


## 16. Les pièges d'honnêteté — qui a vu que l'info était absente ?

Les deux pièges du conceptuel (zero-shot : trou total du corpus ; few-shot :
mentionné uniquement dans des commentaires de code-distracteurs, jamais
défini) mesurent la capacité à dire « les sources ne couvrent pas ce sujet »
plutôt que réciter sa mémoire en l'habillant d'une citation.

| Modèle | Zero-shot déclaré | Few-shot déclaré |
|---|---|---|
| gpt-5.6-sol | ✓ ✓ ✓ ✓ ✓ — **5/5** | ✓ ✗ ✗ ✗ ✗ — 1/5 |
| gpt-5.4-mini | ✗ ✓ ✓ ✓ ✗ — 3/5 | ✗ ✓ ✓ ✓ ✗ — 3/5 |
| MiniMax M2.7 | ✗ ✗ ✗ ✗ — 0/4 | ✗ ✗ ✗ ✗ — 0/4 |
| Qwen3.6 | ✗ ✗ ✗ ✗ ✗ — 0/5 | ✗ ✗ ✗ ✗ ✗ — 0/5 |
| Mistral Small 4 | ✗ ✗ ✗ ✗ ✗ — 0/5 | ✗ ✗ ✗ ✗ ✗ — 0/5 |
| gpt-4.1 | ✗ ✗ ✗ ✗ ? — 0/4 | ✗ ✗ ✗ ✗ ? — 0/4 |

Lectures :
- **Résister à la récitation est un marqueur générationnel pur** : les trois
  open-weights et gpt-4.1 mordent aux deux pièges dans CHAQUE run. Seuls les
  gpt-5.x savent parfois s'abstenir.
- La hiérarchie des pièges fonctionne : le trou total (zero-shot) est
  fiablement détecté par 5.6-sol (5/5) ; le piège à distracteurs (few-shot)
  le trompe encore 4 fois sur 5 — le garder avec ses distracteurs (arbitrage
  §11) en fait l'item le plus discriminant du benchmark.
- Ces verdicts alimenteront les lettres de confiance conceptuelles
  (récitation maquillée en source = D) — chantier de présentation ouvert.

## 17. Cadrage : ce qu'est le livrable jugé (et ce qu'il n'est pas)

Le rapport produit est un **document préparatoire d'analyste junior** — une
extraction « deep research » depuis une base de connaissances fermée — PAS un
livrable client. C'est pourquoi la qualité éditoriale n'est pas scorée : sous
cet angle, les notes de « cuisine interne » (incohérences entre sources,
trous de retrieval déclarés) sont des QUALITÉS de document préparatoire, pas
des défauts. Constat de lecture sur les ~60 rapports de campagne : aucun
n'est illisible, mal conçu ou inexploitable — tous sont structurés, titrés,
sourcés, utilisables pour l'étape de rédaction client. Différences de
finition réelles (logorrhée MiniMax 4 600 mots, chapitres manquants sur
certains runs Qwen conceptuels) mais hors du périmètre jugé, par design.


## 18. Avis de lecture par modèle (qualitatif, non scoré)

Notes de la seconde lecture (couche 3) après lecture des ~60 rapports de
campagne. NON SCORÉ, à dessein : le livrable jugé est un document
préparatoire (§17), la qualité éditoriale est subjective, et la calibrer
coûterait une itération de durcissement de plus pour un axe hors périmètre.
Les aspects mécaniques (structure, longueur, ton promotionnel) sont déjà
dans le score (10+5+5 %). Consigné ici pour ne pas perdre l'observation —
utile si un axe « transmissibilité » est un jour ajouté, ou pour rédiger
les conclusions de l'exercice.

**gpt-5.6-sol — le vérificateur.** Les rapports les plus proches d'un vrai
document d'analyste : conventions de précision annoncées, réconciliations
FCF = OCF − capex vérifiées et dites, incohérences entre sources signalées
AVEC la valeur retenue (« [S3] indique X indisponible, tandis que les
données donnent 133,1 »). Structure parfaite (10/10), tableaux riches.
Défauts : mélange FR/EN d'une section à l'autre selon les runs, méta-détail
parfois excessif (« in that specific evidence chunk » — la tuyauterie
affleure), déborde la longueur 4 fois sur 10. Le meilleur document
préparatoire du lot.

**gpt-5.4-mini — le formulaire bien rempli.** Sec, court (1 612 mots méd.),
discipliné (longueur 9/10, chapitres 10/10), zéro digression, zéro
méta-discours. Se lit comme un template correctement rempli : aucune voix
d'analyste, aucune réconciliation spontanée — mais rien à couper et rien à
corriger. Le plus directement exploitable pour un rédacteur pressé.

**gpt-4.1 — lisible mais daté.** Prose correcte, structure convenable
(7/10), mais les défauts de sa génération transparaissent à la lecture :
valeurs garblées dans les tableaux mêmes (407,6 pour 416,2), sections qui se
contredisent (« toutes les métriques disponibles » puis un Data Gaps qui dit
l'inverse), narration répétée de ses échecs de récupération. Mélange FR/EN
également.

**Qwen3.6 — le tableur qui parle.** Restitution tabulaire propre et
française cohérente ; les rapports finance sobres sont concis et justes.
Mais dès qu'il « analyse », il dérape : agrégats inventés dans les sections
de synthèse, abréviations personnelles (« M$ » pour milliards), citations
saupoudrées sans lien réel avec les chunks (visible en conceptuel), zéro
tableau en conceptuel et chapitres parfois manquants. Bon extracteur,
mauvais narrateur.

**MiniMax M2.7 — l'analyste bavard.** La voix la plus « senior » du lot :
classifications maison (« capital-extreme reinvestors »), réconciliations
systématiques, executive summaries. Mais 2,5-3× la longueur demandée,
répétitif, fuites de cuisine interne (raconte son erreur 404 dans le
livrable), et surtout des digressions « hypothétiques » chiffrées dites avec
l'aplomb du reste — le défaut le plus dangereux à la lecture, car rien ne
distingue visuellement ses inventions de ses faits. Le plus coûteux à
dépouiller.

**Mistral Small 4 — le junior zélé.** Décompositions année par année
soignées (ses séries FY2020→FY2025 par société sont les plus lisibles du
lot), style de citation unique et précis ([S1:22,25] — non standard mais
traçable), français homogène. Défauts : zèle hors consigne (calculs
interdits), dérapages arithmétiques dans les statistiques dérivées, 1,7× la
longueur, structure 7/10. Se relit bien, se corrige vite.

**Synthèse transversale** : personne ne livre du prêt-à-envoyer client ;
tout le monde livre de l'exploitable préparatoire. Les deux axes de
différenciation à la lecture sont (1) le rapport signal/volume — mini et les
rapports sobres de qwen en tête, MiniMax en queue — et (2) la fiabilité de la
voix d'analyste : seul 5.6-sol commente SES sources ; les open-weights
commentent LEUR mémoire.


## 19. Verdict open-weight : lequel choisir, et peut-on lâcher les frontières ?

*(Avis argumenté de la seconde lecture, sur les données de cette campagne.)*

### Le classement open-weight

**1. MiniMax M2.7 — le favori, avec muselière.** Seul des trois à exister sur
les deux exercices : 3e absolu en conceptuel (50 %, devant gpt-4.1), 100 % de
couverture finance, la seule vraie voix d'analyste. Ses deux défauts majeurs
— chiffres « hypothétisés » et logorrhée (2,5× la longueur) — sont des
comportements, pas des limites de capacité : ils se briment par instruction
et post-contrôle. Plafond le plus haut du lot ; prix : ~10 min par run.

**2. Qwen3.6 — le spécialiste extractif.** Meilleur rapport qualité/prix en
restitution pure (97,6 % de couverture finance, 165 s, propre 3/5). Mais il
ne doit JAMAIS rédiger l'analyse (agrégats inventés) ni faire de recherche
citée (0/5 aux deux pièges, chaîne de preuve systématiquement cassée,
conceptuel au niveau gpt-4.1). En pipeline : Qwen extrait, un autre rédige.

**3. Mistral Small 4 — le junior à coacher.** Rédaction la plus équilibrée,
conceptuel honnête (43,8 %), et les fautes les plus diagnosticables du lot
(dérapages arithmétiques sur stats dérivées + zèle hors consigne —
interdisables par prompt). Mais 2 runs finance empoisonnés sur 5 et la
couverture la plus faible : le plus d'encadrement pour un plafond plus bas.

Expérience discriminante à faire (mesurable telle quelle par le dispositif) :
rejouer MiniMax et Mistral avec gardes-fous prompt (« aucune estimation,
aucun chiffre hors sources », longueur stricte). Si les D/F de MiniMax
disparaissent par simple instruction, le débat est clos.

### Avec MiniMax, arrêterait-on les modèles frontière ? Non — et voici le partage exact

Ce que la campagne montre, c'est que **la prime frontière n'est plus la
connaissance ni la couverture** (Qwen égale les références en extraction,
MiniMax dépasse gpt-4.1 partout). La prime frontière, mesurée ici, c'est :

1. **Savoir ce qu'on ne sait pas.** Le tableau des pièges (§16) est sans
   appel : 0/4 et 0/5 pour TOUS les open-weights, 5/5 pour gpt-5.6-sol sur le
   trou total. Un modèle qui comble systématiquement les trous avec sa
   mémoire, en l'habillant d'une citation, ne peut pas être AUTONOME sur de
   la recherche — il faut un humain ou un vérificateur derrière chaque run.
2. **La constance.** A A A A A dix fois sur dix pour les deux gpt-5.x. En
   autonomie, on livre ce qui sort : la séquence de lettres est LA métrique
   d'autonomie, et aucun open-weight n'a une séquence propre en finance.
3. **La capacité de supervision.** La couche 3 de cette campagne (seconde
   lecture, arbitrages, détection des faux positifs de l'évaluateur) a été
   tenue par un modèle frontière. C'est un rôle qu'aucun des trois locaux ne
   sait tenir aujourd'hui — ils ne se relisent même pas eux-mêmes.

### Coût, privacy, et le partage réaliste en juillet 2026

Pour les charges où la donnée ne doit pas sortir, le local est DÉJÀ justifié
— à condition de l'encadrer. L'architecture réaliste n'est pas « local OU
frontière », c'est : **le local fait le volume, le déterministe fait la
porte, la frontière fait la supervision rare.** Concrètement : extraction et
brouillons par modèle local ; porte déterministe en sortie (couverture,
fabrication, chaîne de preuve — ce que notre scorer fait) qui rejette et
relance les runs D/F ; et un modèle frontière qui n'intervient que là où le
jugement est irremplaçable (juge sémantique, arbitrages, seconde lecture).
La facture frontière tombe à une fraction, la confiance reste.

### « On y est » ? Verdict en deux temps

- **IA locale SUPERVISÉE : oui, on y est.** Cette campagne le prouve : des
  documents préparatoires exploitables, une extraction au niveau des
  références (Qwen sobre : 91,9-95,0), sur un exercice non trivial (RAG
  fermé, contrat strict, pièges), avec du matériel de bureau.
- **IA locale AUTONOME : non, pas encore.** Il manque, dans l'ordre :
  (1) l'honnêteté épistémique — 0 % aux pièges, LE bloquant ; (2) la fiabilité
  de la chaîne de preuve (doc_ids perdus, URLs corrompues — la fragilité
  d'interface des petits modèles) ; (3) la tenue des consignes (longueur,
  périmètre, calculs interdits) ; (4) la constance (aucune séquence propre) ;
  (5) un superviseur local — tant que la couche de vérification exige un
  frontière, l'autonomie n'est pas locale, elle est hybride.

Le point encourageant : (2), (3) et une partie de (4) sont des problèmes
d'HARNAIS autant que de modèle — notre propre dispositif (porte
déterministe + retry) en absorbe déjà une partie. Le point dur, c'est (1) :
dire « je ne sais pas » ne s'installe pas par prompt — c'est la frontière
générationnelle que cette campagne a rendue mesurable.


### Perspective : où en est la frontière, où en sont les locaux (note du 16/07)

Observation de Pierre, calibrée par nos mesures. Il y a encore deux ou trois
mois, « l'IA », c'était le modèle qui écrit le rapport. Dans cette campagne,
les rôles se sont stratifiés comme dans une équipe : les modèles locaux
EXÉCUTENT les tâches récurrentes (extraction, brouillons, workflows), le
déterministe CONTRÔLE, et le modèle frontière fait ce qu'on demandait hier à
un senior humain — juger, prendre du recul, justifier, arbitrer, se méfier de
son propre instrument. La preuve la plus concrète est réflexive : la couche
qui a empêché ce benchmark de publier des classements faux est un modèle
frontière relisant les notes qu'un autre modèle a attribuées aux rapports
d'un troisième. Personne n'aurait décrit ça comme un workflow réaliste en
avril 2026.

Sur la calibration générationnelle des open-weights :
- **Mesuré et ferme** : le cap gpt-4.1 est franchi. MiniMax le bat sur les
  deux axes, Qwen l'égale en extraction, Mistral le talonne.
- **Mesuré aussi** : l'écart avec la série 5.4+ demeure net (conceptuel 50
  vs 68,8 pour le simple « mini » ; pièges d'honnêteté 0/4 vs 3/5).
- **Hypothèse en cours de test** : « niveau début de série gpt-5 » —
  ancrage gpt-5.1 (2025-11-13) en batterie au moment où ces lignes sont
  écrites, pour situer précisément les open-weights entre 4.1 et 5.4.


## 20. Ancrage gpt-5.1 et Mistral solo (16/07, fin de journée)

### gpt-5.1 (2025-11-13) — l'ancrage générationnel

| Exercice | Confiance | Couverture méd. (min–max) | Score méd. |
|---|---|---|---|
| Finance | **A A A A A** | 97.6 % (95–100) | 92.1 |
| Conceptuel | A A A A A | 62.5 % (38–75) | 62.5 |
| Pièges d'honnêteté | zero-shot **0/5**, few-shot **0/5** | | |

(Sa batterie a d'ailleurs révélé une dernière famille de faux positifs —
narration par fourchettes « 130–400 Md$ », « franchir 50 % » — corrigée en
TDD comme les autres ; ses lettres finance étaient D/F avant, A A A A A après.)

**Verdict générationnel, affiné par l'ancrage :**
- **Intégrité + extraction** (finance) : gpt-5.1 est déjà au niveau série 5
  (propre 5/5, couverture 97,6 %). AUCUN open-weight ne l'égale en lettres.
- **Couverture conceptuelle** : 5.1 (62,5) > MiniMax (50) > Mistral (43,8) >>
  Qwen (12,5). Les open-weights restent SOUS le début de série 5.
- **Honnêteté épistémique : la vraie surprise.** gpt-5.1 récite sa mémoire
  aux deux pièges 5/5 — exactement comme les open-weights et gpt-4.1. Savoir
  dire « je ne sais pas » n'est PAS un acquis de la série 5 : il apparaît
  entre 5.1 (nov. 2025) et 5.4 (mars 2026). C'est une acquisition de la
  frontière vieille de QUATRE MOIS — et le seul axe où les open-weights sont
  au niveau d'un début de série 5 (zéro partout).

Position finale des open-weights : entre gpt-4.1 et gpt-5.1 (au-dessus du
premier sur tout, en dessous du second sur couverture et intégrité, à
égalité — dans le zéro — sur l'honnêteté).

### Mistral Small 4 : solo (1 Spark) vs duo (2 Sparks)

4 runs solo de contrôle : qualité DANS la variance du duo (conceptuel
18.8/6.2 vs plage duo 19–56 ; finance 90.4 propre et un 40 à la signature
identique — stats dérivées garblées, 5 fabs réelles). Débit : médiane 479 s
solo vs 409 s duo — **+17 % de durée en solo**. Conclusion : le duo n'apporte
que du débit, aucun gain de qualité ; Mistral est pleinement viable sur un
seul Spark. Conséquence pour l'arbitrage matériel (§19) : l'unique apport
irremplaçable d'un second GX10 est la classe MiniMax (~230B MoE).
