# Spike 262 : banc v2 visuel

Issue : #262. Branche spike, PR en draft, ne pas merger sans revue explicite.
Travail des 9 et 10 novembre 2026, mene hors depot (claude/financial analysis/) puis range ici
tel quel. Rien dans src/ ni evaluations/ n est modifie ; les deux scripts du spike importent
evaluations/deterministic_grade.py comme bibliotheque sans y toucher.

## Question

Le banc deterministe (lettres de confiance, couverture, N=5) n est pas montrable en video.
Que faut-il ajouter, sans casser le banc, pour que la difference entre modeles se lise a l ecran ?

## Les trois briques du spike

1. Corpus qualitatif FY2025 (extracts_10k_fy2025/). Six fichiers d extraits textuels des 10-K
   FY2025, huit themes fixes (T1 strategie, T2 capex, T3 trajectoire, T4 contraintes, T5
   amortissement, T6 baux et engagements, T7 risques, T8 non divulgue), 251 lignes de citation
   verifiees mot pour mot contre le texte EDGAR. EDGAR_SOURCES.md donne les URLs et accessions,
   SHA256SUMS_10k_mirror.txt les empreintes du miroir (208 Mo, hors depot). Les extraits portent
   des chiffres de prose a base differente du CSV XBRL de l exercice ai-capex-intensity :
   Amazon capex cash 128,3 (131,8 moins 3,5 de proceeds et incentives), Meta 72,2 (69,7 plus
   2,5 de principal des baux financiers), NVIDIA 3,4 (3,2 plus 0,1 de principal). Memes
   exercices, definitions differentes, gardes pour tester la maitrise des modeles.

2. Etape dashboard, non notee (dashboard/). Un brief fige (brief_dashboard_v1.md : situation,
   ce que le Managing Partner veut comprendre, role, maniere d ecrire, contraintes ; v1.1 ajoute
   l auto-verification du HTML), le rapport quanti du modele lui-meme (inputs/) et les six
   extraits, en un seul appel, zero outil, zero agent, zero skill, un fichier HTML autonome.
   Cinq modeles, resultats et lecons dans RESULTS_2026-11-09.md, sorties dans outputs/.
   ai_capex_dashboard_v0.html est le contre-exemple fait sur un brief de trois lignes.

3. Visualisateur annote du rapport quanti, programmatique (report_viewer/). Le report.md d un
   run rendu en HTML avec des couches activables : nombres (fait attendu, present dans la liste
   blanche, hors corpus, fabrique, invérifiable), tableaux du contrat (colonnes Company, Metric,
   Period, Value, cellules valeur et periode verifiees), structure (chapitres du contrat et hors
   contrat, chapitres manquants), matrice societe x metrique, marge (score, blockers, couverture,
   valeurs fausses, fabrications, ton, format) et bloc Execution (temps et tokens par phase,
   requetes, appels agents, sources, debit d ecriture). Chaque marque a un tooltip qui dit
   pourquoi. Zero LLM : deterministic_grade.py fournit l extraction des nombres, les tableaux
   et la liste blanche ; det_grade.json et stats.json fournissent les verdicts et les mesures.

## Ce que le spike montre

- Avec une mise en situation, les cinq modeles ecrivent dans le registre investment research,
  nomment les trois bases de capex, traitent Apple en temoin et separent guidance initiale,
  reels et indications 2026. Aucun chiffre invente repere a la lecture (controle fait par fait
  a faire avec le visualisateur).
- Modeles de raisonnement : le raisonnement compte dans les tokens de sortie, plafond a 120 000 ;
  controle node --check du script inline apres generation ; un tour de correction avec l erreur
  exacte suffit (Mistral Large 4, sequences \n litterales dans un tableau JavaScript).
- Le visualisateur rend visibles deux angles morts du grader : des faux positifs (le libelle
  Capex / operating cash flow canonise en Operating cash flow) et la colonne Period jamais
  controlee (les deux rapports Mistral Large 4 a 100 du 13/10 ecrivent NVIDIA FY2025 ended
  Jan 2026 ; le run 220648 ecrit ended Dec 2024 pour Amazon, Alphabet et Meta).
