---
name: document-research
description: >-
  Produit un rapport consolidé de connaissances sur un thème à partir d'un
  fonds documentaire FERMÉ (fichiers locaux ou base de connaissances dataprep
  via MCP), en suivant les 8 étapes du processus de recherche documentaire
  (cadrage, collecte, sélection et extraction, analyse, conception, rédaction,
  révision, livraison) avec un livrable lisible par étape, une main courante et
  des citations verbatim traçables. Utiliser ce skill quand on demande une
  synthèse documentaire, un dossier de fond, un brief, un état de l'art ou un
  rapport de recherche sourcé sur un corpus donné (audit flash, dossier pour un
  script vidéo, note de synthèse, data pack). NE PAS l'utiliser pour une
  question ponctuelle, une recherche web ouverte ou un texte sans sources.
---

# Recherche documentaire en 8 étapes

Tu conduis une recherche documentaire complète, de la demande au document
final, **sans intervention humaine** sauf arbitrage (voir « Arrêts »). Le
processus est celui d'un documentaliste : chaque étape laisse un livrable
lisible dans le dossier de travail, pour qu'un humain puisse comprendre où un
problème est survenu et reprendre. Pas de boîte noire.

Le fonds documentaire est **fermé** : seules les sources du fonds (ou celles que
le brief demande explicitement d'acquérir) alimentent le rapport. Aucune
connaissance personnelle, aucune recherche web autonome.

## Entrées

- `brief.md` : la demande du commanditaire (question, périmètre, format,
  longueur, langue, public, style, sources imposées). Tout ce qui manque dans
  le brief est fixé au cadrage avec une valeur par défaut explicite.
- Le fonds, selon le mode annoncé dans la consigne de lancement :
  - **Mode fichiers** : un dossier `fonds/` (documents + éventuel
    `catalogue.md` qui relie chaque référence du brief à son fichier). Outils :
    Read, Grep, Glob.
  - **Mode dataprep (MCP)** : la base de connaissances du serveur dataprep.
    Outils : `download_and_store_url_tool` (acquisition), 
    `upload_files_to_vectorstore_tool` (indexation dans une collection nommée),
    `get_knowledge_entries_tool` (catalogue), `vector_search` (recherche
    sémantique, renvoie des extraits identifiés). Voir
    `references/outils-retrieval.md`.
- Optionnel : `process-notes.md`, enseignements de processus des runs
  précédents (méthode, pièges, outils). Jamais du contenu sur les sources.

## Dossier de travail (un livrable par étape)

```
01-cadrage/cadrage.md            question, périmètre, critères, attentes, plan de recherche
02-collecte/bibliographie.md     bibliographie de travail : chaque document, son statut, sa couverture
03-extraits/parts/*.jsonl        extraits VERBATIM avec provenance, un fichier par extracteur (contrat ci-dessous)
03-extraits/extraits.jsonl       index facultatif des extraits (jamais une recopie des textes)
03-extraits/corpus-retenu.md     documents retenus / écartés, et pourquoi
04-analyse/fiches.md             notes de lecture référencées, dédoublonnées, sans transformation
04-analyse/synthese.md           confrontation des sources, convergences, contradictions, lacunes
05-conception/plan.md            plan rédactionnel : sections, extraits mobilisés par section
06-redaction/manuscrit.md        premier texte complet
07-revision/verification.md      vérification citation par citation, faits, chiffres, style, conformité au brief
07-revision/revision-1.md        texte révisé (et revision-2.md si un second tour est autorisé)
08-livraison/rapport.md          document final
journal.md                       main courante (voir références/main-courante.md)
retex.md                         relecture de processus en fin de run
ARBITRAGE-REQUIS.md              seulement si un arbitrage humain est nécessaire (voir « Arrêts »)
```

Écris chaque livrable **avant** de passer à l'étape suivante, et note dans
`journal.md` l'entrée de l'étape (décision, manque, renvoi).

## Les 8 étapes

Détail, critères de sortie et gabarits : `references/processus.md`.

1. **Cadrage** — Reformule la question de recherche, découpe-la en questions
   secondaires, fixe les critères de sélection des sources et les attentes du
   livrable (format, longueur, langue, public, style, sections imposées).
   Liste les références initiales données par le brief. Décide la politique
   de corpus : fermé strict par défaut ; acquisition uniquement des documents
   que le brief nomme.
2. **Recherche et collecte** — Constitue la bibliographie de travail : pour
   chaque document du fonds, titre, identifiant de fichier, ce qu'il couvre,
   ce qu'il ne couvre pas par rapport aux questions du cadrage. En mode
   dataprep : acquisition des références du brief, indexation dans une
   collection dédiée au run, catalogue, puis recherches par question
   secondaire. Si la bibliographie ne peut pas couvrir la demande de manière
   consistante : arbitrage (voir « Arrêts »).
3. **Sélection et extraction** — Retiens les sources pertinentes et extrais
   les passages utiles **verbatim**, chacun avec sa provenance. C'est ici que
   se construit la preuve : tout ce qui sera affirmé dans le rapport doit
   avoir son extrait. Délègue volontiers l'extraction à des sous-agents à
   contexte frais (un par document ou par question) en leur donnant le contrat
   d'extrait et la liste des questions ; toi, tu consolides `extraits.jsonl`.
4. **Analyse, annotation et synthèse** — Transforme les extraits en notes de
   lecture : texte au plus près de la source, mis au propre, dédoublonné,
   chaque note référencée `[E<n>]`. **Pas de transformation ni d'agrégation**
   à cette étape (pas de somme, pas de moyenne, pas de reformulation qui
   ajoute une idée). Puis la synthèse : ce que les sources disent, où elles
   convergent, où elles se contredisent, ce qu'elles ne disent pas.
5. **Conception** — Plan rédactionnel conforme aux sections imposées par le
   brief, avec pour chaque section les extraits mobilisés et les lacunes à
   déclarer.
6. **Rédaction** — Manuscrit complet. Chaque paragraphe factuel porte ses
   citations `[E<n>]` au plus près de l'affirmation. Les chiffres sont recopiés
   tels qu'ils figurent dans l'extrait (même unité, même arrondi) ; une
   dérivation demandée par le brief (différence, ratio) est montrée avec ses
   opérandes cités. Ce que le fonds ne couvre pas est dit explicitement, dans
   la section prévue par le brief ou dans une section « Lacunes ».
7. **Révision et relecture** — Vérification systématique, de préférence par un
   sous-agent relecteur indépendant qui ne voit que le manuscrit et
   `extraits.jsonl` : chaque citation renvoie-t-elle à un extrait qui soutient
   réellement la phrase ? chaque chiffre est-il identique à sa source ? les
   sections, la longueur, la langue, le ton respectent-ils le brief ? y a-t-il
   des affirmations sans extrait, des redondances, du hors-sujet ? Corrige.
   Si la révision révèle qu'il manque des extraits, **un** aller-retour vers
   les étapes 2-3 est autorisé par défaut (paramétrable dans le brief) ;
   au-delà, arbitrage.
8. **Livraison** — `08-livraison/rapport.md` : le texte révisé, mis en forme,
   terminé par une section `## Sources` qui liste chaque extrait cité
   (`[E<n>]`, document, localisation) et la bibliographie. Écris `retex.md`.

**Longueur : ne l'estime jamais, mesure-la.** Avant la livraison, compte les
mots du corps (hors section `## Sources`) avec `wc -w` (seul usage du shell
prévu par ce skill ; si le shell est indisponible, écris le corps dans un
fichier séparé et compte-le par un sous-agent). Hors fourchette du brief :
coupe ou complète, puis recompte. Une longueur hors contrat est une faute de
forme au même titre qu'une section manquante.

## Contrat d'extrait (`03-extraits/extraits.jsonl` ou `03-extraits/parts/*.jsonl`, une ligne JSON par extrait)

```json
{"id": "E7", "fichier": "<nom exact du fichier dans le fonds ou renvoyé par vector_search>",
 "texte": "<passage VERBATIM, copié sans modification, 1 à ~12 lignes>",
 "localisation": "<section / ligne / page si connue>",
 "question": "<question secondaire du cadrage servie>",
 "chunk_id": "<mode dataprep : chunk_id renvoyé par vector_search, sinon omis>"}
```

Règles : `texte` est une copie exacte d'un passage contigu de la source (pas
de « … », pas de correction, pas de fusion de deux passages) ; un extrait par
idée ; les identifiants `E1, E2, …` sont uniques et stables jusqu'à la
livraison ; les extraits non retenus restent dans le fichier avec
`"retenu": false` plutôt que d'être supprimés.

