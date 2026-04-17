# Sprint 1 - backlog de features prêt à ouvrir en issues

## Objet

Ce document transforme la proposition de Sprint 1 en backlog ordonné de
features prêtes à être ouvertes en issues GitHub.

L'objectif n'est pas de détailler des user stories, mais de définir un lot de
features suffisamment clair pour :

- être priorisé ;
- être confié à plusieurs coding agents en parallèle ;
- être mergé avec un niveau de conflit limité ;
- rester cohérent avec la vision produit et l'analyse technique.

Références :

- `docs/plannings/ROADMAP_TECH_ANALYSIS_2026-04-14.md`
- `docs/plannings/PRODUCT_VISION_REFERENCE_2026-04-14.md`

---

## 1. Objectif du Sprint 1

Le Sprint 1 doit produire un incrément visible sur quatre fronts :

1. **assainir le coeur du workflow** ;
2. **ouvrir le cas d'usage documentaire réel** ;
3. **accélérer la vélocité engineering** ;
4. **préparer la validation DGX / cluster sur un mode mono gros modèle sans
   refonte lourde**.

Le sprint ne doit pas tenter de livrer :

- le lifecycle complet de la connaissance ;
- le HITL complet ;
- la parallélisation complète du writer ;
- le mode service ;
- l'exposition MCP distante.

---

## 2. Règle de découpage

Une feature de Sprint 1 doit respecter autant que possible les critères
suivants :

- être mergeable sans dépendre d'une refonte globale ;
- avoir un périmètre clair ;
- avoir une stratégie de test identifiable ;
- produire soit de la valeur directe, soit un enabler clair ;
- pouvoir être portée par un workstream relativement autonome.

### Critère transverse de test

Chaque feature du Sprint 1 doit inclure au minimum un test d'intégration du
happy path. Le TDD s'applique aux bugs (test qui échoue d'abord), mais les
features doivent aussi livrer une couverture de test minimale vérifiable.

---

## 3. Vue d'ensemble du backlog Sprint 1

| Ordre | Code  | Epic | Titre de feature                                                              | Type    | Workstream | Statut backlog                       |
| ----- | ----- | ---- | ----------------------------------------------------------------------------- | ------- | ---------- | ------------------------------------ |
| 1     | S1-01 | E9   | Evaluer puis migrer de Poetry vers uv                                         | Enabler | WS2        | Réutiliser issue existante           |
| 2     | S1-02 | E4   | Ajouter le hash du syllabus dans les artefacts benchmark                      | Enabler | WS1        | Réutiliser issue existante           |
| 3     | S1-03 | E1   | Rendre le backend d'inférence sélectionnable au démarrage avec priorité vLLM  | Feature | WS1        | Nouvelle issue                       |
| 4     | S1-04 | E1   | Valider un mode mono gros modèle sur dual DGX avec gpt-oss-120B               | Spike   | WS1        | Nouvelle issue                       |
| 5     | S1-05 | E6   | Bloquer la génération de report si aucune source exploitable n'a été produite | Feature | WS4        | Réutiliser issue existante           |
| 6     | S1-06 | E8   | Isoler le writer du prompt utilisateur et de la conversation longue           | Feature | WS4        | Nouvelle issue                       |
| 7     | S1-07 | E8   | Formaliser le contrat writer RAW -> NORMALIZED                                | Feature | WS4        | Nouvelle issue                       |
| 8     | S1-08 | E5   | Ajouter une validation humaine de l'agenda en V1 simple                       | Feature | WS4        | Nouvelle issue                       |
| 9     | S1-09 | E2   | Ajouter l'ingestion PDF texte natif côté dataprep                             | Feature | WS3        | Réutiliser issue existante           |
| 10    | S1-10 | E2   | Rendre le chunking PDF gros fichier sûr et déterministe                       | Feature | WS3        | Nouvelle issue ou extension de S1-09 |
| 11    | S1-11 | E12  | Générer les métadonnées de classification pour l'ingestion locale             | Feature | WS3        | Réutiliser issue existante           |
| 12    | S1-12 | E12  | Exposer la classification documentaire comme capacité réutilisable            | Feature | WS3        | Nouvelle issue                       |

Remarque :

- `S1-09` et `S1-10` peuvent être fusionnées dans une seule issue si tu veux un
  sujet PDF unique.
- `S1-06` et `S1-07` peuvent être séparées pour limiter le risque de conflit
  entre refonte de contrat et adaptation du prompt / orchestration.

---

## 4. Workstreams parallélisables

## WS1 - Inference / Benchmark technique

Features :

