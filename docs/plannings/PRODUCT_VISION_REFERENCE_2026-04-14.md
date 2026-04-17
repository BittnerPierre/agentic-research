# Vision produit et référence roadmap - 2026-04-14

## 1. Objet du document

Ce document sert de référence de travail pour la roadmap d'`agentic-research`.

Il consolide :

- la vision produit ;
- les axes stratégiques ;
- le découpage en epics et features ;
- les dépendances majeures ;
- les workstreams parallélisables ;
- une première proposition de Sprint 1 ;
- le rattachement aux issues ouvertes déjà présentes dans le dépôt.

Ce document n'est pas un document de planning détaillé. Il vise à permettre :

- l'arbitrage produit ;
- le découpage du backlog ;
- le travail parallèle de plusieurs coding agents ;
- la préparation d'une roadmap plus formelle ensuite.

---

## 2. Vision produit

### Positionnement

`agentic-research` est un projet flagship à l'intersection de trois ambitions :

1. **Coworker IA for Finance**
2. **Coworker IA for Writer / Creative Content**
3. **Applied AI / DGX Spark Experiment**

### Proposition de valeur

La proposition de valeur centrale n'est pas seulement de générer un rapport,
mais de faire tourner un workflow agentique utile, autonome et traçable, capable
de :

- ingérer des sources privées ;
- produire une connaissance neutre et factuelle ;
- permettre une validation humaine ;
- réinjecter cette connaissance comme source dans un cycle de travail vivant ;
- fonctionner hors des plateformes managées des laboratoires IA.

### Cible court terme

La cible court terme est une **démonstration produit différenciante**, plus
qu'un usage purement personnel ou une plateforme multi-user aboutie.

Le système doit prouver :

- qu'il peut fonctionner sur DGX Spark / cluster ;
- qu'il produit une valeur métier concrète sur documents privés ;
- qu'il peut ensuite s'intégrer dans Claude, ChatGPT ou un mode service ;
- qu'il constitue une brique simple d'`Agent OS layer`.

### Critère de succès court terme

Le critère de succès principal n'est plus la robustesse brute.

La robustesse de base est jugée suffisante. Le nouveau critère de succès est :

- l'utilisabilité du résultat produit ;
- la couverture fonctionnelle ;
- l'intégration dans un usage quotidien.

En une phrase :

> Le produit doit devenir utile au quotidien comme moteur de curation et de
> connaissance, pas seulement comme générateur de rapports ponctuels.

---

## 3. Principes directeurs

### Principe 1 - Normalized knowledge first

La sortie coeur du système est un **rapport / fiche wiki neutre, factuelle,
traçable**, pas encore un livrable stylisé final.

Pipeline cible :

- `RAW`
- `NORMALIZED`
- `USAGE`

### Principe 2 - Human approval is part of the product

L'humain dans la boucle n'est pas un simple filet de sécurité. Il fait partie du
workflow normal :

- validation d'agenda ;
- arbitrage ;
- approbation d'écriture dans la base ;
- plus tard : actions à droits.

### Principe 3 - Incremental evolution over heavy refactor

Les évolutions recherchées doivent rester incrémentales, compatibles avec
l'existant, et à faible tolérance de régression.

### Principe 4 - Product value before platform expansion

Avant de pousser fortement le mode service, MCP distant ou multi-user, il faut
solidifier la valeur coeur :

- ingestion ;
- lifecycle de la connaissance ;
- neutralité du writer ;
- validation et contrôle.

### Principe 5 - Public benchmark credibility matters, but is not the core product

Les benchmarks sont importants pour la chaîne YouTube, la crédibilité technique
et le positionnement commercial, mais ils ne doivent pas remplacer la livraison
du coeur métier.

---

## 4. Axes stratégiques

### Axe A - Valeur produit immédiate

Objectif :

- rendre la connaissance produite exploitable ;
- ouvrir la gestion documentaire comme cas d'usage quotidien.

Epics concernés :

- `E2` PDF ingestion
- `E3` Knowledge lifecycle
- `E5` HITL & Recovery
- `E12` Classification agents

