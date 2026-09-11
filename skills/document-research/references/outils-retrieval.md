# Outils de retrieval selon le mode

## Mode fichiers (fonds local)

Le fonds est le dossier `fonds/`. `fonds/catalogue.md` (s'il existe) relie
chaque référence du brief (URL, titre) à son fichier local : c'est la table de
correspondance à utiliser pour la bibliographie ; ne pas tenter d'accéder aux
URL.

- Inventaire : listage des fichiers de `fonds/`.
- Lecture : outil de lecture de fichier (lecture intégrale des documents courts ; les fichiers
  tabulaires — CSV, tableaux Markdown — se lisent en entier, jamais par
  recherche de mots-clés seule).
- Recherche ciblée : recherche textuelle (mots-clés, chiffres, noms) pour localiser les
  passages avant de les lire dans leur contexte.
- Extraits : copier le passage tel qu'il est dans le fichier. `fichier` =
  chemin relatif au fonds (ex. `Agents_1.md`, `key_metrics.csv`).

## Mode dataprep (serveur MCP)

La ressource « Référencement et organisation » est le serveur dataprep. Outils :

| Outil | Rôle | Usage dans le processus |
|---|---|---|
| `download_and_store_url_tool(url)` | Acquisition : télécharge, convertit en Markdown, range dans la base de connaissances ; renvoie le nom de fichier local. Idempotent (une URL déjà connue renvoie son fichier). | Étape 2 : uniquement pour les références nommées par le brief. |
| `upload_files_to_vectorstore_tool(inputs, vectorstore_name)` | Indexation des fichiers (noms renvoyés par l'acquisition, ou URL) dans une collection nommée. | Étape 2 : une collection par run, nommée d'après la consigne de lancement (ou `dr-<theme>-<horodatage>`). |
| `get_knowledge_entries_tool()` | Catalogue : entrées de la base (url, filename, title, keywords, summary). | Étape 2 : bibliographie de travail (utiliser `filename` exact pour filtrer les recherches). |
| `vector_search(query, vectorstore_name, top_k, filenames)` | Recherche sémantique dans la collection ; renvoie des extraits avec `chunk_id`, `filename`, `text` (texte exact du morceau indexé). | Étapes 2-3 : une ou plusieurs requêtes par question secondaire ; varier les formulations ; filtrer par `filenames` pour interroger un document précis. |

Règles :

- Le `texte` d'un extrait en mode dataprep est le `text` renvoyé par
  `vector_search` (ou un passage contigu à l'intérieur), et `chunk_id` est
  recopié dans l'extrait : c'est la provenance.
- Un résultat de recherche est un candidat, pas une preuve : lire le texte
  renvoyé et ne garder que ce qui répond vraiment à la question.
- Pour les données tabulaires ou les listes exhaustives (toutes les lignes
  d'un tableau, toutes les entités d'une liste), la recherche sémantique
  fragmente : multiplier les requêtes ciblées (une par entité, par métrique)
  et vérifier l'exhaustivité contre le brief.
- Une entité ou une valeur « introuvable » n'est déclarée non disponible
  qu'après plusieurs requêtes formulées différemment et un filtrage par
  document.
- Les fichiers de la base ne sont pas lus directement sur le disque : le seul
  accès au fonds est l'outil de recherche (c'est ce qui rend le mode
  représentatif d'une base à grande échelle).
