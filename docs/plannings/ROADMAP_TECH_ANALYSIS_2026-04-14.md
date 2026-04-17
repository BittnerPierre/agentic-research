# Analyse technique roadmap - 2026-04-14

## Objet

Ce document synthétise :

- le backlog produit initial issu de `Roadmap agentic research 13-04-2026.pdf` ;
- les réponses de cadrage de `Questions globales - reponses.md` ;
- les issues ouvertes déjà présentes dans le dépôt.

L'objectif n'est pas de figer la roadmap métier, mais de fournir une lecture
tech lead / scrum permettant au Product Owner de prioriser avec une bonne
visibilité sur :

- la valeur produit ;
- les dépendances ;
- les risques ;
- les sujets parallélisables ;
- l'ordre d'exécution technique recommandé.

---

## 1. Lecture générale

La priorité métier exprimée n'est pas équivalente à la priorité
d'implémentation.

Le projet poursuit simultanément trois finalités :

1. démonstration technique DGX Spark / inference backend ;
2. différenciation produit autour d'un workflow agentique utile au quotidien ;
3. socle futur d'intégration dans un Agent OS, un assistant existant ou un
   service autonome.

En pratique, cela fait apparaître trois axes distincts :

### Axe A - Valeur produit immédiate

Ce qui rend le produit utile au quotidien :

- `E2` ingestion documentaire PDF ;
- `E3` lifecycle de la connaissance ;
- `E5` HITL et approbation des actions ;
- `E12` classification des documents.

### Axe B - Qualité structurelle du workflow

Ce qui améliore la qualité et la fiabilité du résultat produit :

- `E8` neutralité du writer et context engineering ;
- `E6` contrôleurs intermédiaires ;
- `E7` écriture parallèle / sous-agents writers.

### Axe C - Crédibilité technique et vélocité engineering

Ce qui soutient la démonstration DGX, les benchmarks et le delivery :

- `E1` inference platform ;
- `E4` benchmark & traçabilité ;
- `E9` migration vers `uv`.

Le principal risque serait de traiter tous les `P1` comme un seul prochain
sprint, alors qu'ils n'ont ni le même rôle ni le même niveau de dépendance.

---

## 2. Conclusion principale

Le centre de gravité produit est `E3`.

Le besoin réel n'est pas seulement de générer un rapport, mais de produire une
connaissance neutre, validée, traçable, réutilisable et maintenable dans le
temps.

Le couple le plus structurant est donc :

- `E3` Knowledge Lifecycle ;
- `E5` HITL & Recovery.

Mais ce couple ne doit pas masquer un prérequis technique important :

- `E8` Writer Quality & Context Engineering.

Tant que le writer n'est pas mieux isolé du prompt utilisateur et de la longue
conversation, la valeur des features de workflow plus avancées (`E6`, `E7`)
reste dégradée.

Autrement dit :

- `E3` est le coeur de la valeur produit ;
- `E5` est une brique fonctionnelle nécessaire ;
- `E8` est un prérequis de qualité du coeur ;
- `E7` ne doit pas démarrer seul.

---

## 3. Analyse par epic

### E1 - Inference Platform

**Lecture technique**

Le besoin n'est pas de construire une abstraction sophistiquée des moteurs,
mais de permettre un choix concret de backend pour comparer performance,
mémoire et stabilité sur DGX Spark, avec sélection au démarrage.

Le point critique n'est pas seulement le choix du backend. La vraie cible court
terme est de faire tourner `agentic-research` sur **un seul gros modèle
instruct + reasoning**.

La cible prioritaire devient donc :

- backend : `vLLM`
- environnement : dual DGX Spark
- modèle principal : `gpt-oss-120B`

Cela implique un changement de contrat important :

- le `reasoning effort` ne doit plus être porté uniquement par le moteur
  d'inférence dans la configuration ;
- il doit être remonté au niveau agent / orchestration / appel modèle.

**Attention** : le mécanisme de reasoning varie par famille de modèles
(OpenAI natif via `reasoning_effort`, Nemotron via `--reasoning-parser` +
`chat_template_kwargs`, Qwen 3 via `--enable-reasoning` + `/think` dans le
prompt). Une note d'étude est requise avant implémentation pour identifier
le bon niveau d'abstraction.