- `S1-02`
- `S1-03`
- `S1-04`

**Règle d'indépendance** : WS1 est **totalement indépendant** de WS4 (workflow
agentique coeur). Il doit :

- fonctionner sur le **workflow tel qu'il est aujourd'hui**, sans dépendre des
  changements de WS4 (isolation writer, contrat NORMALIZED, HITL, etc.) ;
- être **livrable et mergeable de façon autonome** ;
- utiliser une **branche d'intégration de workstream** (ex:
  `ws1/inference-platform`) : chaque feature garde sa propre branche, puis est
  intégrée dans cette branche de workstream sans intégration immédiate dans la
  branche principale du dépôt, afin de ne pas bloquer les autres workstreams.

**Contexte** : ce workstream est lié à un **engagement client ASUS / NVIDIA**.
C'est une contrainte externe de livraison, pas seulement un exercice technique.

Pourquoi ce stream est parallélisable :

- impact surtout config, benchmark, compose, scripts ;
- impact ciblé sur le contrat agent / modèle pour le `reasoning effort` ;
- faible recouvrement avec dataprep et writer ;
- très bonne candidate pour un coding agent dédié.

## WS2 - DevEx / Packaging

Features :

- `S1-01`

Pourquoi ce stream est parallélisable :

- extrêmement isolé ;
- faible conflit de merge ;
- amélioration immédiate de toute la suite.

## WS3 - Dataprep / Ingestion / Classification

Features :

- `S1-09`
- `S1-10`
- `S1-11`
- `S1-12`

Pourquoi ce stream est parallélisable :

- focalisé sur dataprep / ingestion / knowledge metadata ;
- peu de recouvrement avec le writer ;
- forte cohérence fonctionnelle interne.

## WS4 - Workflow agentique coeur

Features minimum viable :

- `S1-05` (gate bloquant si aucune source)
- `S1-06` (isolation writer)

Features stretch :

- `S1-07` (contrat RAW -> NORMALIZED)
- `S1-08` (validation humaine agenda)

`S1-05` et `S1-06` constituent le **noyau dur** de WS4 pour ce sprint. `S1-07`
et `S1-08` sont des stretch goals : souhaitables, mais le sprint est considéré
comme réussi sans eux.

Pourquoi ce stream doit être plus coordonné :

- forte proximité manager / planner / writer ;
- risque de conflits si plusieurs agents touchent les mêmes contrats en même
  temps ;
- nécessite un ordre d'intégration plus strict.

### Issues facilitatrices

- `#96` (éviter mutations globales de config) peut faciliter `S1-06` — à
  traiter en opportunité si rencontrée.
- `#101` (missing sources non-fatal) couvre un périmètre très proche de
  `S1-05` — vérifier si elle peut être adressée en même temps ou devient
  redondante.

---

## 5. Backlog détaillé prêt à ouvrir

## S1-01 - Evaluer puis migrer de Poetry vers uv

### Epic

`E9 - DevEx & Packaging`

### Issue existante

Réutiliser `#128`.

### Pourquoi maintenant

- quick win ;
- améliore la CI/CD ;
- améliore le travail parallèle de plusieurs coding agents ;
- sujet peu couplé au coeur fonctionnel.

### Périmètre recommandé

- évaluer le gain local + CI ;
- décider migration complète ou mode hybride ;
- adapter installation projet ;
- adapter GitHub Actions ;
- mettre à jour la documentation de setup.

### Dépendances

Aucune forte.

### Risque

Faible à moyen.

### Critère de done

- décision claire `uv` ;
- CI compatible ;
- installation locale documentée ;
- pas de régression de workflow principal.

---

## S1-02 - Ajouter le hash du syllabus dans les artefacts benchmark

### Epic

`E4 - Benchmarks & Traceability`

### Issue existante

Réutiliser `#95`.

### Pourquoi maintenant

- petite feature ;
- améliore immédiatement la crédibilité benchmark ;
- indépendante du coeur produit.

### Périmètre recommandé

- calcul d'un hash stable du syllabus ;
- stockage dans l'artefact benchmark ;
- affichage dans les sorties utiles ;
- compatibilité ascendante avec anciens artefacts.

### Dépendances

Aucune forte.

### Risque

Faible.

### Critère de done

- hash présent dans tous les nouveaux runs ;
- ancien comparateur non cassé ;
- tests ajoutés.

---

## S1-03 - Rendre le backend d'inférence sélectionnable au démarrage avec priorité vLLM

### Epic

`E1 - Inference Platform`

### Issue

Nouvelle issue à créer.

### Titre proposé

