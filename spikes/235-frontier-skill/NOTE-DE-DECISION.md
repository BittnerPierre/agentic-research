# Note de décision — spike #235 : IA frontier + skill vs workflow orchestrant des modèles petits/moyens

*Version de travail du 11/09/2026 ; les sections 4 et 6 sont complétées après les derniers runs.*

## 1. Question

Une IA frontier dotée d'un bon harnais et d'un skill bien établi fait-elle mieux qu'un workflow
agentique orchestrant des modèles petits ou moyens, sans intervention humaine, avec une faible
déviance, à l'échelle (coût par livrable, débit) ? Ce que l'on mesure : la qualité au banc
déterministe (lettres de confiance, couverture), le coût par run, la durée, le volume de tokens,
et la dispersion entre runs.

## 2. Dispositif

- **Skill** `document-research` (standard Agent Skills, dossier `skills/document-research/`) :
  les 8 étapes du processus de recherche documentaire, un livrable lisible par étape, une main
  courante, des extraits verbatim cités `[S<n>]`, les arbitrages du cadrage (va au bout ; humain
  seulement pour trois cas d'arbitrage ; corpus fermé ; étape 4 sans transformation ; un
  aller-retour révision → extraction). Le skill porte l'objectif, la méthode et les outils ; il
  ne porte aucun plafond codé (tours, sous-agents, requêtes) : la répartition du budget est un
  choix du responsable au cadrage. Le mécanique est fait par des scripts Python autonomes du
  package (inventaire, extraction verbatim par plages de lignes, contrôle des extraits,
  vérification du manuscrit, assemblage du rapport) : zéro token pour ce qui ne demande pas de
  jugement.
- **Harnais** : Claude Code en mode autonome (`claude -p`), plafond monétaire dur par run,
  outils limités (fichiers, recherche textuelle, sous-agents, scripts du package, MCP), aucune
  lecture du dépôt, dossier de travail hors dépôt. Modèle du responsable et modèle des
  sous-agents fixés par le harnais.
- **Bras A** : le fonds est un dossier de fichiers (lecture, recherche textuelle). Contrôle.
- **Bras B** : le fonds est la base de connaissances dataprep via MCP (acquisition, indexation,
  catalogue, recherche vectorielle par un serveur compagnon qui expose le pipeline de retrieval
  des agents du workflow). Représentatif d'une base à l'échelle.
- **Adaptateur banc** (séparé du skill) : assemble le pack notable (`report.md`, `sources.json`,
  `chunks.json`, `stats.json`, `raw_sources/`) à partir du dossier de travail, sans réécrire le
  texte. L'évaluateur, les exercices, les corpus et `adjustments.yaml` n'ont pas été modifiés.
- **Développement à l'aveugle du banc** : mise au point sur un thème tiers (régime kéto, sept
  sources publiques), évaluation ouverte par grille de lecture et contrôles mécaniques.

## 3. Ce que le développement a appris (thème tiers, 5 runs)

| Run | Skill | Modèle | Durée | Coût | Constat |
|---|---|---|---|---|---|
| A1 kéto | v1 | Fable partout | 50 min | 24,7 $ | fond honnête (pièges France et sport évités, 0 chiffre inventé) ; le responsable a lu le fonds entier puis l'a relu à chaque tour (87 tours, 6,5 M tokens) |
| B1 kéto | v1 | Fable partout | 27 min | 29,2 $ | fond honnête ; 3 extracteurs sans plafond (90 requêtes, 70 % du budget), longueur estimée au lieu de mesurée (+37 %) |
| B-sonnet 1 à 3 kéto | v3 | Sonnet partout, 1 $ | 2 à 3 min | 1,0 à 1,1 $ | trois défauts de harnais corrigés (dossier de travail sous le dépôt refusé, scripts non autorisés, sous-agents en arrière-plan coupés à la fin du tour) ; extraction complète à 0,9 $ ; livraison hors plafond |

