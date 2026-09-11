# Sous-agents : contrats bornés

Les sous-agents servent à **retirer le corpus du contexte du responsable**,
pas à multiplier le travail. Chaque sous-agent reçoit une mission fermée, un
contexte minimal et des plafonds explicites ; il renvoie un compte rendu
court. Il ne délègue jamais à son tour.

## Extracteur (étape 3) — un par question (ou paire de questions proches)

Consigne type (à adapter, garder court) :

```
Mission : extraire les passages du fonds qui répondent à Q<n> : « <question> ».
Fonds : <mode fichiers : liste des fichiers pressentis dans fonds/, lecture et recherche textuelle>
        <mode dataprep : collection « <nom> », outil vector_search, ≤ 6 requêtes,
         top_k ≤ 8, varier les formulations, filtrer par filenames si besoin>
Plafonds : ≤ <8 à 12> extraits, un par idée ; ≤ <6> requêtes ou lectures.
Hors périmètre (traité par d'autres) : Q<m> « … », Q<p> « … » — n'extrais rien pour eux.
Contrat : une ligne JSON par extrait dans 03-extraits/parts/Q<n>.jsonl, ids E<a>–E<b>,
 {"id","fichier","texte" (VERBATIM, sans nettoyage),"localisation","question","chunk_id" (dataprep)}.
Interdits : mémoire personnelle, web, autres fichiers que le fonds, sous-agents.
Réponse attendue (≤ 10 lignes) : nombre d'extraits, fichiers mobilisés, ce que le fonds
 ne dit PAS sur Q<n> (avec les requêtes ou recherches faites), doublons évités.
```

Ordre de grandeur des plafonds : 8 à 12 extraits par question simple, 15 pour
une question composite ; 6 lectures ou requêtes. Un extracteur qui n'a rien
trouvé après ses requêtes le dit : c'est une lacune, pas un échec.

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
Écris 07-revision/verification.md (grille, ≤ 60 lignes) et réponds par une liste numérotée
 d'anomalies (≤ 20 lignes) : bloquantes d'abord, avec la correction proposée.
Interdits : réécrire le manuscrit, lire le fonds, mémoire, web, sous-agents.
```

## Ce que le responsable ne délègue pas

Cadrage, bibliographie (depuis le catalogue), synthèse (depuis les parts),
plan, rédaction, corrections, livraison, journal, retex.

## Modèle des sous-agents

Par défaut, même modèle que le responsable (comparabilité). Si la consigne de
lancement autorise un modèle plus économique pour les extracteurs, l'utiliser
pour l'extraction uniquement ; le relecteur garde le modèle principal.
