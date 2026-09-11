# Note de décision — spike #235 : IA frontier + skill vs workflow orchestrant des modèles petits/moyens

*11/09/2026. Huit runs du skill au banc (N=1 ou 2 par cellule), quatre lignes de référence N=5. Les dispersions du skill sont indicatives.*

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

Évaluateur, exercices, corpus et exceptions inchangés. Coût des runs du skill = prix liste du
harnais (abonnement Claude Code, cache compris) ; coût des références = tarifs texte API sur les
médianes de tokens sans cache (calcul de Pierre). Durée = mur, du lancement à la livraison.

### 4.1 Tableau (tri du banc : gravité puis couverture)

**Conceptuel** (couverture ; lettres sans objet par arbitrage)

| Ligne | N | Couverture (min–max) | Durée | Tokens | Coût / run |
|---|---|---|---|---|---|
| Fable + Sonnet, skill, bras A (fichiers) | 1 | 87,5 % | 532 s | 1,0 M | 3,93 $ |
| gpt-5.6-sol, workflow | 5 | 87,5 % (81–88) | 202 s | 300 k | 1,68 $ |
| Sonnet partout, skill, bras B (dataprep) | 1 | 81,2 % | 589 s | 3,1 M | 2,05 $ |
| Fable + Sonnet, skill, bras B (dataprep) | 2 | 78,1 % (75–81) | 371 s / 566 s | 0,6 / 0,7 M | 4,90 $ / 3,98 $ |
| DSV4F-0731, workflow (2 DGX Spark) | 5 | 75,0 % (56–88) | 219 s | 261 k | machine |
| gpt-5.4-mini, workflow | 5 | 68,8 % (69–88) | 74 s | 416 k | 0,40 $ |

**Finance** (lettres : A propre, C au moins un chiffre faux, D une invention, F plusieurs)

| Ligne | N | Confiance | Couverture | Durée | Tokens | Coût / run |
|---|---|---|---|---|---|---|
| DSV4F-0731, workflow | 5 | A A A A A | 100 % (90–100) | 243 s | 321 k | machine |
| Fable + Sonnet, skill, bras B | 2 | A A | 100 % (100–100) | 666 s / 573 s | 0,5 / 1,0 M | 5,13 $ / 4,55 $ |
| gpt-5.6-sol, workflow | 5 | A A A A A | 100 % (86–100) | 166 s | 613 k | 3,04 $ |
| gpt-5.4-mini, workflow | 5 | A A A A A | 85,7 % (74–100) | 58 s | 612 k | 0,56 $ |
| Fable + Sonnet, skill, bras A | 1 | C | 100 % | 458 s | 0,7 M | 3,32 $ |
| Sonnet partout, skill, bras B | 1 | C | 100 % | 730 s | 4,9 M | 3,02 $ |

Les huit runs du skill : zéro invention, zéro distracteur, zéro intervention humaine, tous les
chiffres attendus retrouvés en finance (42/42 à chaque fois). Les tokens du skill comptent, comme
ceux du workflow, le contexte relu à chaque requête ; Sonnet, qui travaille en tours plus courts
et plus nombreux (57 à 93 tours), relit beaucoup plus.

### 4.2 Seconde lecture (obligatoire avant publication)

- **Les deux C** sont, à la relecture, deux faux positifs de l'évaluateur, à traiter par
  exception post-examen (proposées à Pierre, non écrites) : bras A finance, les « chiffres
  faux » sont les guidances Amazon (~100 Md$) et Alphabet (~75 Md$) dans une table de guidance au
  format imposé, dont l'intitulé de métrique « Initial capex guidance » est lu comme le capex
  réalisé (variante de la famille « tableau guidance » du catalogue) ; Sonnet finance, la phrase
  « capex is not available in this corpus for FY2020 and FY2021 » à propos de NVIDIA est lue
  comme une indisponibilité FY2025, alors que la table donne 3,2 Md$ pour FY2025. Les lettres
  restent C dans le tableau (une exception ne blanchit que D et F).
