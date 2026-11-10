# Extraits FY2025 — investissements datacenter / infrastructure IA

Six fichiers, un par société, extraits textuellement des 10-K FY2025 (dossier ../text/, conversion
des HTML EDGAR). Produits le 9 novembre 2026 par six agents en parallèle, puis vérifiés
indépendamment : chaque ligne de citation existe mot pour mot dans le texte source
(251 lignes, 0 écart ; une citation Alphabet enjambe un saut de page, lignes 699 et 709).

Structure commune (huit thèmes fixes) :
- T1 Stratégie déclarée : IA et infrastructure datacenter
- T2 Capex FY2025 : montants et moteurs
- T3 Trajectoire attendue des investissements
- T4 Contraintes de capacité, d'approvisionnement et d'énergie
- T5 Amortissement et durées d'utilité des serveurs et équipements réseau
- T6 Baux, financement et engagements d'achat datacenters
- T7 Risques liés à l'investissement en infrastructure IA (Item 1A)
- T8 Non divulgué

Chaque citation est suivie d'un localisateur : Item, sous-section telle qu'imprimée, lignes du texte.

| Société | Citations | Mots | Non divulgué |
| --- | --- | --- | --- |
| Amazon | 40 | 4 264 | aucun |
| Alphabet | 38 | 3 632 | aucun |
| Meta | 39 | 3 780 | aucun |
| Microsoft | 36 (65 lignes, tableaux) | 3 203 | aucun |
| NVIDIA | 39 (50 lignes, tableaux) | 3 704 | aucun |
| Apple | 19 | 1 889 | T1 ; T3 et T7 génériques |

Total : environ 20 500 mots, 144 Ko.

Points d'attention avant tout usage comme corpus noté :
- Les extraits contiennent des chiffres de prose 10-K dont la base diffère du CSV XBRL du corpus
  ai-capex-intensity : Amazon capex cash 128,3 Md$ (CSV 131,8), NVIDIA 3,4 Md$ (CSV 3,2),
  Meta 72,22 Md$ avec principal des baux (CSV 69,7). Tout chiffre présent dans un fichier du
  corpus entre dans la liste blanche du grader : décider de les garder (doublons voulus,
  base à citer) ou de les neutraliser.
- Guidance : Meta donne 115–135 Md$ pour 2026 ; Alphabet « significantly increase » sans
  chiffre ; Amazon et NVIDIA « expect to increase » ; Microsoft « will continue to invest » ;
  Apple rien. L'answer key actuelle déclare la guidance initiale FY2025 figée au 7 février
  2025, un autre objet : ne pas confondre.
- Les tableaux Microsoft et NVIDIA sont cités cellule par cellule (une ligne par cellule).