Conclusions de cette phase : (1) le coût vient du contexte relu à chaque tour et de la sortie
du modèle, pas de la recherche ; (2) tout ce qui est mécanique doit sortir du modèle ; (3) en
mode autonome, la délégation doit être synchrone et le responsable ne doit jamais terminer son
tour avant la livraison ; (4) le modèle des sous-agents doit être imposé par le harnais, une
consigne n'est suivie qu'une fois sur deux.

## 4. Résultats au banc

Voir §4 bis pour le tableau consolidé, complété après les runs bras A et bras B Sonnet.

### 4.1 Bras B, Fable responsable + Sonnet sous-agents (quatre runs de fumée, N=1 par génération)

| Génération | Conceptuel | Finance | Durée | Coût | Tokens |
|---|---|---|---|---|---|
| Fumée 1 (sans scripts, sous-agents Fable au conceptuel) | 81,2 % (13/16) | A, 100 % (42/42), 2 056 mots | 371 s / 666 s | 4,90 $ / 5,13 $ | 1,0 M / 0,8 M |
| Fumée 2 (harnais corrigé, scripts, relecteur) | 75,0 % (12/16) | A, 100 % (42/42), 1 749 mots | 566 s / 573 s | 3,98 $ / 4,55 $ | 1,3 M / 1,8 M |

Zéro chiffre faux, zéro invention, zéro distracteur sur les quatre runs. En finance, le run de
fumée 2 est le seul de tout le tableau à ne manquer aucune exigence critique reconnue par le
vérificateur déterministe hors le faux positif #237 ; aucune intervention humaine.

### 4.2 Références (campagnes N=5, juillet et septembre 2026)

| Ligne | Conceptuel (couv. méd., min–max) | Finance | Durée | Tokens | Coût / run |
|---|---|---|---|---|---|
| gpt-5.6-sol | 87,5 % (81–88) | A×5, 100 % (86–100) | 202 s / 166 s | 300 k / 613 k | 1,68 $ / 3,04 $ |
| gpt-5.4-mini | 68,8 % (69–88) | A×5, 85,7 % (74–100) | 74 s / 58 s | 416 k / 612 k | 0,40 $ / 0,56 $ |
| DSV4F-0731 (2 DGX Spark) | 75,0 % (56–88) | A×5, 100 % (90–100) | 219 s / 254 s | 261 k / 321 k | machine |

Coûts des références aux tarifs texte API (gpt-5.6-sol 4 / 20 $ par million, gpt-5.4-mini
0,75 / 4,50), calculés par Pierre sur les médianes de tokens sans cache.

### 4.3 Seconde lecture

- Conceptuel : les échecs du skill sont du même type que ceux des références (few-shot et
  zero-shot définis à partir d'un exemple au lieu de déclarer la lacune ; orchestration sans
  l'intégration des résultats). Dispersion entre les deux fumées : 81 → 75, du même ordre que la
  dispersion des références (gpt-5.6-sol 81–88, DSV4F 56–88).
- Finance : les deux réserves « non qualifié » du run de fumée 2 sont deux faux positifs de
  l'évaluateur signalés dans l'issue #237 (exigence non numérique présente en tableau ; preuve
  vraie mais tirée d'un autre fichier du corpus que celui attendu). Ces deux familles touchent
  aussi les cinq runs gpt-5.6-sol.

## 5. Ce que le skill a appris au harnais, et l'inverse

À compléter.

## 6. Décision

À compléter.

## 7. Limites et suites

- N=1 ou N=2 par cellule pour le skill : les dispersions annoncées sont indicatives ; la
  campagne N=5 en Fable + Sonnet a été écartée pour son coût (45 $ de prix liste).
- Le drapeau « qualifié » du banc est faux pour tous les runs finance des références (issue
  #237) ; il n'entre pas dans le podium officiel.
- Le MCP dataprep livré n'expose pas la recherche vectorielle ; le bras B a exigé un serveur
  compagnon (`skills/document-research/mcp/dataprep_search_server.py`) qui réutilise le
  pipeline des agents du workflow.
