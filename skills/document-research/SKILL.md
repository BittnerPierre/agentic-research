---
name: document-research
description: >-
  Produit un rapport consolidé de connaissances sur un thème à partir d'un
  fonds documentaire FERMÉ (fichiers locaux ou base de connaissances dataprep
  via MCP), en suivant les 8 étapes du processus de recherche documentaire
  (cadrage, collecte, sélection et extraction, analyse, conception, rédaction,
  révision, livraison) avec un livrable court et lisible par étape, une main
  courante, des citations verbatim traçables et un budget serré (tours, tokens,
  temps, coût). Utiliser ce skill quand on demande une synthèse documentaire,
  un dossier de fond, un brief, un état de l'art ou un rapport de recherche
  sourcé sur un corpus donné (audit flash, dossier pour un script vidéo, note
  de synthèse, data pack). NE PAS l'utiliser pour une question ponctuelle, une
  recherche web ouverte ou un texte sans sources.
---

# Recherche documentaire en 8 étapes, à budget fermé

Tu es le **responsable** d'une recherche documentaire : tu planifies, tu
délègues des tâches bornées à des sous-agents à contexte minimal, tu
consolides et tu livres. Tu ne lis pas le fonds toi-même ; tu ne fais pas
circuler le corpus dans ton contexte. Chaque étape laisse un livrable court
dans le dossier de travail, pour qu'un humain puisse comprendre où un problème
est survenu et reprendre. Pas de boîte noire, pas de force brute.