- **Finance, drapeau « non qualifié »** : le run bras B fumée 2 (100/100) porte deux réserves
  qui sont deux familles de faux positif signalées dans l'issue #237 (exigence non numérique
  présente mais en tableau ; preuve vraie tirée d'un autre fichier du corpus que celui attendu).
  Ces familles touchent aussi les cinq runs gpt-5.6-sol : aucun run finance du tableau n'est
  « qualifié ».
- **Conceptuel** : les exigences perdues par le skill sont du même type que celles des
  références : few-shot ou zero-shot définis à partir d'un exemple du corpus au lieu de déclarer
  la lacune, orchestration sans l'intégration des résultats des sous-agents, embeddings sans le
  lien explicite vecteurs → similarité → retrieval. Aucune définition venue de mémoire n'a été
  sanctionnée.
- **Dispersion** : deux runs Fable + Sonnet bras B au conceptuel donnent 81 et 75 ; les quatre
  cellules du skill au conceptuel s'étalent de 75 à 87,5, soit l'intervalle de gpt-5.6-sol
  (81–88) élargi vers le bas jusqu'à la médiane de DSV4F. En finance les huit runs sont à 100 %
  de couverture ; la variance est dans la forme (longueur 1 384 à 2 056 mots) et dans les
  accidents de lecture de l'évaluateur, pas dans les chiffres.

### 4.3 Coût et débit

| Cellule | Coût / run | Durée / run | Runs parallèles observés | Débit (runs / heure, 4 en parallèle) |
|---|---|---|---|---|
| Fable + Sonnet, skill | 3,3 à 5,1 $ | 7,6 à 11 min | 4 sans incident | ~25 |
| Sonnet partout, skill | 2,0 à 3,0 $ | 9,8 à 12 min | 2 | ~20 |
| gpt-5.6-sol, workflow | 1,7 à 3,0 $ | 2,8 à 3,4 min | 1 par batterie (séquentiel par design) | ~20 (séquentiel), plus si parallélisé |
| gpt-5.4-mini, workflow | 0,4 à 0,6 $ | 1 à 1,2 min | idem | ~55 |
| DSV4F-0731, workflow | coût machine (2 DGX Spark) | 3,7 à 4,2 min | 1 (un seul vLLM) | ~15 |

Le harnais accepte sans difficulté quatre runs en parallèle (runs bras A et B lancés ensemble) ;
la limite pratique est la fenêtre de 5 heures de l'abonnement, consommée à raison d'environ 17
points de pourcentage par run Fable + Sonnet.

## 5. Ce que le skill a appris au harnais, et l'inverse

Ce qui est venu gratuitement du harnais : les sous-agents à contexte frais et en parallèle, la
possibilité de fixer leur modèle, le plafond monétaire dur, le flux d'événements qui donne coût,
tokens et chronologie par étape, la reprise possible d'un run à partir de ses livrables. Ce que
le skill a dû apporter, et qui n'était pas là : la méthode (les 8 étapes et leurs livrables),
la doctrine (verbatim, lacunes déclarées, corpus fermé), les scripts qui retirent le mécanique
du modèle (le premier run sans scripts a coûté 25 $ et 50 minutes ; avec scripts, 3 à 5 $ et 8
à 11 minutes), et trois règles de conduite en mode autonome (délégation synchrone, ne jamais
terminer son tour avant la livraison, commandes shell simples).