### Axe B - Qualité structurelle du workflow

Objectif :

- améliorer la qualité intrinsèque de la production ;
- isoler le writer ;
- préparer des workflows plus sophistiqués.

Epics concernés :

- `E6` Intermediate controllers
- `E7` Parallel writing
- `E8` Writer quality & context engineering

### Axe C - Crédibilité technique, benchmark et delivery

Objectif :

- choisir le meilleur backend d'inférence ;
- préparer les démonstrations DGX Spark ;
- accélérer la vélocité engineering ;
- rendre les benchmarks plus crédibles.

Epics concernés :

- `E1` Inference platform
- `E4` Benchmark & traceability
- `E9` UV migration

### Axe D - Plateforme et intégrations futures

Objectif :

- préparer l'ouverture du système vers assistants externes et mode service.

Epics concernés :

- `E10` Expose as MCP server
- `E11` Conversational service
- `E13` Note connectors
- `E14` Report lint / wiki health check

---

## 5. Backlog de référence par epic

## E1 - Inference Platform

### Intention produit

Choisir le backend d'inférence le plus pertinent pour DGX Spark / cluster en
comparant performance, mémoire, stabilité et qualité.

Le succès recherché à court terme est plus précis :

- faire tourner `agentic-research` sur **un seul gros modèle** ;
- commencer par `vLLM` sur dual DGX Spark ;
- valider ce mode avec `gpt-oss-120B`.

### Features proposées

- Backend d'inférence sélectionnable au démarrage via config / compose
- Priorité de mise en oeuvre : `vLLM`
- Référence technique initiale : `https://github.com/eugr/spark-vllm-docker`
- Support de variantes `llama.cpp`, `vLLM`, `SGLang` si nécessaire
- Support d'un mode mono-gros-modèle instruct + reasoning
- Déplacement du `reasoning effort` au niveau agent / orchestration
- Décorrélation du `reasoning effort` des paramètres globaux moteur
- Bench comparatifs backend x modèle x quantization
- Documentation d'exploitation DGX / cluster
- Validation cible principale sur `gpt-oss-120B`
- Stretch goals sur :
  - `nvidia/Qwen3.5-397B-A17B-NVFP4`
  - `nvidia/Gemma-4-31B-IT-NVFP4`
  - `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`

### Notes

Le sujet relève davantage d'un spike d'évaluation et de standardisation config
que d'une grosse architecture runtime.

---

## E2 - Document Ingestion

### Intention produit

Supporter des documents réels utilisés dans les cas d'usage finance et recherche
documentaire, au-delà du Markdown.

### Features proposées

- Ingestion PDF texte natif
- Parsing robuste page par page
- Chunking déterministe pour gros PDF
- Indexation de texte lisible
- Conservation de métadonnées utiles
- Support local file + output de `download_and_store_url`
- V1 texte-only
- OCR reporté à plus tard

---

## E3 - Knowledge Lifecycle

### Intention produit

Transformer le rapport en actif de connaissance réutilisable.

### Features proposées

- Approbation explicite d'un report avant ajout à la base
- Ajout du report validé dans le dataset / knowledge base
- Traçabilité stricte source -> report
- Possibilité d'utiliser un report comme source de recherche
- Mise à jour d'un report à partir de nouvelles sources
- Remplacement d'un report existant
- Suppression d'un report et de ses métadonnées associées
- Organisation dossiers / catégories pour reports
- Diff de connaissance : "qu'est-ce que cette nouvelle source change ?"
- Fondations pour GraphRAG à moyen terme

### V1 recommandée

- ajout validé ;
- indexation ;
- provenance stricte ;
- report comme source ;
- remplacement / suppression basiques.

---

## E4 - Benchmarks & Traceability

### Intention produit

Rendre les benchmarks reproductibles, crédibles et publiables, notamment pour
les démonstrations YouTube et les cas d'usage finance.

### Features proposées

