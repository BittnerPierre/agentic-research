# Agent Engineer Fondations Course

## Raw Notes

Definitions and composants essentiels:
- Un agent est une entité capable de percevoir son environnement via des capteurs et d'agir via des effecteurs. Les agents IA sont munis d'un modèle d'intelligence leur permettant de planifier, raisonner, et exécuter des tâches.
- Les systèmes multi-agents (SMA) se composent typiquement d'agents spécialisés et d'une architecture orchestratrice où un agent principal (orchestrateur) coordonne le travail des sous-agents (agents travailleurs) opérant souvent en parallèle.
- L'environnement définit le cadre où les agents évoluent et leurs capacités d'action. Les outils accessibles aux agents sont cruciaux pour leurs performances, car ils étendent leur capacité d'action et de perception.

Modèles d'interaction:
- L'architecture orchestrateur-travailleurs est courante, avec un agent principal qui décompose la tâche utilisateur en sous-tâches qu'il distribue à des sous-agents spécialisés effectuant des recherches ou traitements parallèles.
- Les agents communiquent via des échanges d'informations itératifs, s'évaluant mutuellement, adaptant leurs stratégies selon les résultats intermédiaires, ce qui permet une flexibilité nécessaire à des tâches incertaines et dynamiques comme la recherche.
- L'utilisation simultanée de plusieurs agents avec leurs propres contextes permet de gérer des volumes d'information dépassant la capacité contextuelle d'un agent unique.

Principes de conception:
- La décomposition des tâches complexes en sous-tâches gérables facilite la coordination et la spécialisation des agents.
- L'ingénierie des prompts est cruciale pour guider les agents, notamment pour expliquer clairement les objectifs, les limites des tâches, et les outils pertinents à utiliser.
- Un équilibre doit être trouvé entre la complexité des agents et la gestion de leurs erreurs, puisque des erreurs mineures peuvent avoir des effets cumulatifs importantes.
- L'évaluation des agents privilégie des critères d'état final plutôt que des étapes précises, compte tenu de la diversité des trajectoires possibles pour atteindre un but donné.
- Les systèmes doivent gérer la persistance et la mémoire pour maintenir la cohérence sur des interactions longues.
- La parallélisation, tant dans la génération de plans que dans l'exécution des sous-tâches, améliore considérablement l'efficacité.
- La robustesse en production nécessite des architectures capables de reprendre d'erreurs et d'intégrer les retours utilisateur pour améliorer la coordination et la fiabilité.

Sources :
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

## Detailed Agenda

- Introduction
  - Contexte et objectifs du cours
  - Définitions clés
- Fondamentaux des agents intelligents
  - Définition d'un agent
  - Capteurs et effecteurs
  - Modèle d'intelligence: planification, raisonnement, exécution
- Architectures des systèmes multi-agents
  - Orchestrateur-travailleurs
  - Agents spécialisés et parallélisme
  - Environnements et outils
- Modèles d'interaction et communication
  - Échanges itératifs et adaptation
  - Gestion de contextes multiples
- Principes de conception et ingénierie des prompts
  - Décomposition des tâches
  - Ingénierie des prompts
  - Équilibre complexité/gestion d'erreurs
  - Critères d'évaluation basés sur l'état final
  - Persistance et mémoire
  - Parallélisation et robustesse en production
- Cas d'usage et applications
  - Recherche complexe
  - Analyse de grandes bases de données
  - Interfaçage avec des outils multiples
- Conclusion et recommandations
  - Bonnes pratiques
  - Perspectives
- Références

## Report

Introduction

Contexte et objectifs du cours

Le présent rapport traite du thème "Agent Engineer Fondations Course" avec un focus sur les systèmes multi-agents en IA. Il vise à présenter les éléments fondamentaux, les architectures, les modèles d'interaction, et les principes de conception nécessaires pour concevoir, évaluer et déployer des systèmes multi-agents performants.

Définitions clés

Un agent est une entité capable de percevoir son environnement via des capteurs et d'agir via des effecteurs. Les agents IA sont munis d'un modèle d'intelligence leur permettant de planifier, raisonner, et exécuter des tâches.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

Fondamentaux des agents intelligents

Définition d'un agent

Un agent est une entité capable de percevoir son environnement via des capteurs et d'agir via des effecteurs. Les agents IA sont munis d'un modèle d'intelligence leur permettant de planifier, raisonner, et exécuter des tâches.

Capteurs et effecteurs

Un agent perçoit son environnement via des capteurs et agit via des effecteurs. L'environnement définit le cadre où les agents évoluent et leurs capacités d'action.