**Nature du travail**

- principalement config, Docker, benchmark, scripts ;
- impact limité mais réel sur le contrat des agents ;
- bonne compatibilité avec une stratégie incrémentale.

**Recommandation**

Traiter `E1` comme un `spike + enabler`, pas comme un gros chantier
d'architecture, avec deux sous-objectifs :

- standardiser `vLLM` comme backend cible prioritaire ;
- valider un mode `single-model` où le raisonnement est piloté côté agent.

### E2 - Document Ingestion

**Lecture technique**

Le besoin prioritaire est clair et limité :

- PDF texte natif d'abord ;
- documents structurés ensuite ;
- OCR plus tard.

La V1 peut rester simple :

- extraction texte ;
- extraction robuste page par page ;
- chunking déterministe ;
- conservation de métadonnées utiles si possibles.

**Recommandation**

Très bon candidat de sprint proche. La feature ouvre directement des cas d'usage
finance et recherche documentaire.

### E3 - Knowledge Lifecycle

**Lecture technique**

C'est l'epic le plus important et aussi l'un des plus gros.

Le besoin ne se limite pas à "indexer des rapports". Il faut au minimum :

- approbation explicite avant ajout ;
- traçabilité stricte source -> report ;
- remplacement / mise à jour ;
- suppression ;
- possibilité d'utiliser ensuite le rapport comme source.

**Risque**

Epic trop gros si traité en bloc. Il faut impérativement le découper.

**Recommandation**

Traiter une V1 étroite :

- rapport validé ;
- indexable ;
- traçable ;
- remplaçable / supprimable.

### E4 - Benchmarks & Traceability

**Lecture technique**

Le besoin existe, mais sa valeur est surtout externe :

- crédibilité publique ;
- reproductibilité des benchmarks ;
- communication YouTube / démonstration.

Ce n'est pas le coeur du produit utilisateur final.

**Recommandation**

Faire un socle minimal et utile :

- hash syllabus ;
- version protocole ;
- version benchmark weights si nécessaire.

Ne pas surinvestir tant que le benchmark fonctionnel finance n'est pas cadré.

### E5 - HITL & Recovery

**Lecture technique**

Ce n'est pas seulement une amélioration UX. Le humain est explicitement une
partie normale du workflow cible :

- validation d'agenda ;
- réponses à des questions ;
- approbation d'écriture dans la base ;
- validation de certaines actions avec droits.

Le sujet `recovery` et orchestration durable peut être beaucoup plus large que
la première itération nécessaire.

**Risque**

Si l'epic est pris trop large, il avale tout le sprint :

- pause/reprise durable ;
- état orchestration ;
- annulation ;
- interface de validation ;
- multi-user plus tard.

**Recommandation**

Commencer par une V1 étroite :

- point d'arrêt sur agenda ;
- point d'arrêt sur ajout du rapport à la base ;
- structure simple de reprise / poursuite.

### E6 - Intermediate Controllers

**Lecture technique**

Il faut distinguer deux familles :

1. contrôleurs programmatiques bloquants ;
2. contrôleurs agentiques consultatifs ou semi-bloquants.

La première famille est peu risquée et immédiatement utile :

- pas de source -> pas de rapport ;
- erreur connue -> arrêt ;
- fichiers absents / résultats vides -> blocage.

La deuxième famille demande une gouvernance explicite pour éviter les boucles de
révision infinies.

**Recommandation**

Commencer par les garde-fous programmatiques, puis introduire progressivement
les contrôleurs agentiques.

### E7 - Parallel Writing

**Lecture technique**

Le besoin est moins la performance brute que la qualité :

- conversations plus courtes ;
- meilleure spécialisation par chapitre ;
- agrégation déterministe ;
- relecture finale ciblée.

Mais cette architecture n'est saine que si le contrat d'entrée du writer est
stable et si le plan est suffisamment propre.

**Recommandation**

Ne pas lancer `E7` avant un socle `E8 + agenda autonome + contrôle minimal`.

### E8 - Writer Quality & Context Engineering

**Lecture technique**

Cet epic est sous-priorisé côté métier par rapport à son importance technique.