- Hash du syllabus dans les artefacts
- Version du protocole d'évaluation
- Version des pondérations / benchmark weights
- Affichage de version dans les rapports benchmark
- Benchmark fonctionnel finance V1
- Syllabus financier réaliste basé sur sources locales
- Évolution des critères d'évaluation au-delà du simple rapport de recherche

### Notes

Le benchmark financier est un benchmark de cas d'usage, pas un clone complet de
`vals.ai`.

---

## E5 - HITL & Recovery

### Intention produit

Introduire l'humain comme acteur normal du workflow, en particulier avant les
actions sensibles et lors des décisions structurantes.

### Features proposées

- Validation humaine de l'agenda
- Questions à l'utilisateur en cours d'exécution
- Approbation avant écriture dans la base
- Approbation avant actions à droits ou sur datasets privés
- Pause / reprise du workflow
- Reprise après incident
- Support futur de durable execution

### V1 recommandée

- validation d'agenda ;
- approbation d'ajout en base ;
- point de reprise simple.

---

## E6 - Intermediate Controllers

### Intention produit

Éviter les faux positifs, stopper les workflows invalides et améliorer la
qualité sans créer de boucle infinie de corrections.

### Features proposées

- Contrôle bloquant : pas de source -> pas de report
- Contrôle bloquant : recherche incomplète / erreurs connues
- Contrôle programmatique des sorties attendues
- Contrôleur agentique de qualité du contenu
- Feedback loop bornée avec décision manager
- Escalade possible vers l'utilisateur si arbitrage nécessaire

### V1 recommandée

- garde-fous programmatiques ;
- un premier contrôleur bloquant sur la présence effective de sources.

---

## E7 - Parallel Writing

### Intention produit

Améliorer la qualité du reporting neutre et préparer les workflows rédacteur
plus complexes grâce à des conversations plus courtes et un découpage par
chapitre.

### Features proposées

- Agenda autonome comme contrat de découpage
- Writer par chapitre / section
- Agrégation déterministe des sections
- Relecture finale centrée sur répétitions / transitions / cohérence
- Contrôle qualité final après assemblage

### V1 recommandée

- agenda autonome ;
- génération par chapitre ;
- assemblage déterministe ;
- relecture finale simple.

---

## E8 - Writer Quality & Context Engineering

### Intention produit

Garantir un report neutre, factuel, stable et non contaminé par l'intention
finale de l'utilisateur.

### Features proposées

- Isolation du writer du prompt utilisateur
- Contrat explicite `RAW -> NORMALIZED -> USAGE`
- Context engineering pour limiter la pollution par conversation longue
- Réduction des informations inutiles passées au writer
- Clarification du format de sortie neutre
- Préparation à des workflows `plan-execute-revise`

### V1 recommandée

- writer complètement isolé du prompt initial ;
- entrée basée sur plan + sources + contrat explicite ;
- sortie normalisée neutre.

---

## E9 - DevEx & Packaging

### Intention produit

Améliorer la vélocité de développement, la CI et le déploiement.

### Features proposées

- Évaluer `uv` vs `Poetry`
- Décider migration complète ou mode hybride
- Adapter CI / GitHub Actions
- Adapter documentation de setup local
- Adapter déploiement Spark si utile

---

## E10 - Expose As MCP Server

### Intention produit

Exposer `agentic-research` comme service MCP distant pour assistants externes.

### Features proposées

- Serveur MCP distant pour `query` et `syllabus`
- Exposition granulaire de capacités
- Support streamable HTTP
- Documentation client
- Tests d'intégration MCP

---

## E11 - Conversational Service

### Intention produit

Créer une offre conversationnelle autonome pour les utilisateurs ne souhaitant
pas dépendre d'un assistant tiers.

### Features proposées

- API service pour lancer des runs de recherche
- Jobs asynchrones
- Healthcheck
- Suivi de statut
- V1 mono-user
- Base future pour sessions isolées et multi-user

---

## E12 - Classification Agents

### Intention produit

Faire de la classification documentaire une capacité réutilisable et visible,
pas seulement un effet de bord dataprep.

### Features proposées

