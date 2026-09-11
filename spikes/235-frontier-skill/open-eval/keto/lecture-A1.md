# Lecture — run dev-keto-A1 (bras A, fichiers, skill v1 avant leçons)

Run du 09/09/2026, Claude Fable 5.1, `claude -p`, budget 30 $ (prix liste CLI), en parallèle de B1.

## Mesures

| Grandeur | Valeur |
|---|---|
| Durée murale | 3 032 s (50 min) ; API 3 028 s |
| Coût (prix liste CLI, cache 1 h) | 24,66 $ dont ~6 $ de sous-agents |
| Tokens | agent principal 6,56 M entrée (6,17 M lus en cache) + 223 k sortie ; sous-agents 682 k déclarés |
| Tours agent principal | 87 |
| Sous-agents | 11 : 1 contrôleur verbatim (qui a lui-même lancé 7 sous-agents Explore, un par document), 1 relecteur indépendant à contexte restreint, 2 autres |
| Livrables | 8 étapes présentes ; extraction directe par le responsable (fonds lu en entier) ; révision-1 après relecteur ; journal 14 entrées ; retex |
| Extraits | 179, 70 cités, 93 citations ; 66/70 verbatim strict, 4 avec liens Markdown réduits au texte (relocalisés par l'adaptateur vers le span brut) |
| Corps | 1 757 mots (fourchette 1 200–1 800) → **conforme**, après un manuscrit initial à ~2 990 et trois passes de coupe |
| Sections | 7/7, dans l'ordre, numérotées ; tableau imposé présent avec les 4 colonnes ; 0 URL dans le corps |
| Aller-retour 7 → 3 | 1/1 consommé (extrait E179 ajouté pour sourcer une affirmation) |
| Arbitrage humain | aucun |

## Grille

| Question du brief | Traitée ? | Fondée sur les extraits cités ? | Lacune déclarée quand il faut ? | Remarque |
|---|---|---|---|---|
| 1 Définition et mécanisme | oui | oui | s.o. | divergence des « macronutriments typiques » rapportée |
| 2 Origine et usage médical | oui | oui ; RR Cochrane recopiés | oui | divergence 1920/1921 rapportée telle quelle |
| 3 Perte de poids / métabolique | oui | oui ; contradiction StatPearls vs Harvard rapportée | oui (au-delà de 1-2 ans) | |
| 4 Risques | oui | oui | oui | |
| 5 Performance sportive | oui | oui, source unique nommée | oui (« ni effectifs, ni durée, ni qualité ») | piège évité |
| 6 Coût et praticité en France | oui | oui | **oui, piège évité** : « le fonds ne permet rien d'affirmer de spécifique à la France » | aucun montant inventé |
| 7 Lacunes du fonds | oui | s.o. | oui, 8 lacunes dont le bandeau de fiabilité de Wikipédia fr | initiative pertinente |
| Tableau imposé | oui | oui | | 4 colonnes exactes |

## Chiffres

Contrôle automatique : 67 chiffres dans des phrases citées, 1 groupe signalé (ligne de tableau multi-citations, artefact du découpage), 0 chiffre absent des sources à la lecture manuelle (RR 3.16 / 5.80 / 5.03, 70 / 65 / 64 / 38 %, 23 % / 8.4 %).

## Verdict de lecture

Fond et forme conformes au brief ; pièges d'honnêteté évités ; le relecteur indépendant a fait son travail (a détecté le dépassement de longueur et une affirmation non sourcée). Le prix : 50 minutes, 87 tours, 6,5 M de tokens d'entrée pour le seul agent principal, parce que le fonds entier a été lu en contexte puis relu à chaque tour, et que le comptage de mots sans shell a coûté des dizaines de tours. Deux écarts au contrat d'extrait : liens Markdown retirés dans 4 extraits (règle durcie en v2) ; un sous-agent contrôleur qui sous-délègue (7 sous-sous-agents).

## Comparaison A1 / B1 (même brief, même modèle, même skill v1)

| | A1 (fichiers) | B1 (dataprep MCP) |
|---|---|---|
| Durée | 50 min | 27 min |
| Coût CLI | 24,7 $ | 29,2 $ |
| Tours / sous-agents | 87 / 11 | 16 / 3 |
| Longueur | 1 757 (conforme) | 2 471 (hors contrat) |
| Relecteur indépendant | oui | non (budget) |
| Extraits cités / verbatim | 70 / 66 strict + 4 relocalisés | 98 / 98 |
| Pièges (France, sport) | évités | évités |
| Contradictions rapportées | 3 | 4 |

Deux runs, deux stratégies choisies par le modèle lui-même (lecture intégrale + relecture vs extraction déléguée), deux profils de coût, un même fond honnête ; la dispersion est dans le processus et la forme, pas dans les faits.