Le problème principal est identifié :

- contamination par l'intention utilisateur ;
- pollution par la longueur de conversation ;
- manque d'isolation entre `RAW`, `NORMALIZED`, `USAGE`.

**Recommandation**

Remonter `E8` très tôt dans l'ordre technique, même s'il reste `P2` métier.
Sans cette fondation, `E7` et une partie de `E3` vont produire une dette
workflow durable.

### E9 - DevEx & Packaging

**Lecture technique**

Sujet à faible risque et forte valeur engineering :

- CI plus rapide ;
- dev loop plus courte ;
- meilleure expérience multi-coding-agents.

**Recommandation**

Quick win isolable, fortement parallélisable, bonne candidate Sprint 1.

### E10 - Expose As MCP Server

**Lecture technique**

Le besoin est légitime, mais il suppose un coeur métier déjà stabilisé :

- capacités à exposer clairement ;
- granularité des outils ;
- contrats plus nets ;
- gestion des runs et annulations.

**Recommandation**

Long terme, après stabilisation du coeur produit et du workflow.

### E11 - Conversational Service

**Lecture technique**

Sujet produit / plateforme plus lointain :

- API ou UI ;
- sessions ;
- jobs async ;
- multi-user à terme ;
- auth plus tard.

**Recommandation**

À garder hors des prochains sprints centraux.

### E12 - Classification Agents

**Lecture technique**

Le besoin est déjà partiellement présent dans dataprep :

- résumé ;
- tags ;
- extraction de métadonnées.

La vraie évolution consiste à rendre cette capacité réutilisable unitairement et
à en faire une brique d'organisation de la connaissance.

**Recommandation**

Bon sujet transverse, utile à `E3` et `E13`, et compatible avec une évolution
incrémentale.

### E13 - Connecteurs carnet de notes

**Lecture technique**

Epic utile mais dépendant :

- d'un contrat d'ingestion clair ;
- d'une classification exploitable ;
- d'un lifecycle de la connaissance suffisamment propre.

**Recommandation**

Pas prioritaire tant que `E12` et une partie de `E3` ne sont pas posés.

### E14 - Lint des reports / wiki health check

**Lecture technique**

Sujet pertinent mais fortement dépendant d'un corpus déjà vivant :

- rapports réinjectés ;
- liens ;
- traçabilité ;
- notion de fraîcheur.

**Recommandation**

Long terme. Forte valeur une fois `E3` installé, faible rendement avant cela.

---

## 4. Dépendances structurantes

Les dépendances les plus importantes sont :

- `E8 -> E7`
- `E5 -> E3`
- `E12 -> E3`
- `E12 -> E13`
- `E3 -> E14`
- `E2 -> E3` pour le cas d'usage documentaire cible
- `E5` influence fortement `E7`
- `E6` dépend partiellement du contrat de workflow défini par `E5`

Conséquences :

- `E3`, `E5`, `E7` forment un programme cohérent, pas trois chantiers isolés ;
- `E8` est une fondation du writer ;
- `E12` est une fondation de classification / organisation des sources ;
- `E1`, `E4`, `E9` sont presque indépendants.

---

## 5. Workstreams parallélisables

### Workstream WS1 - Inference / DGX / Benchmark technique

Inclut :

- `E1`
- éventuellement une partie de `E4`

**Règle d'indépendance** : WS1 est **totalement indépendant** de WS4. Il doit
fonctionner sur le workflow actuel, être livrable et mergeable de façon
autonome, et utiliser une branche d'intégration de workstream dédiée
(ex: `ws1/inference-platform`) : chaque feature garde sa propre branche, puis
est intégrée dans cette branche de workstream sans intégration immédiate dans
la branche principale du dépôt, afin de ne pas bloquer les autres workstreams.

**Contexte** : ce workstream est lié à un engagement client ASUS / NVIDIA.

Caractéristiques :

- peu de dépendances sur le coeur workflow ;
- forte autonomie ;
- merge facile si les changements restent surtout config / infra / benchmark.

### Workstream WS2 - DevEx / Packaging / CI

Inclut :

- `E9`

Caractéristiques :

- très isolable ;
- valeur transversale immédiate ;
- merge très peu conflictuel.