- Exposer l'agent / pipeline de classification de façon unitaire
- Produire résumé, tags, type de document, catégories
- Réutiliser la classification lors d'un ajout de source
- Réutiliser la classification lors d'un ajout de report validé
- Mettre à jour la knowledge base avec métadonnées enrichies

---

## E13 - Connecteurs carnet de notes

### Intention produit

Utiliser des systèmes de prise de notes comme sources vivantes du workflow.

### Features proposées

- Connecteur lecture Evernote
- Connecteur lecture / écriture Notion
- Connecteur lecture Obsidian
- Synchronisation source -> dataprep
- Classification automatique à l'entrée
- Organisation de notes / pages issues de la curation

---

## E14 - Lint des reports / wiki health check

### Intention produit

Maintenir la base de connaissance saine au fur et à mesure de sa croissance.

### Features proposées

- Détection de contradictions entre pages
- Détection de claims obsolètes
- Détection de pages orphelines
- Détection de concepts sans page dédiée
- Détection de cross-references manquantes
- Suggestions de nouvelles questions / sources à investiguer
- Health check périodique de la base

---

## 6. Tableau de pilotage backlog

| Epic | Sous-epic / feature | Taille | Risque | Dépendances | Sprint recommandé |
|---|---|---|---|---|---|
| E1 | Backend inference sélectionnable par config avec priorité vLLM | M | Moyen | aucune forte | Sprint 1 |
| E1 | Validation mono gros modèle sur dual DGX avec gpt-oss-120B | M/L | Moyen | backend configurable | Sprint 1 |
| E1 | Déplacement du reasoning effort au niveau agent | M | Moyen | contrat agents / config modèle | Sprint 1 |
| E2 | Ingestion PDF texte natif | M | Moyen | dataprep ingestion | Sprint 1 |
| E2 | Chunking sûr gros PDF | M | Moyen | parsing PDF | Sprint 1 |
| E2 | Métadonnées utiles pages / extraction | S/M | Faible à moyen | parsing PDF | Sprint 2 |
| E3 | Approbation avant ajout d'un report en base | M | Moyen | E5 | Sprint 1 ou 2 |
| E3 | Report validé réutilisable comme source | M/L | Moyen à fort | E5, E12 | Sprint 2 |
| E3 | Provenance stricte source -> report | M | Moyen | knowledge DB | Sprint 2 |
| E3 | Remplacement / suppression de report | M | Moyen | provenance stricte | Sprint 2 |
| E3 | Diff de connaissance après nouvelle source | L | Fort | report comme source | Plus tard |
| E4 | Hash syllabus benchmark | S | Faible | benchmark artifacts | Sprint 1 |
| E4 | Version protocole d'éval | S/M | Faible | benchmarks | Sprint 1 ou 2 |
| E4 | Benchmark financier V1 | M/L | Moyen | syllabus finance, E2 | Sprint 2 |
| E5 | Validation humaine de l'agenda | M | Moyen | workflow writer / planner | Sprint 1 |
| E5 | Approbation avant écriture dans la base | M | Moyen | knowledge lifecycle | Sprint 1 ou 2 |
| E5 | Pause / reprise simple | M/L | Moyen à fort | orchestration workflow | Sprint 2 |
| E5 | Durable execution / recovery avancé | L | Fort | design orchestration | Plus tard |
| E6 | Gate bloquant si aucune source | S/M | Faible | workflow actuel | Sprint 1 |
| E6 | Contrôles programmatiques intermédiaires | M | Faible à moyen | instrumentation / outputs | Sprint 2 |
| E6 | Contrôleur agentique qualité | M/L | Moyen à fort | E8 | Sprint 2 |
| E7 | Agenda autonome | M | Moyen | writer contract | Sprint 2 |
| E7 | Writers par chapitre | L | Fort | E8, agenda autonome | Sprint 2 |
| E7 | Assemblage déterministe | M | Moyen | writers par chapitre | Sprint 2 |
| E7 | Relecture finale après assemblage | M | Moyen | assemblage | Sprint 2 |
| E8 | Isolation du writer du prompt utilisateur | M | Moyen | writer only | Sprint 1 |
| E8 | Contrat RAW -> NORMALIZED -> USAGE | M | Moyen | writer only | Sprint 1 |
| E8 | Context engineering / payload réduit | M | Moyen | writer / manager | Sprint 1 |
| E9 | Évaluation migration uv | S | Faible | aucune forte | Sprint 1 |
| E9 | Migration CI vers uv | M | Faible à moyen | décision uv | Sprint 1 |
| E9 | Migration locale / docs / scripts | M | Faible à moyen | décision uv | Sprint 1 |
| E10 | Serveur MCP distant query / syllabus | M/L | Moyen | coeur workflow stable | Plus tard |
| E10 | Exposition granulaire des capacités | M/L | Moyen | design service MCP | Plus tard |
| E11 | API service mode V0 mono-user | L | Fort | coeur workflow stable | Plus tard |
| E11 | Jobs async / suivi d'état | L | Fort | service mode | Plus tard |
| E12 | Classification unitaire réutilisable | M | Moyen | dataprep metadata | Sprint 1 |
| E12 | Classification à l'ajout de report | M | Moyen | E3 | Sprint 2 |
| E13 | Connecteur lecture Evernote | M/L | Moyen | E12 | Plus tard |
| E13 | Connecteur lecture/écriture Notion | M/L | Moyen | E12, E3 | Plus tard |
| E13 | Connecteur lecture Obsidian | M | Moyen | E12 | Plus tard |
| E14 | Contradictions / orphan pages / stale claims | M/L | Moyen à fort | E3 vivant | Plus tard |
| E14 | Suggestions de nouvelles sources / questions | M | Moyen | E3, lint base | Plus tard |