`Feature: rendre le backend d'inférence sélectionnable au démarrage avec priorité vLLM`

### Pourquoi maintenant

- prépare les comparaisons moteurs ;
- prépare DGX cluster ;
- reste compatible avec une approche incrémentale.

### Périmètre recommandé

- choix du backend via config / compose ;
- priorité initiale à `vLLM` ;
- possibilité de s'appuyer sur `https://github.com/eugr/spark-vllm-docker` ;
- pas de sélection dynamique à chaud ;
- compatibilité avec modèle mono ou split si possible ;
- doc d'usage simple.

### Dépendances

Faibles.

### Risque

Moyen.

### Critère de done

- backend sélectionnable sans modification manuelle profonde du code ;
- `vLLM` supporté comme backend cible ;
- documentation claire de configuration.

---

## S1-04 - Valider un mode mono gros modèle sur dual DGX avec gpt-oss-120B

### Epic

`E1 - Inference Platform`

### Issue

Nouvelle issue à créer.

### Titre proposé

`Spike: valider agentic-research sur un mode mono gros modèle avec vLLM et gpt-oss-120B`

### Pourquoi maintenant

- aligné avec l'échéance partenariat et démonstration Q2 ;
- permet une décision technique sans figer toute l'architecture ;
- peut devenir une clé de succès du sprint.

### Périmètre recommandé

- définir le setup cible dual DGX Spark avec `vLLM` ;
- remonter le `reasoning effort` au niveau agent / orchestration ;
- ne plus faire porter le mode reasoning par les paramètres globaux du moteur ;
- valider l'exécution sur `gpt-oss-120B` en mode instruct + reasoning ;
- comparer vs setup actuel multi-modèles si utile ;
- documenter forces / limites / décision.

### Sous-tâche : étude reasoning effort par famille de modèles

Le déplacement du reasoning effort au niveau agent est plus complexe qu'un
simple flag config. Chaque famille de modèles a son propre mécanisme :

| Modèle       | Mécanisme moteur d'inférence                        | Mécanisme côté prompt / API                                      |
| ------------ | --------------------------------------------------- | ---------------------------------------------------------------- |
| OpenAI natif | `reasoning_effort` param                            | natif dans l'API                                                 |
| Nemotron     | `--reasoning-parser nemotron_v3`                    | `extra_body={"chat_template_kwargs": {"enable_thinking": True}}` |
| Qwen 3       | `--enable-reasoning --reasoning-parser deepseek_r1` | `/think` dans le user input                                      |

Ref: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4

**Action requise avant implémentation** : produire une note d'étude couvrant :

1. les mécanismes de reasoning par famille de modèles cible ;
2. le niveau d'abstraction pertinent (config agent ? paramètre d'appel ?
   template ?) ;
3. la compatibilité avec le workflow multi-modèles existant, pour que le
   résultat soit mergeable aussi dans WS4 à terme.

### Stretch goals

- `nvidia/Qwen3.5-397B-A17B-NVFP4`
- `nvidia/Gemma-4-31B-IT-NVFP4`
- `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`

### Dépendances

- idéalement `S1-03` ou au moins une configurabilité minimale.

### Risque

Moyen.

### Critère de done

- `agentic-research` fonctionne sur `gpt-oss-120B` via `vLLM` en mode
  mono-modèle ;
- le `reasoning effort` est piloté côté agent et non plus uniquement côté
  moteur ;
- note d'étude reasoning effort produite et validée ;
- note de décision technique produite ;
- résultats comparatifs exploitables si comparaison effectuée ;
- recommandation explicite pour la suite.

---

## S1-05 - Bloquer la génération de report si aucune source exploitable n'a été produite

### Epic

`E6 - Intermediate Controllers`

### Issue existante

Réutiliser `#145`.

### Pourquoi maintenant

- corrige un faux positif critique ;
- augmente immédiatement la confiance produit ;
- faible coût relatif.

### Périmètre recommandé

- gate bloquant si aucun résultat de recherche exploitable ;
- signalement clair dans le workflow ;
- benchmark / évaluation compatible avec cet échec attendu.

### Dépendances

Faibles.

### Risque

Faible à moyen.

### Critère de done

- aucun report final ne peut être produit sans source ;
- les runs concernés sont explicitement marqués comme échec / incomplets ;
- tests couvrant le cas.

---

## S1-06 - Isoler le writer du prompt utilisateur et de la conversation longue

### Epic

`E8 - Writer Quality & Context Engineering`

### Issue

Nouvelle issue à créer.

### Titre proposé

`Feature: isoler le writer du prompt utilisateur et de la conversation longue`

