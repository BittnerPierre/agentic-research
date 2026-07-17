# Catalogue des familles de faux positifs (campagne 07/2026)

Chaque famille a son test de non-régression dans `tests/test_deterministic_grade.py`
(écrit rouge d'abord) et son garde dans `evaluations/deterministic_grade.py`.
À consulter pendant la seconde lecture : si un item accusé ressemble à une de
ces formes, vérifier que le garde existant couvre bien le cas AVANT d'en
créer un nouveau. Révélées par : le modèle qui écrivait cette forme-là.

| Famille | Extrait réel | Garde | Révélée par |
|---|---|---|---|
| Deltas de synthèse loin des opérandes | « Amazon (+91,7 Md$), devant Alphabet (+69,1)… » | dérivation vérifiée contre les valeurs corpus de la société nommée, quasi-exact (0.15 abs / 0.2 % rel) | gpt-5.6-sol |
| Ratios recalculés sans société dans le paragraphe | « les Capex/OCF recalculés sont respectivement de 94,5 %… » | recomputation précise d'un fait ratio DÉJÀ publié (±0.55 du fait stocké ET quotient exact des montants) | gpt-5.6-sol |
| Convention de précision | « montants arrondis/présentés à 0,1 Md$ » | valeurs ≤1 + vocabulaire d'arrondi | gpt-5.6-sol |
| Méta-discours sur les sources | « [S7] marks all Apple metrics as unavailable, while… retained » ; « one corpus extraction states… » | attribution à une source ([Sx] + verbe de rapport) = méta ; clause qui MONTRE la valeur = note d'incohérence | gpt-5.6-sol |
| Tableau guidance | « Alphabet, Environ 75, 4 fév. 2025 » accusé contre l'actual 91,4 | en-tête guidance → aucune autorité d'accusation | gpt-5.6-sol |
| Signe moins binaire | « 131,8 − 40,1 » lu −40,1 ; « $139.5B − $131.8B » | moins précédé d'un chiffre OU d'une lettre d'unité = opérateur | gpt-5.6-sol, MiniMax |
| Dates | « 30 juin 2025 » → 30 flaggé | nombre suivi d'un nom de mois = date | gpt-4.1 |
| Synthèses multi-sociétés | « disponibles pour Alphabet, Meta, Microsoft…, manquantes pour Amazon » → 36 faux WRONG | clause nommant >2 sociétés = prose de synthèse, territoire du juge | gpt-4.1 |
| Négation/complétude | « sans valeur manquante ni donnée non reportée » | couvert par la règle multi-sociétés + valeur montrée | gpt-4.1 |
| Échelle d'unité | « milliards de dollars (M$) » puis « 131,8 M$ » lu 0.1318 Md | numéral ×1000 quasi exact (tol 0) dans la whitelist | Qwen3.6 |
| Vocabulaire guidance FR | « guides initiaux de Capex » | « guide » ajouté au vocabulaire guidance | Qwen3.6 |
| Seuils hedgés | « exceeding 50% », « capex 20-50% of OCF », « inférieurs à 15 % » | hedge words EN/FR + multiples de 5 | MiniMax, Mistral |
| Localisateurs de citation | « [S1:22,25] » lu 22,25 ; « [S1:9,30,53] » lu 93053 | spans [S…] masqués avant extraction | Mistral |
| Énumérations de croissances | « hausses respectives de 86,9 % et 74,1 % » (exactes) | fallback corpus essaie TOUTES les sociétés nommées du paragraphe, atteignable depuis toutes les sorties de _derivation_status | Mistral |
| Fourchettes / franchissements | « fourchette 130–400 Md$ », « franchir 50 % » | hedge words fourchette/franchir/crossed/band | gpt-5.1 |
| Étiquetage de période d'un % | « 86,9 % en FY2025 par rapport à FY2020 » (chiffre vrai, période fausse) | un POURCENTAGE suivi d'années = étiquette de croissance (erreur d'analyse → juge) ; un MONTANT daté reste exclu | Mistral |
| Constantes techniques en conceptuel | « 384 ou 768 dimensions », « 200-500 tokens », « S&P 500 » | porte numérique réservée au mode numeric (le juge evidence-bound couvre le conceptuel) | Mistral |

## Élargissements RETOQUÉS par le filet anti-blanchiment (ne pas retenter)

- Tolérances larges sur dérivations d'opérandes non montrés : un 73 % inventé
  excusé (Amazon OCF +73,25 %) ; un 4.2x excusé par un 4202 sans rapport.
- Paires multi-sociétés sans ancre : 4/6 taux inventés trouvaient un ratio
  fortuit ; sommes de sous-ensembles = ~2600 candidats.
- Ratio de deux métriques déjà en % : 62,0/84,9 = 73,03 ; marges 37,3/27,2 =
  137,13 (a failli blanchir le contrôle falsifié).
- Direction /1000 de l'échelle d'unité avec tolérance absolue : 0.022 ≈
  n'importe quelle petite valeur.

Le contrôle falsifié (`evaluations/controls/fabricated_report.md`, hôte
épinglé dans `evaluations/controls/host_run/`) attrape 3 chiffres plantés :
88.7 (« revenu data-center »), 137 (« hausse »), 210.5 (« carnet de
commandes » — longtemps passé au travers, attrapé depuis les gardes du
16/07 ; le verdict dépend de l'hôte, d'où l'épinglage). Après TOUT
changement de l'évaluateur : exactement 3, ni plus (sur-accusation) ni
moins (blanchiment).
