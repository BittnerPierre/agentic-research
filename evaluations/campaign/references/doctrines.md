# Doctrines de correction et de publication

Référence détaillée du skill benchmark-campaign. À lire AVANT toute seconde
lecture, toute exception et toute publication de tableau. Le rapport
`docs/benchmark-campaign-report.md` documente chaque doctrine avec ses
exemples réels (campagne 07/2026, ~90 packs, 8 modèles).

## 1. Seconde lecture (OBLIGATOIRE avant publication)

AUCUN score n'est accepté sans lire ce qui l'a causé — y compris les A et
les échecs sémantiques (revue externe de juillet 2026, finding #3).
`compile_table.py --flags` liste pour CHAQUE run son verdict root-cause, ses
accusations numériques et ses exigences échouées ; la lettre E signale une
évaluation NON ABOUTIE (run mort, validation impossible) — et elle seule :
un échec de provenance du candidat dont l'évaluation a abouti compte par les
lettres normales (arbitrage 17/07 : déclarer honnêtement « non trouvé » = C,
pas E).

La boucle d'audit, pour chaque run non-A ET pour tout verdict inattendu d'un
run A :

1. **Lire** les items accusés (fabrications, WRONG) dans le résumé ou
   `det_grade.json`.
2. **Re-vérifier contre la vérité terrain À LA MAIN** : recalculer depuis
   `evaluations/exercises/*/corpus/key_metrics.csv` (sommes, croissances,
   ratios). Un chiffre accusé peut être exact (delta, ratio recalculé, somme).
3. **Classer** :
   - vrai défaut du candidat → on garde, on documente dans le rapport ;
   - faux positif de l'évaluateur → **SIGNALER, ne pas corriger** (voir §2).
4. **Contre-test d'équité** (si un garde a été ajouté, dans la tâche de dev
   dédiée) : vérifier que les vrais défauts des AUTRES modèles tiennent
   toujours (leurs 40 doivent rester des 40).

### Faux positif découvert : la campagne s'arrête au signalement

**La campagne ne modifie JAMAIS l'évaluateur** (contrat du skill). Quand la
seconde lecture conclut à un faux positif :

1. Terminer l'audit et documenter le cas (extrait du rapport, valeur, calcul
   de vérification) dans le compte rendu de campagne.
2. Proposer à l'utilisateur SOIT une exception `adjustments.yaml` (cas
   singulier, voir §3), SOIT une issue GitHub « nouvelle famille de faux
   positifs » (cas généralisable).
3. La correction elle-même — test ROUGE (le cas réel réduit en fixture),
   garde minimal dans l'évaluateur, `regrade.py` (suite + contrôle falsifié
   + re-notation), contre-test d'équité — est une TÂCHE DE DÉVELOPPEMENT
   SÉPARÉE : issue, branche dédiée, go explicite. Jamais pendant la campagne.

### Familles de faux positifs déjà rencontrées

Ne pas re-découvrir — le détail et les extraits sont dans
`evaluations/campaign/false-positive-catalog.md` : deltas loin des opérandes,
ratios recalculés, signe moins binaire, conventions d'arrondi, méta-discours
sur les sources, tableaux guidance, dates, synthèses multi-sociétés,
localisateurs de citation, échelles d'unité, seuils hedgés, fourchettes,
vocabulaire guidance français.

### Pièges connus du filet anti-blanchiment

Ils ont déjà mordu : élargir une excuse avec des tolérances larges ou des
paires multi-sociétés blanchit des chiffres inventés — le contrôle falsifié
DOIT rester à 3/3 après chaque changement d'évaluateur, c'est non négociable
(et c'est une raison de plus pour que ces changements vivent hors campagne).

## 2. Exceptions post-examen

Quand une réponse est VRAIE mais qu'aucune règle générale saine n'existerait
pour l'excuser (ex. somme multi-sociétés exacte) : on NE MODIFIE PAS
l'évaluateur. On PROPOSE à l'utilisateur une entrée dans
`evaluations/adjustments.yaml` (score ajusté, motif, vérification manuelle,
arbitre, date) — **l'écriture du fichier n'a lieu qu'après son go** (fichier
suivi par git). L'évaluateur referait la même erreur : c'est assumé. Les
copies non contestées ne sont pas revues. `compile_table.py` applique les
ajustements automatiquement (marqués `*`).

## 3. Doctrines de comptage

- **Casser sa chaîne de preuve = faute du candidat** (URL corrompue → 0.0
  compté ; doc_ids absents → items perdus). À reporter, pas à réparer.
- **Zèle** : un calcul hors consigne EXACT est excusé mécaniquement (les
  dérivations couvrent) ; un calcul hors consigne FAUX est flaggé. Rien à
  faire de spécial.
- Un run `evaluation_failed` pour panne de VALIDATION DE PREUVES est compté ;
  un `evaluation_failed` pour panne de protocole du juge se re-corrige
  (relancer la correction du pack suffit en général).

## 4. Présentation des résultats

Présentation officielle (arbitrage utilisateur) : **séquence de lettres de
confiance + couverture médiane**, jamais un score unique. Sémantique :
A propre · C ≥1 chiffre faux (à relire) · D une invention (récupérable en
relecture attentive) · F inventions multiples (rapport mort) · E évaluation
non aboutie. Les lettres ne s'agrègent pas : on montre la séquence (la
variance à l'œil nu). Podium trié F > D > C > couverture. Le score 0-100
reste disponible en annexe.

## 5. Résultats de référence (calibration)

Ordres de grandeur attendus si tout va bien (campagne 07/2026) :
gpt-5.6-sol A×5 / cov 100 % (finance) et 87.5 % (concept) ; gpt-5.4-mini
A×5 / 85.7 et 68.8. Si une référence sort avec des lettres D/F, suspecter
d'abord une NOUVELLE famille de faux positifs (le modèle le plus fort frappe
le plus fort les angles morts de l'évaluateur), pas le modèle.