- Un run par modele, niveaux de raisonnement laisses par defaut : variance inconnue, pas de
  classement a en tirer. Le podium reste celui de la campagne du 13/10 apres seconde lecture.

## Resultats dashboard (un run par modele)

| Modele | Brief | Temps | Tokens prompt | Tokens sortie | HTML | Mots de prose | JS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-5.6-sol | v1 | 130 s | 31 515 | 15 717 | 53 Ko | 2 424 | OK |
| Claude Fable 5.1 (claude -p) | v1 | 853 s | n/a | ~21 300 visibles | 85 Ko | 4 347 | OK |
| Mistral Large 4 | v1.1 | 367 s + 224 s | 32 113 puis 52 656 | 34 745 puis 28 382 | 70 Ko | 4 190 | casse, puis OK |
| DeepSeek V4.1 Flash (rapport du V4 Flash 0731) | v1.1 | 69 s | 31 866 | 19 999 | 64 Ko | 3 722 | OK |
| GLM 5.3 | v1.1 | 529 s | 32 325 | 111 277 | 77 Ko | 4 693 | OK |

Detail, lecture qualitative et lecons dans dashboard/RESULTS_2026-11-09.md.

## Arborescence

- dashboard/brief_dashboard_v1.md, RESULTS_2026-11-09.md, ai_capex_dashboard_v0.html
- dashboard/inputs/ : un rapport quanti par modele (provenance dans README.md), deux grades
- dashboard/outputs/ : gpt56sol, fable51, ml4.v1_broken (JS casse), ml4_fix (corrige),
  dsv41flash, glm53 ; ml4.error.txt (erreur node exacte), ml4.truncated60k.raw.txt (essai
  coupe a 60 000 tokens, non compte), logs/
- dashboard/tools/run_dashboard.py : le lanceur
- extracts_10k_fy2025/ : six extraits, README, EDGAR_SOURCES.md, empreintes du miroir
- report_viewer/tools/report_viewer.py : le visualisateur
- report_viewer/runs/ : report.md, det_grade.json, stats.json des quatre runs rendus
  (identifiant complet dans RUN_ID.txt), copies depuis benchmarks/runs (hors depot)
- report_viewer/*.html : les quatre rendus

Restes hors depot : miroir EDGAR complet et Company Facts (230 Mo), captures d ecran headless
des dashboards (4,3 Mo de PNG), fichiers .prompt.txt et .raw.txt des sorties (le prompt se
reconstruit avec run_dashboard.py ; le raw est le HTML a l octet pres, sauf extraction).

## Reproduire

Dashboard (cles OPENAI_API_KEY ou MISTRAL_API_KEY dans l environnement ou .env ; Claude via
le CLI sous abonnement) :

    DASH_MAX_TOKENS=120000 uv run python spikes/262-benchmark-v2-visual/dashboard/tools/run_dashboard.py glm53 litellm:mistral/zai-glm-5-3 spikes/262-benchmark-v2-visual/dashboard/inputs/quant_report_glm53_20261013_222440.md
    uv run python spikes/262-benchmark-v2-visual/dashboard/tools/run_dashboard.py fable51 claude-cli:claude-fable-5-1 spikes/262-benchmark-v2-visual/dashboard/inputs/quant_report_fable51_20260911_132624.md
    node --check sur le script inline ; en cas d erreur :
    uv run python .../run_dashboard.py ml4_fix fix:mistral/mistral-large-4 outputs/ml4.raw.txt outputs/ml4.prompt.txt outputs/ml4.error.txt

Visualisateur (un dossier de run contenant report.md, det_grade.json et stats.json) :

    uv run python spikes/262-benchmark-v2-visual/report_viewer/tools/report_viewer.py spikes/262-benchmark-v2-visual/report_viewer/runs/ml4_220648 evaluations/exercises/ai-capex-intensity out.html

## Suite, sur go explicite, une issue par brique

1. Visualisateur annote dans evaluations/ : cote a cote de deux runs, chapitres manquants
   places a leur position attendue, alias de metriques alignes sur le grader, couche citations,
   controle de la colonne Period.
2. Etape dashboard dans le pipeline : role writer final avec le brief v1.1, plafond de sortie
   eleve, controle JavaScript et un tour de correction.
3. Format Markdown strict et grille quali depuis les extraits (issue chapeau v2).