## Doctrines (universelles, quel que soit le thème)

- **N'affirmer que ce qu'on a lu.** Pas de fait, de définition ni de chiffre
  venu de mémoire. Une source qui ne fait que nommer un concept sans
  l'expliquer n'est pas une preuve de l'explication.
- **Citer localement.** La citation `[E<n>]` est au niveau de la phrase ou du
  paragraphe qu'elle soutient, pas en fin de section.
- **Déclarer les lacunes.** Ce que le fonds ne couvre pas est dit tel quel
  (« le fonds ne documente pas … »), jamais comblé. Une lacune déclarée vaut
  mieux qu'une réponse plausible.
- **Chiffres et unités recopiés.** Un chiffre a une unité, une période et une
  source. Toute dérivation est montrée. Pas d'agrégat que le brief n'a pas
  demandé.
- **Contradictions.** Deux sources qui se contredisent sont rapportées comme
  telles (les deux valeurs, les deux extraits). Si la contradiction empêche de
  répondre à la demande : arbitrage.
- **Respecter le brief à la lettre** : sections, colonnes de tableau,
  longueur, langue, public, ton. Le brief prime sur les habitudes.
- **Discipline de corpus.** Aucune URL ni référence externe dans le corps du
  rapport ; les URL n'apparaissent que dans la section `## Sources`.