Le fonds est **fermé** : seules les sources du fonds (ou celles que le brief
demande d'acquérir) alimentent le rapport. Aucune connaissance personnelle,
aucune recherche web.

## Objectif de coût, non négociable

Un run complet = **au plus 12 tours du responsable**, **5 à 8 sous-agents**
bornés, **moins de 4 minutes** si les sous-agents tournent en parallèle, et un
volume de tokens comparable à un workflow codé (ordre de grandeur 300 à 600 k
tokens tout compris). La consigne de lancement peut fixer un plafond monétaire
dur : s'il est atteint, le run est perdu. Donc :

- **Planifie d'abord, exécute une fois.** Le cadrage est un contrat de
  travail court ; les sous-agents partent tous en parallèle sur ce contrat.
- **Jamais de lecture intégrale du fonds par le responsable.** Tu lis le brief,
  le catalogue, les sorties compactes des sous-agents, et le manuscrit.
- **Sorties compactes entre étapes** : tables et listes, pas de prose ; pas de
  recopie d'extraits d'un fichier à l'autre.
- **Réserve** : les étapes 6 à 8 (rédaction, relecture, livraison) ont droit à
  un tiers du budget. Si l'extraction menace cette réserve, elle s'arrête et
  on livre avec les lacunes déclarées.
- **Le mécanique ne passe pas par le modèle.** Le package fournit des scripts
  Python autonomes (`scripts/`, voir `references/scripts.md`) : inventaire du
  fonds, extraction verbatim par plages de lignes, contrôle des extraits,
  vérification du manuscrit (citations, chiffres, sections, longueur),
  assemblage du rapport. Les utiliser à chaque fois qu'ils s'appliquent : un
  script coûte zéro token et ne se trompe pas en recopiant.

## Entrées

- `brief.md` : la demande (question, périmètre, format, longueur, langue,
  public, style, sources imposées). Ce qui manque est fixé au cadrage avec une
  valeur par défaut explicite.
- Le fonds, selon le mode annoncé dans la consigne de lancement :
  - **Mode fichiers** : dossier `fonds/` + `fonds/catalogue.md` (référence du
    brief → fichier). Les sous-agents lisent les fichiers (lecture de fichier, recherche textuelle).
  - **Mode dataprep (MCP)** : base de connaissances du serveur dataprep.
    Acquisition `download_and_store_url_tool`, indexation
    `upload_files_to_vectorstore_tool` dans une collection propre au run,
    catalogue `get_knowledge_entries_tool`, recherche `vector_search`
    (extraits identifiés par `chunk_id`). Voir `references/outils-retrieval.md`.
- Optionnel : `process-notes.md`, enseignements de processus des runs
  précédents (méthode, pièges, outils). Jamais de contenu sur les sources.

## Dossier de travail (un livrable court par étape)

```
01-cadrage/cadrage.md            ≤ 40 lignes : questions Q1..Qn, attentes de forme, politique de corpus, plan de délégation, budget par étape
01-cadrage/contrat.json          contrat de forme lisible par les scripts : sections, min_words, max_words, table_columns, language
02-collecte/bibliographie.md     table : référence → fichier/identifiant, nature, questions couvertes, statut
03-extraits/parts/Q<n>.jsonl     extraits VERBATIM avec provenance, UN fichier par sous-agent (contrat ci-dessous)
03-extraits/corpus-retenu.md     ≤ 15 lignes : documents mobilisés / écartés, lacunes constatées par question
04-analyse/synthese.md           par question : 3 à 8 puces référencées [E<n>] ; convergences, contradictions, lacunes
05-conception/plan.md            sections imposées → extraits mobilisés → lacunes à déclarer (une table)
06-redaction/manuscrit.md        texte complet
07-revision/verification.md      grille du relecteur : citations, chiffres, conformité au brief, longueur mesurée
08-livraison/rapport.md          document final (= manuscrit corrigé), avec section ## Sources
journal.md                       main courante : une ligne par étape, horodatée (voir references/main-courante.md)
retex.md                         ≤ 15 lignes : ce qui a bien/mal marché dans le PROCESSUS, budget consommé par étape
ARBITRAGE-REQUIS.md              seulement si un arbitrage humain est nécessaire
```

L'étape 4 « fiches de lecture » est portée par les fichiers `parts/*.jsonl`
eux-mêmes (extraits verbatim référencés, dédoublonnés par question) : ne les
recopie pas en prose.

## Les 8 étapes et leur budget

Détail et gabarits : `references/processus.md`.

1. **Cadrage** (1 tour) — Questions secondaires numérotées Q1..Qn, une par
   section imposée ou par thème du brief. Attentes de forme (format, sections,
   colonnes, longueur, langue, public, ton). Politique de corpus (fermé
   strict ; acquisition seulement des références nommées). **Plan de
   délégation** : un sous-agent par question (ou par paire de questions
   proches), avec pour chacun ses sources pressenties, son plafond d'extraits
   et de lectures ou de requêtes. Budget par étape écrit. Écris aussi
   `contrat.json` (sections imposées dans l'ordre, bornes de longueur,
   colonnes du tableau imposé, langue) : les scripts de vérification le lisent.
2. **Recherche et collecte** (1 tour, en mode dataprep : + acquisition et
   indexation, lancées en parallèle) — Bibliographie de travail à partir du
   catalogue (pas des documents). Mode fichiers : `scripts/inventory.py`
   (tailles, titres, mots-clés par fichier) pour affecter les sources aux
   extracteurs sans rien lire. Si le fonds ne peut manifestement pas
   couvrir le cœur de la demande : arbitrage.
3. **Sélection et extraction** (1 tour de lancement + 1 tour de
   consolidation) — Lance **tous les extracteurs en parallèle**, un par
   question, avec le contrat d'extrait, ses sources, la liste des questions
   des autres extracteurs (pour éviter les doublons) et ses plafonds
   (`references/sous-agents.md`). Chaque extracteur écrit
   `03-extraits/parts/Q<n>.jsonl` et te renvoie **un compte rendu de 10
   lignes maximum** : extraits produits, questions couvertes, ce qu'il n'a pas
   trouvé. Mode fichiers : l'extracteur repère les passages (`extract.py --find`,
   recherche textuelle, lecture ciblée) puis les matérialise par plages de
   lignes avec `scripts/extract.py --range fichier:debut-fin` : le script copie
   le texte exact, l'extracteur ne le recopie jamais. Mode dataprep : le texte
   renvoyé par `vector_search` va dans un fichier de spécification
   (`Q<n>.spec.json`) puis `extract.py --spec …`, une seule commande simple.
   Puis `scripts/verify_extracts.py` (déterministe) : identifiants uniques,
   verbatim, doublons ; tu écris `corpus-retenu.md` depuis les comptes rendus
   et ce contrôle.
4. **Analyse et synthèse** (1 tour) — Tu lis les `parts/*.jsonl` (compacts)
   et écris `synthese.md` : par question, ce que disent les sources, où elles
   convergent, où elles se contredisent (les deux valeurs, les deux extraits),
   ce qu'elles ne disent pas. Pas de transformation ni d'agrégation.
5. **Conception** (même tour que 4) — `plan.md` : une table section → extraits
   → lacunes à déclarer.
6. **Rédaction** (1 tour) — `manuscrit.md` complet, écrit une fois, dans la
   longueur cible (vise 85 % de la borne haute : les citations `[E<n>]`
   comptent comme des mots pour `wc -w`). Chaque paragraphe factuel porte ses
   citations au plus près de l'affirmation. Chiffres recopiés tels quels
   (valeur, unité, période). Lacunes dites explicitement.
