# Agent Engineer Fondations Course

## Raw Notes

### Fondamentaux des agents intelligents et leurs architectures

- L'architecture fondamentale des systèmes multi-agents en intelligence artificielle (IA) repose sur la collaboration coordonnée de plusieurs agents autonomes qui perçoivent leur environnement et interagissent pour atteindre des objectifs complexes que des agents uniques ne pourraient pas accomplir efficacement.
- Un agent est une entité capable de percevoir son environnement via des capteurs et d'agir via des effecteurs. Les agents IA sont munis d'un modèle d'intelligence leur permettant de planifier, raisonner, et exécuter des tâches.
- Les systèmes multi-agents (SMA) se composent typiquement d'agents spécialisés et d'une architecture orchestratrice où un agent principal (orchestrateur) coordonne le travail des sous-agents (agents travailleurs) opérant souvent en parallèle.
- L'environnement définit le cadre où les agents évoluent et leurs capacités d'action. Les outils accessibles aux agents sont cruciaux pour leurs performances, car ils étendent leur capacité d'action et de perception.
- L'architecture orchestrateur-travailleurs est courante, avec un agent principal qui décompose la tâche utilisateur en sous-tâches qu'il distribue à des sous-agents spécialisés effectuant des recherches ou traitements parallèles.
- Les agents communiquent via des échanges d'informations itératifs, s'évaluant mutuellement, adaptant leurs stratégies selon les résultats intermédiaires, ce qui permet une flexibilité nécessaire à des tâches incertaines et dynamiques comme la recherche.
- L'utilisation simultanée de plusieurs agents avec leurs propres contextes permet de gérer des volumes d'information dépassant la capacité contextuelle d'un agent unique.
- La décomposition des tâches complexes en sous-tâches gérables facilite la coordination et la spécialisation des agents.
- L'ingénierie des prompts est cruciale pour guider les agents, notamment pour expliquer clairement les objectifs, les limites des tâches, et les outils pertinents à utiliser.
- Un équilibre doit être trouvé entre la complexité des agents et la gestion de leurs erreurs, puisque des erreurs mineures peuvent avoir des effets cumulatifs importants.
- L'évaluation des agents privilégie des critères d'état final plutôt que des étapes précises, compte tenu de la diversité des trajectoires possibles pour atteindre un but donné.
- Les systèmes doivent gérer la persistance et la mémoire pour maintenir la cohérence sur des interactions longues.
- La parallélisation, tant dans la génération de plans que dans l'exécution des sous-tâches, améliore considérablement l'efficacité.
- La robustesse en production nécessite des architectures capables de reprendre d'erreurs et d'intégrer les retours utilisateur pour améliorer la coordination et la fiabilité.

### Sources

- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

## Detailed Agenda

### Introduction
- Définition des agents intelligents
- Importance des systèmes multi-agents en IA

### Architecture des systèmes multi-agents
- Définition et composants essentiels
  - Agents autonomes
  - Environnement et outils
  - Architecture orchestrateur-travailleurs
- Modèles d'interaction
  - Communication entre agents
  - Flexibilité et adaptation
  - Gestion des volumes d'information

### Principes de conception
- Décomposition des tâches complexes
- Ingénierie des prompts
- Équilibre entre complexité et gestion des erreurs
- Évaluation des agents
- Persistance et mémoire
- Parallélisation
- Robustesse en production

### Conclusion
- Récapitulatif des points clés
- Importance des principes architecturaux

## Report

### Introduction

Les agents intelligents sont des entités capables de percevoir leur environnement et d'agir de manière autonome pour accomplir des tâches complexes. En intelligence artificielle (IA), les systèmes multi-agents (SMA) jouent un rôle crucial en permettant la collaboration coordonnée de plusieurs agents, ce qui dépasse les capacités d'un agent unique. Ce rapport explore les fondements des agents intelligents et leurs architectures, en mettant l'accent sur les systèmes multi-agents.

### Architecture des systèmes multi-agents

#### Définition et composants essentiels

Un agent est une entité capable de percevoir son environnement via des capteurs et d'agir via des effecteurs. Les agents IA sont munis d'un modèle d'intelligence leur permettant de planifier, raisonner et exécuter des tâches. Les systèmes multi-agents se composent typiquement d'agents spécialisés et d'une architecture orchestratrice où un agent principal (orchestrateur) coordonne le travail des sous-agents (agents travailleurs) opérant souvent en parallèle.

L'environnement définit le cadre où les agents évoluent et leurs capacités d'action. Les outils accessibles aux agents sont cruciaux pour leurs performances, car ils étendent leur capacité d'action et de perception. Par exemple, un agent peut utiliser des outils pour interagir avec des bases de données ou des interfaces utilisateur, ce qui lui permet d'accomplir des tâches plus complexes et variées.