Notes de lecture :

- `Taille` est relative : `S`, `M`, `L`.
- `Sprint recommandé` indique la première fenêtre réaliste, pas un engagement.
- Plusieurs lignes marquées `Sprint 1 ou 2` dépendent du niveau d'ambition
  retenu pour la première itération.

---

## 7. Workstreams parallélisables

## WS1 - Inference / DGX / Bench technique

Contenu :

- `E1`
- `E4` minimal

**Règle d'indépendance** : WS1 est **totalement indépendant** de WS4. Il doit
fonctionner sur le workflow actuel, être livrable et mergeable de façon
autonome, et utiliser une branche d'intégration de workstream dédiée
(ex: `ws1/inference-platform`) : chaque feature garde sa propre branche, puis
est intégrée dans cette branche de workstream sans intégration immédiate dans
la branche principale du dépôt, afin de ne pas bloquer les autres workstreams.

**Contexte** : ce workstream est lié à un engagement client ASUS / NVIDIA.
C'est une contrainte externe de livraison.

Pourquoi c'est parallélisable :

- changements surtout infra / compose / benchmark ;
- faible recouvrement avec writer et dataprep ;
- merge simple si ownership clair.

## WS2 - DevEx / Packaging

Contenu :

- `E9`

Pourquoi c'est parallélisable :

- très isolé ;
- faible conflit avec autres workstreams ;
- bénéfice immédiat pour toute la suite.

## WS3 - Ingestion / Classification / Knowledge foundations

Contenu :

- `E2`
- `E12`
- début de `E3`

Pourquoi c'est parallélisable :

- principalement dataprep / knowledge DB ;
- peut avancer indépendamment du gros refactoring workflow writer.

## WS4 - Workflow agentique coeur

Contenu :

- `E8`
- `E5`
- `E6`
- `E7`
- partie workflow de `E3`

Pourquoi ce stream doit rester cohérent :

- forte cohérence fonctionnelle ;
- forte chance de conflits si plusieurs changements touchent manager, planner,
  writer, orchestration ;
- nécessite un séquencement plus strict.

## WS5 - Plateforme et intégrations futures

Contenu :

- `E10`
- `E11`
- `E13`
- `E14`

Pourquoi c'est plus tard :

- dépend d'un coeur métier plus stable ;
- plus faible rendement produit court terme.

---

## 8. Proposition de Sprint 1

## Objectif du sprint

Créer un premier incrément combinant :