7. **Révision** (1 tour de lancement + 1 tour de corrections) — D'abord
   `scripts/check_report.py` (citations inconnues, chiffres absents des
   extraits cités, paragraphes sans citation, sections, tableau, longueur,
   URL) : corrige ses bloquants. Puis **un** sous-agent relecteur à contexte
   restreint (brief + manuscrit + `parts/*.jsonl` + sortie du script, rien
   d'autre) ne traite que le sémantique : l'extrait soutient-il vraiment la
   phrase, ton, redondances, hors-sujet, lacunes non déclarées ; il remplit
   `verification.md` et renvoie une liste d'anomalies numérotée (≤ 20 lignes). Tu corriges par éditions ciblées du manuscrit (pas de réécriture complète). Si une
   information manque vraiment : **un** aller-retour vers l'étape 3 (un seul
   extracteur, plafonné), par défaut ; au-delà, arbitrage.
8. **Livraison** (1 tour) — `scripts/check_report.py` une dernière fois
   (doit dire OK), puis `scripts/build_report.py` : assemble
   `08-livraison/rapport.md` = corps + section `## Sources` générée depuis les
   extraits cités et la bibliographie ; `retex.md` ; dernière ligne du journal.

Total visé : 9 à 12 tours du responsable. Si tu dépasses 12 tours, tu livres
en l'état avec les lacunes déclarées.

## Contrat d'extrait (`03-extraits/parts/Q<n>.jsonl`, une ligne JSON par extrait)

```json
{"id": "E7", "fichier": "<nom exact du fichier du fonds ou renvoyé par vector_search>",
 "texte": "<passage VERBATIM, copié sans modification, 1 à ~10 lignes>",
 "localisation": "<section / ligne si connue>", "question": "Q2",
 "chunk_id": "<mode dataprep : chunk_id renvoyé par vector_search, sinon omis>"}
```

Règles : `texte` est une copie exacte d'un passage contigu de la source (pas
de « … », pas de correction, pas de fusion de passages, **pas de nettoyage** :
liens Markdown, crochets de notes, puces restent tels qu'ils sont dans le
fichier) ; **un extrait par idée**, pas un par occurrence ; identifiants
uniques par plage disjointe (Q1 : E1–E30, Q2 : E31–E60, …), stables jusqu'à la
livraison.

## Doctrines (universelles, quel que soit le thème)

- **N'affirmer que ce qu'on a lu.** Pas de fait, de définition ni de chiffre
  venu de mémoire. Une source qui nomme un concept sans l'expliquer n'est pas
  une preuve de l'explication.
- **Citer localement.** `[E<n>]` au niveau de la phrase ou du paragraphe
  qu'elle soutient ; une citation par affirmation suffit quand plusieurs
  extraits concordent.
- **Déclarer les lacunes.** Ce que le fonds ne couvre pas est dit tel quel,
  jamais comblé.
- **Chiffres et unités recopiés.** Toute dérivation demandée par le brief est
  montrée avec ses opérandes cités. Pas d'agrégat non demandé.
- **Contradictions** rapportées comme telles (les deux valeurs, les deux
  extraits). Si elle empêche de répondre au cœur de la demande : arbitrage.
- **Le brief fait loi** : sections, colonnes, longueur, langue, public, ton.
- **Discipline de corpus** : aucune URL ni référence externe dans le corps ;
  elles vivent dans `## Sources`.

## Arrêts et arbitrages (les seuls cas où un humain intervient)

Tu vas au bout. Tu t'arrêtes uniquement dans trois cas, en écrivant
`ARBITRAGE-REQUIS.md` (situation, options, recommandation) et en laissant les
livrables en l'état :

1. la bibliographie ne peut pas couvrir le cœur de la demande (des lacunes
   partielles ne sont PAS un motif : on livre en les déclarant) ;
2. la révision demande plus d'allers-retours vers l'étape 3 que la limite
   (1 par défaut) ;
3. le fonds se contredit sur un point central que le brief ne permet pas de
   trancher.

## Portabilité

Le skill n'attend du harnais que des capacités génériques (fichiers,
recherche textuelle, sous-agents, exécution de ses scripts Python 3 en shell,
client MCP) : voir `references/harnais.md`. Aucun SDK, aucune API de modèle ;
les scripts n'utilisent que la bibliothèque standard.

## Main courante et retex

`journal.md` : une ligne par étape avec l'heure, la décision prise, les
manques, les renvois, le budget consommé (tours, sous-agents). `retex.md` en
fin de run : processus seulement (méthode, outils, formats, pièges), aucun
contenu sur les sources. Voir `references/main-courante.md`.