#### Modèles d'interaction

L'architecture orchestrateur-travailleurs est courante, avec un agent principal qui décompose la tâche utilisateur en sous-tâches qu'il distribue à des sous-agents spécialisés effectuant des recherches ou traitements parallèles. Les agents communiquent via des échanges d'informations itératifs, s'évaluant mutuellement et adaptant leurs stratégies selon les résultats intermédiaires. Cette flexibilité est nécessaire pour des tâches incertaines et dynamiques comme la recherche.

L'utilisation simultanée de plusieurs agents avec leurs propres contextes permet de gérer des volumes d'information dépassant la capacité contextuelle d'un agent unique. Par exemple, dans un système de recherche complexe, plusieurs agents peuvent travailler en parallèle sur différentes parties de la tâche, ce qui permet de traiter des volumes de données plus importants et d'obtenir des résultats plus rapidement.

### Principes de conception

#### Décomposition des tâches complexes

La décomposition des tâches complexes en sous-tâches gérables facilite la coordination et la spécialisation des agents. Par exemple, une tâche complexe comme la recherche d'informations dans une grande base de données peut être décomposée en plusieurs sous-tâches, chacune étant attribuée à un agent spécialisé. Cela permet de mieux gérer la complexité et d'améliorer l'efficacité globale du système.

#### Ingénierie des prompts

L'ingénierie des prompts est cruciale pour guider les agents, notamment pour expliquer clairement les objectifs, les limites des tâches, et les outils pertinents à utiliser. Un bon prompt doit être clair et précis, fournissant suffisamment d'informations pour que l'agent puisse comprendre la tâche et agir de manière appropriée. Par exemple, un prompt bien conçu peut inclure des instructions détaillées sur les étapes à suivre, les outils à utiliser, et les critères d'évaluation à respecter.

#### Équilibre entre complexité et gestion des erreurs

Un équilibre doit être trouvé entre la complexité des agents et la gestion de leurs erreurs, puisque des erreurs mineures peuvent avoir des effets cumulatifs importants. Par exemple, un système trop complexe peut être difficile à gérer et à déboguer, tandis qu'un système trop simple peut ne pas être capable d'accomplir des tâches complexes. Il est donc important de concevoir des agents qui sont suffisamment complexes pour accomplir leurs tâches, mais pas trop complexes pour éviter des erreurs cumulatives.

#### Évaluation des agents

L'évaluation des agents privilégie des critères d'état final plutôt que des étapes précises, compte tenu de la diversité des trajectoires possibles pour atteindre un but donné. Par exemple, plutôt que d'évaluer chaque étape d'un processus, il peut être plus efficace d'évaluer l'état final atteint par l'agent. Cela permet de prendre en compte la diversité des trajectoires possibles et de se concentrer sur le résultat final.

#### Persistance et mémoire

Les systèmes doivent gérer la persistance et la mémoire pour maintenir la cohérence sur des interactions longues. Par exemple, dans un système de dialogue, il est important de maintenir la cohérence des informations échangées sur une longue période. Cela peut être accompli en utilisant des mécanismes de persistance et de mémoire qui permettent de stocker et de récupérer des informations pertinentes.

#### Parallélisation

La parallélisation, tant dans la génération de plans que dans l'exécution des sous-tâches, améliore considérablement l'efficacité. Par exemple, en exécutant plusieurs sous-tâches en parallèle, un système multi-agents peut accomplir des tâches complexes plus rapidement et plus efficacement. Cela permet de mieux utiliser les ressources disponibles et d'améliorer les performances globales du système.

#### Robustesse en production

La robustesse en production nécessite des architectures capables de reprendre d'erreurs et d'intégrer les retours utilisateur pour améliorer la coordination et la fiabilité. Par exemple, un système robuste doit être capable de détecter et de corriger les erreurs, ainsi que d'intégrer les retours utilisateur pour améliorer ses performances. Cela permet d'assurer une coordination et une fiabilité optimales en production.

### Conclusion

Les principes architecturaux des systèmes multi-agents en IA permettent de concevoir des systèmes capables d'accomplir des tâches complexes et dynamiques de manière efficace et fiable. En tirant parti de la collaboration coordonnée de plusieurs agents autonomes, ces systèmes peuvent exceller dans des tâches ouvertes, dynamiques et volumineuses, telles que la recherche complexe, l'analyse de grandes bases de données, ou l'interfaçage avec des outils multiples.

## FINAL STEP
