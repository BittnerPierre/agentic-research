# Sous-agents : contrats bornés

Les sous-agents servent à **retirer le corpus du contexte du responsable**,
pas à multiplier le travail. Chaque sous-agent reçoit une mission fermée, un
contexte minimal et le budget que le responsable lui alloue ; il renvoie un
compte rendu court. Il ne délègue jamais à son tour. Le découpage (par
question, par source, mixte) et le nombre de sous-agents sont des choix du
responsable, pris au cadrage en fonction du brief et du budget.

## Délégation synchrone

Le responsable lance ses sous-agents **dans un même tour, en mode bloquant**
(tous les extracteurs en parallèle, puis il attend leurs retours dans ce
tour). Jamais en arrière-plan, jamais avec un outil d'attente, de
planification ou de messagerie : en exécution autonome, le harnais met fin au
run quand le responsable termine son tour, et les sous-agents encore actifs
sont coupés.

## Extracteur (étape 3) — un par question (ou paire de questions proches)

Consigne type (à adapter, garder court) :

```
Mission : extraire les passages du fonds qui répondent à Q<n> : « <question> ».
Fonds : <mode fichiers : liste des fichiers pressentis dans fonds/, lecture et recherche textuelle>
        <mode dataprep : collection « <nom> », outil vector_search, ≤ 6 requêtes,
         top_k ≤ 8, varier les formulations, filtrer par filenames si besoin>
Budget : <ce que le responsable alloue : extraits attendus (un par idée), requêtes ou lectures>.
Hors périmètre (traité par d'autres) : Q<m> « … », Q<p> « … » — n'extrais rien pour eux.
Contrat : une ligne JSON par extrait dans 03-extraits/parts/Q<n>.jsonl, ids E<a>–E<b>,
 {"id","fichier","texte" (VERBATIM, sans nettoyage),"localisation","question","chunk_id" (dataprep)}.
Méthode : écris 03-extraits/parts/Q<n>.spec.json (part, question, start_id, items = plages
 « fichier:a-b » ou {file, chunk_id, text}) avec l'outil d'écriture de fichier, puis UNE commande :
 python3 <skill>/scripts/extract.py --spec 03-extraits/parts/Q<n>.spec.json
 Commande shell simple : depuis le dossier de travail, sans cd, sans pipe, sans texte long en argument.
Interdits : mémoire personnelle, web, autres fichiers que le fonds, sous-agents.
Réponse attendue (courte) : nombre d'extraits, fichiers mobilisés, ce que le fonds
 ne dit PAS sur Q<n> (avec les requêtes ou recherches faites), doublons évités.
```

Repères mesurés (pas des règles) : une question simple se couvre en général
avec une dizaine d'extraits et quelques requêtes ; ce qui a coûté cher dans
les essais, ce sont les requêtes redondantes à large `top_k` et les extraits
« par occurrence ». Un extracteur qui n'a rien trouvé après ses requêtes le
dit : c'est une lacune, pas un échec.

## Relecteur (étape 7) — un seul

Contexte : `brief.md`, `06-redaction/manuscrit.md`, `03-extraits/parts/*.jsonl`.
Rien d'autre (pas le fonds : il vérifie le manuscrit contre les extraits, pas
contre les sources).

```
Mission : vérifier le manuscrit contre le brief et les extraits.
1. Chaque citation [E<n>] existe et l'extrait soutient réellement la phrase.
2. Chaque chiffre du manuscrit est identique (valeur, unité, période) à un extrait cité dans la phrase.
3. Affirmations factuelles sans citation.
4. Conformité au brief : sections et intitulés, ordre, tableau et colonnes, langue, ton, longueur
   (mesurer : wc -w sur le corps hors ## Sources, ou tokens \S+ si pas de shell).
5. Redondances, hors-sujet, lacunes non déclarées.
Écris 07-revision/verification.md (grille) et réponds par une liste numérotée
 d'anomalies : bloquantes d'abord, avec la correction proposée.
Interdits : réécrire le manuscrit, lire le fonds, mémoire, web, sous-agents.
```

## Discipline shell (tous les sous-agents)

Le harnais n'autorise que les scripts du package (`python3 <skill>/scripts/…`)
et quelques commandes de base. Une commande composée (`cd … && …`, `|`,
`;`), un texte long ou des guillemets imbriqués en argument sont refusés :
passer par un fichier de spécification et une commande simple. Ne pas
réessayer une commande refusée sous une autre forme : lire le message, écrire
le fichier, relancer une fois.

## Ce que le responsable ne délègue pas

Cadrage, bibliographie (depuis le catalogue), synthèse (depuis les parts),
plan, rédaction, corrections, livraison, journal, retex.

## Modèle des sous-agents

Par défaut, même modèle que le responsable (comparabilité). Si la consigne de
lancement autorise un modèle plus économique pour les extracteurs, l'utiliser
pour l'extraction uniquement ; le relecteur garde le modèle principal.