### Pourquoi maintenant

- fondation de qualité ;
- réduit la contamination du writer ;
- prérequis indirect pour la parallélisation future.

### Périmètre recommandé

- le writer ne reçoit plus directement la demande utilisateur brute ;
- il reçoit un contexte réduit, structuré et orienté report neutre ;
- la logique reste incrémentale sans refonte totale du manager.

### Dépendances

- aucune forte, mais forte proximité avec `S1-07`.

### Risque

Moyen.

### Critère de done

- le writer est alimenté par un contrat intermédiaire plus propre ;
- amélioration mesurable sur cas de dérive connus ;
- pas de régression sur les cas déjà stables.

---

## S1-07 - Formaliser le contrat writer RAW -> NORMALIZED

### Epic

`E8 - Writer Quality & Context Engineering`

### Issue

Nouvelle issue à créer.

### Titre proposé

`Feature: formaliser le contrat writer RAW -> NORMALIZED pour les reports neutres`

### Pourquoi maintenant

- clarifie la sortie canonique du système ;
- prépare `E3` et `E7` ;
- évite de mélanger report neutre et livrable stylisé.

### Pré-requis bloquant

**Ne pas commencer l'implémentation tant que le contrat cible n'est pas
défini et validé.**

Ordre des tâches :

1. **Définir le contrat** (schéma, frontières, formats) — bloquant
2. Review / validation du contrat
3. Implémenter les adaptations prompts / orchestration
4. Tests

### Périmètre recommandé

- définir le schéma minimal de l'output NORMALIZED (ex: title, sections[],
  sources[], metadata) ;
- formaliser l'entrée du writer neutre ;
- formaliser sa sortie attendue ;
- documenter la séparation `RAW -> NORMALIZED -> USAGE` ;
- adapter prompts / contrat sans refonte lourde du reste.

### Dépendances

- forte cohérence avec `S1-06`.

### Risque

Moyen.

### Critère de done

- contrat explicite documenté avec schéma cible ;
- output neutre mieux défini ;
- base claire pour le lifecycle de connaissance.

---

## S1-08 - Ajouter une validation humaine de l'agenda en V1 simple

### Epic

`E5 - HITL & Recovery`

### Issue

Nouvelle issue à créer.

### Titre proposé

`Feature: ajouter une validation humaine de l'agenda en V1 simple`

### Pourquoi maintenant

- rend l'humain visible dans la boucle ;
- augmente la confiance produit ;
- version étroite et concrète du HITL.

### Périmètre recommandé

- point d'arrêt après agenda ;
- validation explicite pour continuer ;
- refus / ajustement simple ;
- pas de durable execution complète dans cette première version.

### Dépendances

- proximité fonctionnelle avec `S1-06` et `S1-07`.

### Risque

Moyen.

### Critère de done

- agenda visible et validable ;
- le workflow n'avance pas sans validation explicite ;
- le chemin de poursuite reste simple et testable.

---

## S1-09 - Ajouter l'ingestion PDF texte natif côté dataprep

### Epic

`E2 - Document Ingestion`

### Issue existante

Réutiliser `#102`.

### Pourquoi maintenant

- ouvre des cas d'usage réels finance / recherche ;
- blocage fonctionnel clair aujourd'hui ;
- bonne valeur produit immédiate.

### Périmètre recommandé

- parsing PDF texte natif ;
- indexation lisible ;
- support local file et output de téléchargement ;
- logs utiles d'extraction.

### Dépendances

Faibles.

### Risque

Moyen.

### Critère de done

- des PDF texte sont correctement indexés ;
- le contenu retrouvé est exploitable ;
- les gros fichiers ne cassent pas le processus.

---

## S1-10 - Rendre le chunking PDF gros fichier sûr et déterministe

### Epic

`E2 - Document Ingestion`

### Issue

Nouvelle issue ou sous-partie de `#102`.

### Titre proposé

`Enhancement: sécuriser le chunking et l'indexation des gros PDF`

### Pourquoi maintenant

- complète `S1-09` ;
- évite une V1 fragile sur documents réels.

### Périmètre recommandé

- chunking page-aware si possible ;
- limites sûres sur extraction ;
- traitement déterministe ;
- garde-fous mémoire / taille.

### Dépendances

- `S1-09`.

### Risque

Moyen.

### Critère de done

- comportement stable sur gros PDF ;
- chunking reproductible ;
- logs d'indexation utiles.

---

## S1-11 - Générer les métadonnées de classification pour l'ingestion locale

### Epic

`E12 - Classification Agents`