Modèle d'intelligence: planification, raisonnement, exécution

Les agents IA sont munis d'un modèle d'intelligence leur permettant de planifier, raisonner, et exécuter des tâches.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

Architectures des systèmes multi-agents

Orchestrateur-travailleurs

Les systèmes multi-agents (SMA) se composent typiquement d'agents spécialisés et d'une architecture orchestratrice où un agent principal (orchestrateur) coordonne le travail des sous-agents (agents travailleurs) opérant souvent en parallèle.

Agents spécialisés et parallélisme

L'architecture orchestrateur-travailleurs est courante, avec un agent principal qui décompose la tâche utilisateur en sous-tâches qu'il distribue à des sous-agents spécialisés effectuant des recherches ou traitements parallèles.

Environnements et outils

L'environnement définit le cadre où les agents évoluent et leurs capacités d'action. Les outils accessibles aux agents sont cruciaux pour leurs performances, car ils étendent leur capacité d'action et de perception.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

Modèles d'interaction et communication

Échanges itératifs et adaptation

Les agents communiquent via des échanges d'informations itératifs, s'évaluant mutuellement, adaptant leurs stratégies selon les résultats intermédiaires, ce qui permet une flexibilité nécessaire à des tâches incertaines et dynamiques comme la recherche.

Gestion de contextes multiples

L'utilisation simultanée de plusieurs agents avec leurs propres contextes permet de gérer des volumes d'information dépassant la capacité contextuelle d'un agent unique.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

Principes de conception et ingénierie des prompts

Décomposition des tâches

La décomposition des tâches complexes en sous-tâches gérables facilite la coordination et la spécialisation des agents.

Ingénierie des prompts

L'ingénierie des prompts est cruciale pour guider les agents, notamment pour expliquer clairement les objectifs, les limites des tâches, et les outils pertinents à utiliser.

Équilibre complexité/gestion d'erreurs

Un équilibre doit être trouvé entre la complexité des agents et la gestion de leurs erreurs, puisque des erreurs mineures peuvent avoir des effets cumulatifs importantes.

Critères d'évaluation basés sur l'état final

L'évaluation des agents privilégie des critères d'état final plutôt que des étapes précises, compte tenu de la diversité des trajectoires possibles pour atteindre un but donné.

Persistance et mémoire

Les systèmes doivent gérer la persistance et la mémoire pour maintenir la cohérence sur des interactions longues.

Parallélisation et robustesse en production

La parallélisation, tant dans la génération de plans que dans l'exécution des sous-tâches, améliore considérablement l'efficacité. La robustesse en production nécessite des architectures capables de reprendre d'erreurs et d'intégrer les retours utilisateur pour améliorer la coordination et la fiabilité.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

Cas d'usage et applications

Recherche complexe

Ces principes architecturaux permettent aux systèmes multi-agents IA d'exceller dans des tâches ouvertes, dynamiques et volumineuses, telles que la recherche complexe, l'analyse de grandes bases de données, ou l'interfaçage avec des outils multiples, en tirant parti de la coordination, la spécialisation et la parallélisation des agents autonomes.

Analyse de grandes bases de données

Ces principes architecturaux permettent aux systèmes multi-agents IA d'exceller dans des tâches ouvertes, dynamiques et volumineuses, telles que la recherche complexe, l'analyse de grandes bases de données, ou l'interfaçage avec des outils multiples, en tirant parti de la coordination, la spécialisation et la parallélisation des agents autonomes.

Interfaçage avec des outils multiples

Ces principes architecturaux permettent aux systèmes multi-agents IA d'exceller dans des tâches ouvertes, dynamiques et volumineuses, telles que la recherche complexe, l'analyse de grandes bases de données, ou l'interfaçage avec des outils multiples, en tirant parti de la coordination, la spécialisation et la parallélisation des agents autonomes.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

Conclusion et recommandations

Bonnes pratiques

Décomposer les tâches, concevoir des prompts clairs, gérer la mémoire et la persistance, paralléliser les tâches lorsque c'est pertinent, et prévoir des mécanismes de reprise d'erreurs et d'intégration des retours utilisateur.

Perspectives

Les architectures multi-agents restent adaptées aux tâches ouvertes, dynamiques et volumineuses et continueront d'évoluer en améliorant la coordination, la spécialisation et la robustesse.

Références et sources:
- How we built our multi, Anthropic engineer blog (2025)
- Agents, AI engineering book and blog by Huyen Chip (2025)
- LLM Powered Autonomous Agents, Lilian Weng blog (2023)

## FINAL STEP