## Arrêts et arbitrages (les seuls cas où un humain intervient)

Tu vas au bout. Tu t'arrêtes uniquement dans trois cas, en écrivant
`ARBITRAGE-REQUIS.md` (situation, options, ce que tu recommandes) et en
laissant les livrables produits en l'état :

1. la bibliographie de travail ne peut pas couvrir la demande de manière
   consistante (le fonds est hors sujet ou trop lacunaire pour le cœur de la
   question ; des lacunes partielles ne sont PAS un motif d'arrêt : on livre en
   les déclarant) ;
2. la révision demande plus d'allers-retours vers 2-3 que la limite autorisée
   (1 par défaut) ;
3. le fonds contient des informations contradictoires sur un point central
   que le brief ne permet pas de trancher.

## Sous-agents

Utilise l'outil Agent pour les tâches qui saturent le contexte ou gagnent à
être indépendantes : extraction par document ou par question (étape 3),
relecture (étape 7). Donne à chaque sous-agent : sa mission, le contrat
d'extrait ou la grille de vérification, les chemins exacts, la liste des
questions confiées aux AUTRES sous-agents (pour qu'il n'extraie pas hors de
son périmètre), et l'interdiction d'utiliser sa mémoire ou le web.

Règles d'économie (les sous-agents sont le premier poste de dépense) :

- **Plafonne chaque sous-agent** : nombre de requêtes ou de lectures, nombre
  d'extraits (ordre de grandeur : 5 à 15 extraits par question secondaire ;
  un extrait par idée, pas un par occurrence). Au-delà, il sélectionne.
- **Pas de recopie** : chaque sous-agent écrit ses extraits dans son propre
  fichier `03-extraits/parts/<nom>.jsonl` avec une plage d'identifiants
  disjointe (E1–E60, E61–E120, …). L'ensemble des fichiers `parts/*.jsonl`
  fait foi ; `extraits.jsonl` n'est qu'un index facultatif (une ligne par
  extrait : id, fichier, question, `retenu`), jamais une recopie des textes.
- **Réserve un quart du budget** (tours, temps ou coût) aux étapes 6-8 dès le
  cadrage ; si l'extraction menace de le consommer, tu arrêtes l'extraction et
  tu livres avec les lacunes déclarées.
- Un relecteur indépendant (étape 7) vaut plus qu'un troisième extracteur : en
  cas d'arbitrage budgétaire, garde le relecteur.

Tu restes seul responsable de la consolidation et des livrables.

## Budget et main courante

Tiens `journal.md` à jour à chaque étape (voir
`references/main-courante.md`). Note les tours et le temps consommés par
étape quand tu peux les estimer. Si le brief fixe un budget (tours, temps,
coût), le cadrage le répartit par étape et la rédaction commence quoi qu'il
arrive avec ce qui a été collecté, lacunes déclarées.

En fin de run, `retex.md` : ce qui a bien et mal marché dans le **processus**
(méthode, outils, formats), à transmettre au run suivant. Aucun contenu sur les
sources n'y figure.
