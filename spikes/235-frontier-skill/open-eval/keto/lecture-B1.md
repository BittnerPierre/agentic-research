# Lecture — run dev-keto-B1 (bras B, dataprep MCP, skill v1 avant leçons)

Run du 09/09/2026, Claude Fable 5.1, `claude -p`, budget 30 $ (prix liste CLI).

## Mesures

| Grandeur | Valeur |
|---|---|
| Durée murale | 1 633 s (27 min) ; API 806 s |
| Coût (prix liste CLI, cache 1 h) | 29,18 $ dont ~20 $ pour 3 sous-agents |
| Tokens | agent principal 1,06 M entrée (932 k lus en cache) + 72,6 k sortie ; sous-agents 579 k déclarés |
| Tours agent principal | 16 |
| Sous-agents | 3 extracteurs (Q1+Q2, Q3+Q6, Q4+Q5), 28 à 31 requêtes vector_search chacun ; aucun relecteur (budget) |
| Livrables | 8 étapes présentes ; manuscrit et révision fusionnés dans le rapport (budget) ; journal 12 entrées ; retex |
| Extraits | 177 (125 retenus), 98 cités, 121 citations ; 98/98 verbatim dans les morceaux indexés |
| Corps | 2 471 mots pour une fourchette 1 200–1 800 → **hors contrat** |
| Sections | 7/7, dans l'ordre ; tableau imposé présent avec les 4 colonnes exactes ; 0 URL dans le corps |
| Arbitrage humain | aucun |

## Grille

| Question du brief | Traitée ? | Fondée sur les extraits cités ? | Lacune déclarée quand il faut ? | Remarque |
|---|---|---|---|---|
| 1 Définition et mécanisme | oui | oui (cétose, 4:1, 90/6/4, variantes MCT/Atkins/IGB) | s.o. | dense, exact |
| 2 Origine et usage médical | oui | oui (1911, 1921 Wilder, 1938 phénytoïne, 1994 Charlie) ; RR Cochrane recopiés ; « ≥ 50 % » attribué à E57 qui ne porte pas le seuil | oui (adultes : preuve très faible) | divergence 11 vs 13 essais rapportée telle quelle |
| 3 Perte de poids / métabolique | oui | oui ; contradiction StatPearls vs Harvard rapportée côte à côte | oui (au-delà de 2 ans) | « 88 % d'observance » : la source l'écrit en lettres, exact |
| 4 Risques | oui | oui (calculs 1/20, lipides 60 %, contre-indications métaboliques) | oui (fréquence chez l'adulte non épileptique) | distinction court/long terme respectée |
| 5 Performance sportive | oui | oui, une seule source (Wikipédia fr), dit explicitement | oui | piège évité : « les six autres sources sont muettes » |
| 6 Coût et praticité en France | oui | oui pour l'observance et le coût hors France ; France : « le fonds ne permet pas de l'affirmer » | **oui, piège évité** | rien n'est comblé de mémoire |
| 7 Lacunes du fonds | oui | s.o. | oui, 5 lacunes + 4 contradictions non tranchables | seul paragraphe sans citation, légitime |
| Tableau imposé | oui | oui | | 4 colonnes exactes, 7 lignes |

## Chiffres (échantillon manuel, 6 + contrôle automatique sur 94)

RR 3.16 / 5.80 / 5.03 et IC : identiques aux extraits (Cochrane). 150 enfants, 3 % / 7 % : identiques. « Eighty-eight percent » (Harvard Chan) rendu « 88 % » : exact. « As of 2022 » (Wikipédia en) : exact. Aucun chiffre inventé trouvé. Un seuil (« au moins 50 % ») mal rattaché à E57.

## Verdict de lecture

Le fond répond à la demande et les pièges d'honnêteté sont évités ; la seule faute est de forme : longueur non mesurée (+37 %). Le processus a été dégradé par le budget : l'extraction (3 sous-agents, 177 extraits pour 98 utiles) a consommé 70 % du crédit, au détriment du relecteur indépendant. Le skill l'a constaté lui-même (journal, retex) et a adapté sans s'arrêter.

## Ce qui a été changé dans le skill à la suite de ce run (v2)

Plafonds par sous-agent (requêtes, extraits : 5 à 15 par question), fichiers `parts/*.jsonl` sans recopie, réserve d'un quart du budget pour les étapes 6-8, relecteur prioritaire sur un troisième extracteur, longueur mesurée avec `wc -w` avant livraison.