### Issue existante

Réutiliser `#103`.

### Pourquoi maintenant

- harmonise le comportement URL vs fichiers locaux ;
- fondation directe pour classification et knowledge lifecycle ;
- bon sujet dataprep autonome.

### Périmètre recommandé

- résumé ;
- tags ;
- fallback si LLM désactivé ;
- mise à jour de la knowledge base locale.

### Dépendances

Faibles.

### Risque

Faible à moyen.

### Critère de done

- les fichiers locaux reçoivent des métadonnées cohérentes ;
- le comportement se rapproche de l'ingestion URL ;
- tests couvrants.

---

## S1-12 - Exposer la classification documentaire comme capacité réutilisable

### Epic

`E12 - Classification Agents`

### Issue

Nouvelle issue à créer.

### Titre proposé

`Feature: exposer la classification documentaire comme capacité réutilisable dans dataprep`

### Pourquoi maintenant

- transforme une logique implicite en vraie capacité produit ;
- prépare `E3` et `E13` ;
- bon candidat pour un coding agent séparé.

### Périmètre recommandé

- factoriser la logique de classification existante ;
- l'appeler de manière unitaire ;
- pouvoir la réutiliser à l'ajout de source ou plus tard à l'ajout de report ;
- ne pas encore chercher à couvrir tous les connecteurs.

### Dépendances

- idéalement `S1-11`.

### Risque

Moyen.

### Critère de done

- la classification n'est plus seulement un effet de bord ;
- elle est appelable comme brique distincte ;
- base posée pour les connecteurs et le lifecycle.

---

## 6. Ordre recommandé d'ouverture des issues

Pour éviter un backlog désordonné, l'ordre d'ouverture recommandé est :

1. `#128` - `S1-01`
2. `#95` - `S1-02`
3. nouvelle issue `S1-03`
4. nouvelle issue `S1-04`
5. `#145` - `S1-05`
6. nouvelle issue `S1-06`
7. nouvelle issue `S1-07`
8. nouvelle issue `S1-08`
9. `#102` - `S1-09`
10. nouvelle issue `S1-10` ou intégration dans `#102`
11. `#103` - `S1-11`
12. nouvelle issue `S1-12`

Cet ordre permet :

- d'ouvrir vite les quick wins ;
- de lancer les spikes et streams parallèles ;
- de garder le coeur workflow groupé ;
- de rattacher les sujets déjà existants avant de créer de nouvelles issues.

---

## 7. Recommandation d'assignation par workstream

### Coding agent A - WS2 DevEx

- `S1-01`

### Coding agent B - WS1 Inference

- `S1-02`
- `S1-03`
- `S1-04`

### Coding agent C - WS3 Dataprep

- `S1-09`
- `S1-10`
- `S1-11`
- `S1-12`

### Coding agent D - WS4 Workflow coeur

- `S1-05`
- `S1-06`
- `S1-07`
- `S1-08`

Important :

- `S1-06`, `S1-07` et `S1-08` doivent être séquencées proprement pour éviter les
  conflits.
- si plusieurs agents interviennent sur WS4, il faut définir une ownership très
  claire par fichier / contrat.

---

## 8. Ce qui reste volontairement hors Sprint 1

Pour garder un sprint réaliste, les sujets suivants ne doivent pas être ouverts
comme objectifs Sprint 1 principaux :

- `E3` lifecycle complet de la connaissance ;
- `E6` contrôleurs agentiques avancés ;
- `E7` parallélisation complète du writer ;
- `E10` MCP distant ;
- `E11` mode service ;
- `E13` connecteurs carnet de notes ;
- `E14` lint périodique des reports / wiki.

Ils peuvent rester dans la roadmap, mais pas dans le lot principal à lancer
immédiatement.

---

## 9. Recommandation finale

Le backlog Sprint 1 doit être ouvert comme un **lot cohérent mais non monolithique** :

- un noyau workflow (`S1-05` à `S1-08`) ;
- un noyau dataprep (`S1-09` à `S1-12`) ;
- deux streams d'enablers (`S1-01` à `S1-04`).

La meilleure stratégie est donc :

- ouvrir les issues existantes déjà exploitables ;
- créer les nouvelles issues manquantes avec le découpage ci-dessus ;
- lancer en parallèle `WS1`, `WS2`, `WS3` ;
- garder `WS4` plus étroitement coordonné.

Dans `WS1`, la cible prioritaire n'est pas de comparer tous les moteurs dès le
départ, mais de sécuriser un premier succès sur `vLLM` avec `gpt-oss-120B` en
mode mono-modèle.
