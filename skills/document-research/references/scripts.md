# Scripts du package (Python 3, bibliothèque standard uniquement)

Tous s'exécutent depuis le dossier de travail : `python3 <chemin-du-skill>/scripts/<script>.py …`
(le chemin du skill est celui où le harnais l'a installé, par exemple `.claude/skills/document-research`).
Ils ne lisent que le dossier de travail et `fonds/` ; ils n'appellent aucun modèle.

| Script | Étape | Remplace | Sortie |
|---|---|---|---|
| `inventory.py [--fonds fonds] [--keywords …]` | 2 | la lecture du fonds par le responsable | lignes, mots, titres (avec numéro de ligne) et occurrences de mots-clés par fichier |
| `extract.py --find "…" [--file F] [--context N]` | 3 | la lecture exploratoire | passages candidats avec `fichier:lignes` |
| `extract.py --part 03-extraits/parts/Q<n>.jsonl --question Q<n> [--start-id N] --range fichier:a-b [--range …]` | 3 | la recopie du texte par le modèle | extraits verbatim ajoutés au fichier de la question |
| `extract.py --part … --question … --file F --text "…" [--chunk id]` | 3 (dataprep) | idem, texte renvoyé par `vector_search` | extrait ajouté |
| `verify_extracts.py [--json]` | 3 bis | le sous-agent de contrôle verbatim | verbatim / normalisés / non verbatim, ids dupliqués, textes dupliqués, extraits par question ; code 1 si à corriger |
| `check_report.py [--manuscrit …] [--sections … --min-words N --max-words N --columns …] [--json]` | 7 et 8 | la partie mécanique de la relecture et le comptage de mots | bloquants (citations inconnues, chiffres sans appui, longueur, sections, tableau, URL), paragraphes sans citation ; lit `01-cadrage/contrat.json` par défaut ; code 1 si bloquant |
| `build_report.py [--manuscrit …] [--out 08-livraison/rapport.md]` | 8 | la recopie du rapport et la rédaction de la section Sources | rapport final = corps + `## Sources` (extraits cités, bibliographie) |

## `01-cadrage/contrat.json`

```json
{"sections": ["Definition et mecanisme", "…"], "min_words": 1200, "max_words": 1800,
 "table_columns": ["Indication", "Effet rapporté", "Qualité de la preuve selon la source", "Source"],
 "language": "fr"}
```

Les intitulés de sections sont comparés en sous-chaîne, insensible à la casse
et aux espaces multiples ; les colonnes doivent être exactes.

## Ce que les scripts ne font pas

Juger si un extrait soutient réellement une affirmation, le ton, la
redondance, la pertinence : c'est le travail du relecteur (sous-agent) et du
responsable. Les scripts éliminent le mécanique pour que le modèle ne dépense
ses tokens que là où son jugement est nécessaire.
