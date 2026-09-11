# Spike #235 — frontier + skill vs workflow

Outillage du spike (issue #235). Le skill lui-même est `skills/document-research/`
(standard Agent Skills, symlinké dans `.claude/skills/` et `.agents/skills/`).

- `run_skill.py` — lance un run headless du skill (`claude -p`), bras A (fichiers) ou B (dataprep MCP), dossier de travail isolé, allowlist d'outils, refus de lecture du dépôt et des autres runs, journal d'événements, coût/tokens/tours.
- `pack_adapter.py` — traduit le dossier de travail du skill en pack notable par l'évaluateur (report.md, sources.json, chunks.json, stats.json, raw_sources/). Adaptateur côté banc : le skill ne connaît pas le contrat.
- `make_catalogue.py` — catalogue du fonds pour le bras A (référence du brief → fichier local).
- `campaign_runs.py` — batterie N runs en parallèle pour un exercice et un bras, puis adaptation en packs. La correction se fait ensuite avec le skill `benchmark-campaign`.
- `open-eval/` — évaluation ouverte sur un thème tiers (kéto) : brief, grille de lecture, lectures.
- `NOTE-DE-DECISION.md` — livrable du spike.

Les dossiers de travail vivent hors du dépôt (`../spike235-work/<run>/`, car les règles de refus couvrent tout le dépôt) et sont archivés dans `output/spike235/<run>/` (non suivi).