- une vraie amélioration du coeur de valeur documentaire ;
- une fondation de qualité pour le writer ;
- un quick win de vélocité engineering ;
- un spike crédible pour la démonstration DGX / cluster.

## Périmètre recommandé

### Stream A - Writer / workflow qualité

Noyau dur :

- `E6` gate bloquant si aucune source n'a été produite
- `E8` isolation du writer du prompt utilisateur

Stretch :

- `E8` contrat `RAW -> NORMALIZED -> USAGE`
- `E5` validation humaine de l'agenda en V1 simple

### Stream B - Ingestion / classification

- `E2` ingestion PDF texte natif
- `E2` chunking sûr pour gros PDF
- `E12` classification unitaire réutilisable

### Stream C - Engineering enablement

- `E9` évaluation + migration `uv`
- `E4` hash syllabus benchmark

### Stream D - Inference spike

- `E1` backend inference configurable avec `vLLM` comme cible prioritaire
- `E1` déplacement du `reasoning effort` au niveau agent
- `E1` spike mono gros modèle / cluster DGX sur `gpt-oss-120B`

## Ce que Sprint 1 ne doit pas essayer de faire

- `E3` complet
- `E5` complet
- `E7` complet
- `E10` / `E11`

## Livrables cibles de Sprint 1

- writer mieux isolé, avec contrat plus net ;
- impossible de produire un report sans vraie source ;
- ingestion PDF texte fonctionnelle ;
- classification réutilisable comme capacité distincte ;
- décision plus claire sur `uv` ;
- hash syllabus ajouté aux benchmarks ;
- première validation technique d'un mode mono gros modèle sur `vLLM` et
  `gpt-oss-120B`, avec `reasoning effort` piloté côté agent.

---

## 9. Mapping avec les issues ouvertes

## À embarquer directement

- `#145` -> `E6` gate bloquant si aucune source
- `#128` -> `E9` migration / évaluation `uv`
- `#102` -> `E2` ingestion PDF
- `#95` -> `E4` syllabus hash
- `#103` -> `E12` métadonnées et classification à l'ingestion locale

## Déjà formulé, mais pas Sprint 1

- `#83` -> `E10` MCP distant
- `#13` -> `E11` mode service API
- `#69` -> `E5` / durable execution Restate, à garder comme référence
- `#114` -> multi-user futur, à ne pas traiter avant service / MCP plus mature
- `#100` -> benchmark financier V1, à relier à `E4`

## Fondations / hygiene backlog à rattacher mais sans en faire des axes roadmap

- `#54` config embedding unifiée
- `#57` duplication compose / env
- `#96` éviter les mutations globales de config
- `#101` guard missing sources non-fatal
- `#125` couverture de tests workflows / coordination

## Sujet déjà largement réalisé ou partiellement couvert

- routage retrieval via MCP / Chroma : base architecture déjà en place
- robustification DGX : niveau jugé suffisant
- évals / benchmark framework : base déjà en place
- metadata extraction partielle dans dataprep : existante pour certains flux, à
  généraliser pour l'ingestion locale

---

## 10. Recommandation finale

Le coeur de la prochaine étape ne doit pas être "faire plus de features". Il
doit être :

1. rendre la connaissance produite exploitable ;
2. introduire l'humain au bon endroit dans le workflow ;
3. assainir le contrat du writer ;
4. ouvrir le cas d'usage documentaire réel ;
5. avancer en parallèle sur les sujets infra/CI qui ne bloquent pas le coeur.

En conséquence, le meilleur compromis actuel est :

- **Build now** : `E8`, `E2`, `E12`, `E6` minimal, `E5` minimal, `E9`, `E4`
  minimal, `E1` en spike avec `vLLM` prioritaire et validation mono-modèle
- **Build next** : `E3` V1, `E6` enrichi, `E7`
- **Build later** : `E10`, `E11`, `E13`, `E14`

Cette structure permet de garder une roadmap cohérente, mergeable en parallèle,
et alignée avec la fois sur la démonstration DGX et sur la valeur produit
documentaire.
