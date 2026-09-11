# Le processus en 8 étapes — définitions, critères de sortie, gabarits

Transcription du processus de production d'un rapport de recherche
documentaire (schéma de référence du projet). Une ressource transverse,
« Référencement et organisation », porte le fonds : catalogue, index, base de
connaissances, et la **demande d'acquisition** des ressources manquantes. En
mode dataprep, cette ressource est le serveur MCP ; en mode fichiers, c'est le
dossier `fonds/` et son `catalogue.md`.

| Étape | Livrable | Définition | Critère de sortie |
|---|---|---|---|
| 1. Cadrage | `01-cadrage/cadrage.md` | Ce que le travail cherche à établir, comprendre, démontrer ou raconter. Thèmes, questions, types de sources, méthode, périmètre. Attentes du destinataire. | Questions secondaires numérotées ; attentes de forme toutes renseignées ; politique de corpus écrite ; plan de recherche (quelle question, quelles sources, quelle méthode). |
| 2. Recherche et collecte | `02-collecte/bibliographie.md` | Identification et collecte des documents susceptibles d'alimenter le travail. Bibliographie de travail et corpus initial. | Chaque document du fonds a une notice (identifiant, titre, nature, couverture attendue par question). Les documents manquants ou inaccessibles sont listés. Décision : couverture suffisante ou arbitrage. |
| 3. Sélection et extraction | `03-extraits/parts/Q<n>.jsonl` (un fichier par extracteur, plages d'identifiants disjointes), `03-extraits/corpus-retenu.md` | Sélection des sources réellement pertinentes ; extraction des passages, citations, données, faits, en conservant provenance et localisation. | Chaque question secondaire a au moins un extrait ou une mention explicite « aucun extrait trouvé ». Chaque extrait est verbatim et localisé. |
| 4. Analyse, annotation, synthèse | `04-analyse/synthese.md` (les fiches = les `parts/*.jsonl`) | Analyse et confrontation des sources. Le dossier de recherche réunit corpus, bibliographie, extraits, notes et synthèse. | Notes référencées `[E<n>]`, dédoublonnées, sans transformation. Synthèse par question : convergences, divergences, lacunes. |
| 5. Conception | `05-conception/plan.md` | Organisation argumentative, démonstrative ou narrative du document final. | Plan conforme aux sections imposées ; extraits affectés par section ; lacunes à déclarer positionnées. |
| 6. Rédaction | `06-redaction/manuscrit.md` | Première matérialisation complète du document. | Texte complet, chaque affirmation factuelle citée, longueur dans la cible. |
| 7. Révision et relecture | `07-revision/verification.md` (corrections appliquées par éditions ciblées du manuscrit) | Révision du fond et de la structure, vérification des faits et des sources, style, correction, conformité aux attentes. | Grille de vérification remplie (voir ci-dessous) ; toutes les anomalies corrigées ou déclarées ; au plus un aller-retour vers 2-3. |
| 8. Livraison | `08-livraison/rapport.md`, `retex.md` | Version validée et mise en forme, remise au commanditaire. | Rapport final avec section `## Sources` ; journal et retex écrits. |

## Gabarit — `01-cadrage/cadrage.md` (≤ 40 lignes)

```markdown
# Cadrage
## Demande (reformulée)
## Questions de recherche
Q1 … / Q2 … (numérotées ; chaque section du livrable final s'y rattache)
## Attentes du livrable
- Format : … · Longueur : … · Langue : … · Public : … · Ton/style : …
- Sections imposées : … · Tableaux/colonnes imposés : …
- Contraintes explicites du brief (interdits, définitions à utiliser, calculs demandés) : …
## Critères de sélection des sources
## Politique de corpus
Fermé strict | acquisition des références nommées par le brief : …
## Références initiales (du brief)
## Plan de délégation
| Sous-agent | Questions | Sources pressenties | Plafond extraits | Plafond lectures/requêtes | Ids |
## Budget
Tours du responsable (≤ 12), sous-agents (≤ 8), allers-retours 7→3 (1), plafond monétaire s'il est fixé, réserve rédaction-relecture (1/3) : …
```

## Gabarit — `02-collecte/bibliographie.md`

```markdown
# Bibliographie de travail
| Réf | Fichier / identifiant | Titre | Nature | Couvre (Q…) | Ne couvre pas | Statut |
|---|---|---|---|---|---|---|
| D1 | … | … | article / donnée / note interne … | Q1, Q3 | Q4 | disponible / acquis / manquant |
## Manques constatés
## Décision de couverture
Suffisante pour livrer (avec lacunes déclarées : …) | Arbitrage requis (motif)
```

## Gabarit — `04-analyse/synthese.md`

Par question : ce que disent les sources (avec `[E<n>]`), convergences,
divergences (les deux positions, les deux extraits), lacunes. Une rubrique
finale « Points de vigilance pour la rédaction » (chiffres à recopier tels
quels, définitions à respecter, pièges du brief).

## Gabarit — `07-revision/verification.md`

```markdown
# Vérification
## Citations (une ligne par citation du manuscrit)
| § | Affirmation (résumé) | Citation | L'extrait soutient-il l'affirmation ? | Action |
## Chiffres
| Chiffre dans le texte | Extrait | Identique (valeur, unité, période) ? | Action |
## Conformité au brief
Sections : … · Longueur : … mots (cible …) · Langue : … · Ton : … · Tableaux/colonnes : …
## Affirmations sans extrait
## Redondances / hors-sujet / transitions
## Manques → aller-retour 2-3 nécessaire ? (oui/non, quoi)
```

## Section `## Sources` du rapport final

```markdown
## Sources
### Extraits cités
- [E1] <fichier> — <localisation> — « <premiers mots de l'extrait…> »
- [E2] …
### Bibliographie
- D1 — <titre> — <fichier> — <URL si connue>
```

C'est la seule place du rapport où une URL peut apparaître.
