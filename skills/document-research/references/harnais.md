# Portabilité : ce que le skill attend du harnais

Ce skill suit le standard Agent Skills (un dossier, `SKILL.md` à la racine,
références à côté). Il ne dépend d'aucun SDK ni d'aucune API propre à un
fournisseur. Il attend du harnais qui l'exécute quatre capacités génériques,
plus les outils MCP du mode dataprep (protocole ouvert) :

| Capacité attendue | Usage dans le skill | Si absente |
|---|---|---|
| Lire, écrire et éditer des fichiers du dossier de travail | livrables, extraits, manuscrit, corrections ciblées | indispensable |
| Lister et rechercher du texte dans des fichiers (mode fichiers) | extracteurs, catalogue | mode dataprep seulement |
| Déléguer une tâche à un sous-agent à contexte frais, en parallèle, avec un modèle éventuellement différent | extracteurs (étape 3), relecteur (étape 7) | le responsable exécute lui-même les contrats d'extracteur, un par un, en gardant les plafonds ; coût et durée augmentent |
| Shell pour exécuter les scripts Python 3 du package (`python3 scripts/*.py`) | inventaire, extraction verbatim, contrôles, assemblage | le modèle fait le travail lui-même (recopie, comptage) : coût et risque d'erreur augmentent |
| Client MCP (mode dataprep) | acquisition, indexation, catalogue, `vector_search` | mode fichiers seulement |

Correspondance indicative des noms d'outils (informative, ne pas la recopier
dans les consignes) :

| Capacité | Claude Code | Codex CLI | Deep Agents (LangChain) |
|---|---|---|---|
| lecture / écriture / édition | Read, Write, Edit | fichiers via shell ou outils d'édition | filesystem virtuel (read_file, write_file, edit_file) |
| listage / recherche | Glob, Grep | shell (ls, grep) | ls, grep |
| sous-agent | Agent (paramètre `model`) | sous-agents | task (sous-agents à contexte frais) |
| shell | Bash (allowlist) | shell | sandbox |
| MCP | mcp-config | MCP | MCP |

Ce que le skill n'utilise jamais : appels directs à une API de modèle, SDK
d'agents, formats d'événements ou d'états propres à un harnais. Les mesures
(coût, tokens, durée par étape) sont produites par le harnais et
l'adaptateur, hors du skill.