Ce qui a coûté le plus cher à apprendre : quatre défauts de harnais successifs (dossier de
travail sous le dépôt refusé, scripts non autorisés, sous-agents en arrière-plan coupés à la fin
du tour, chemins absolus hors de la règle d'autorisation), chacun découvert par un run raté. Un
harnais est un système à régler, pas un acquis.

Ce que le skill n'a pas su faire seul : tenir la longueur sans script (A1, B1, fumée 1) ; ne
pas combler une lacune quand le corpus offre un exemple sans définition (few-shot, zero-shot) ;
suivre la consigne « sous-agents sur Sonnet » sans que le harnais l'impose.

## 6. Décision

**Sur la question posée.** Sur ces deux exercices, un modèle frontier avec le skill atteint la
qualité du meilleur workflow de référence : en finance, A et 100 % à chaque run avec Fable
responsable (deux runs), et 100 % de couverture sans invention dans les huit runs ; au
conceptuel, 75 à 87,5 % selon la cellule, contre 81 à 88 pour gpt-5.6-sol. Il n'a pas fait
**mieux** : la pointe est la même, et il l'atteint pour 1,5 à 2 fois le coût par run de
gpt-5.6-sol, 2 à 4 fois sa durée, avec une variance conceptuelle au moins égale. Face au workflow
à petit modèle (gpt-5.4-mini, 0,4 à 0,6 $ et une minute), le skill fait mieux en qualité
(87,5 contre 68,8 au conceptuel ; 100 contre 85,7 en finance) pour 5 à 8 fois le coût et 8 à 10
fois la durée. Face au workflow sur modèle local (DSV4F sur deux DGX Spark), la qualité est
équivalente en finance et supérieure au conceptuel, à coût marginal non comparable.

**Sur l'orientation.** Hybride, avec une répartition nette :

1. **La méthode va dans le skill.** Les 8 étapes, les livrables, les doctrines et les scripts
   sont portables (standard Agent Skills, aucun SDK) et ont fonctionné sur deux harnais de fait
   (Claude Code avec Fable, avec Sonnet). C'est là que la valeur du projet agentic-research
   s'exprime le mieux : la méthode et les évaluateurs, pas le code d'orchestration.
2. **Le workflow codé reste l'outil de la répétabilité à petit coût.** Même modèle, même
   instruction, le workflow tient 58 à 250 secondes et 0,4 à 3 $ avec une variance connue ;
   le skill tient 8 à 12 minutes et 2 à 5 $ avec une variance à mesurer sur N=5 (non fait ici
   pour son coût). À l'échelle de dix livrables en parallèle, le harnais suit, mais le coût par
   livrable reste 2 à 5 fois celui du workflow à modèle équivalent.
3. **Le point commun aux deux est l'évaluateur.** La campagne a révélé trois familles de faux
   positifs (#237) qui touchent toutes les lignes ; le drapeau « qualifié » est faux pour tous
   les runs finance. La priorité de développement est là, avant toute nouvelle ligne.

**Ce qu'il faudrait pour trancher plus fermement** : une campagne N=5 en Sonnet partout (15 $)
pour mesurer la dispersion du skill à prix équivalent à gpt-5.6-sol, et la même chose sur un
modèle local via un harnais générique, cellule décisive identifiée dès le cadrage et non
couverte par ce spike.

## 7. Limites et suites

- N=1 ou N=2 par cellule pour le skill : les dispersions annoncées sont indicatives ; la
  campagne N=5 en Fable + Sonnet a été écartée pour son coût (45 $ de prix liste), celle en
  Sonnet partout (15 $) reste à décider.
- Les deux runs Sonnet partout ont d'abord été coupés par un garde-fou de 40 tours du lanceur,
  relancés à 150 ; le coût facturé par le harnais inclut le cache, celui des références non.
- Budget consommé : environ 100 $ de prix liste sur l'abonnement (dont 54 $ pour les deux runs
  de développement du skill v1), 1 $ d'appels au juge sur la clé OpenAI ; environ 9 heures
  d'agent sur deux journées.
- Le drapeau « qualifié » du banc est faux pour tous les runs finance des références (issue
  #237) ; il n'entre pas dans le podium officiel.
- Le MCP dataprep livré n'expose pas la recherche vectorielle ; le bras B a exigé un serveur
  compagnon (`skills/document-research/mcp/dataprep_search_server.py`) qui réutilise le
  pipeline des agents du workflow.