### Workstream WS3 - Ingestion & Knowledge Foundations

Inclut :

- `E2`
- `E12`
- une partie de `E3`

Caractéristiques :

- impact surtout dataprep / knowledge DB / métadonnées ;
- peut avancer sans dépendre du refactoring profond du writer ;
- merge raisonnablement simple si ownership clair.

### Workstream WS4 - Workflow agentique coeur

Inclut :

- `E8`
- `E5`
- `E6`
- `E7`
- une partie de `E3`

Caractéristiques :

- forte cohérence fonctionnelle ;
- forte possibilité de conflits si plusieurs changements touchent manager /
  writer / orchestration en parallèle ;
- nécessite un découpage fin.

### Workstream WS5 - Intégrations externes

Inclut :

- `E10`
- `E11`
- `E13`
- `E14`

Caractéristiques :

- à garder plus tard ;
- dépendance forte à la stabilisation du coeur.

---

## 6. Ordre d'exécution technique recommandé

Ordre recommandé sans figer la priorité métier :

1. `E9` quick win engineering
2. `E1` spike cadré sur `vLLM` / cluster / mono gros modèle, avec
   `reasoning effort` remonté côté agent
3. `E8` fondation writer / context engineering
4. `E2` + `E12` pour ouvrir un cas d'usage documentaire réel
5. `E5` en V1 étroite
6. `E3` en V1 étroite
7. `E6` d'abord programmatique, puis agentique
8. `E7` après stabilisation du contrat writer et du plan

Ce séquencement permet :

- de livrer vite de la valeur visible ;
- de ne pas diluer l'effort sur trop de sujets couplés ;
- de préserver des chantiers parallèles à faible conflit.

---

## 7. Ce qu'il ne faut pas faire

### Ne pas lancer en même temps en mode "gros chantier"

- `E3` complet
- `E5` complet
- `E7` complet

Ces trois sujets sont trop couplés.

### Ne pas lancer `E7` avant stabilisation du writer

Sinon on distribue sur plusieurs sous-agents un problème déjà présent dans un
writer monolithique.

### Ne pas surinvestir `E4` avant clarification du benchmark fonctionnel

La traçabilité est utile, mais ne doit pas prendre la place du produit coeur.

---

## 8. Mapping utile avec les issues ouvertes

Issues déjà alignées avec la roadmap :

- `#145` contrôleur bloquant si aucune source n'a été produite -> `E6`
- `#128` migration Poetry -> uv -> `E9`
- `#102` support ingestion PDF -> `E2`
- `#95` hash syllabus benchmark -> `E4`
- `#83` exposition MCP distante -> `E10`
- `#13` mode service API -> `E11`
- `#69` Restate POC -> support de réflexion pour `E5`
- `#114` multi-user / runs concurrents -> dépendance future de `E11`
- `#103` métadonnées pour ingestion locale -> fondation de `E12`
- `#100` premier syllabus finance -> `E4` et ancrage métier

Issues à traiter comme fondations / hygiene backlog, pas comme axes roadmap :

- `#54` unification config embeddings
- `#57` duplication env / compose
- `#96` mutation de config globale
- `#101` missing sources non-fatal

---

## 9. Synthèse décisionnelle

### Si l'objectif est la valeur produit la plus visible

Prioriser :

- `E2`
- `E12`
- `E5`
- `E3`

### Si l'objectif est la qualité structurelle du workflow

Prioriser :

- `E8`
- `E6`
- puis `E7`

### Si l'objectif est la crédibilité technique / DGX / vidéo

Prioriser :

- `E1`
- `E4`
- `E9`

### Recommandation de compromis

Pour les prochains travaux, le meilleur compromis paraît être :

- `E9` en quick win ;
- `E1` en spike cadré avec `vLLM` comme cible prioritaire et validation d'un
  mode mono-modèle sur `gpt-oss-120B` ;
- `E8` comme fondation qualité ;
- `E2` et `E12` comme ouverture d'un cas d'usage documentaire concret ;
- `E5` et `E3` en V1 étroite.

Cette combinaison préserve la démonstration technique DGX, améliore le coeur du
workflow et ouvre une valeur métier visible sans exiger de refonte massive.
