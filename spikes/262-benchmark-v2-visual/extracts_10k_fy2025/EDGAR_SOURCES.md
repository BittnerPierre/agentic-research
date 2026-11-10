# 10-K FY2025 des six sociétés de l'exercice ai-capex-intensity

Identifiés depuis submissions.zip (bulk EDGAR du 13 juillet 2026). Les hashes des six
Company Facts JSON utilisés par generate.py sont dans companyfacts/SHA256SUMS.txt et
correspondent à evaluations/exercises/ai-capex-intensity/corpus/manifest.json.

| Société | Clôture FY2025 | Déposé le | Accession | Document principal |
| --- | --- | --- | --- | --- |
| Amazon | 2025-12-31 | 2026-02-06 | 0001018724-26-000004 | https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm |
| Alphabet | 2025-12-31 | 2026-02-05 | 0001652044-26-000018 | https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm |
| Meta | 2025-12-31 | 2026-01-29 | 0001628280-26-003942 | https://www.sec.gov/Archives/edgar/data/1326801/000162828026003942/meta-20251231.htm |
| Microsoft | 2025-06-30 | 2025-07-30 | 0000950170-25-100235 | https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm |
| NVIDIA | 2025-01-26 | 2025-02-26 | 0001045810-25-000023 | https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm |
| Apple | 2025-09-27 | 2025-10-31 | 0000320193-25-000079 | https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm |

Attention NVIDIA : le 10-K déposé en février 2026 (nvda-20260125.htm) est le FY2026, hors exercice.

Dans chaque dossier d'accession (URL sans le nom de fichier) se trouvent aussi :
- Financial_Report.xlsx : les états financiers XBRL en Excel
- <accession>.txt : la soumission complète
- <accession>-index.htm : la liste des pièces jointes (exhibits)

EDGAR exige un en-tête User-Agent avec nom et email pour tout téléchargement programmatique.

## Miroir local (9 novembre 2026)

Dossier 10k_fy2025/ : à la racine les six 10-K HTML, puis un sous-dossier par société
contenant le miroir complet du dossier d'accession EDGAR (726 fichiers, 208 Mo) :
- <accession>.txt : soumission complète ; <accession>-index.html : index des exhibits
- <accession>-xbrl.zip : instance XBRL et linkbases (états financiers bruts)
- exhibits (ex21 filiales, ex23 consentement auditeur, ex31/ex32 certifications, ex10 contrats, ex4 titres)
- FilingSummary.xml + R*.htm : états financiers rendus par la SEC
- Financial_Report.xlsx : publié par la SEC uniquement pour NVIDIA ; absent des cinq autres dépôts

Pages R des états principaux :
| Société | Compte de résultat | Bilan | Flux de trésorerie |
| --- | --- | --- | --- |
| Amazon | R4 | R7 | R3 |
| Alphabet | R5 (à vérifier) | R3 | R10 |
| Meta | R5 (à vérifier) | R3 | R9 |
| Microsoft | R2 | R4 | R6 |
| NVIDIA | R4 (à vérifier) | R5 | R9 |
| Apple | R3 | R5 | R8 |

SHA256SUMS.txt couvre htm, zip, xlsx et txt.

## Extraits quali (9 novembre 2026)

10k_fy2025/extracts/ : six fichiers d'extraits textuels par société, huit thèmes fixes, 251 lignes
de citation vérifiées contre les textes source. Voir extracts/README.md pour la structure, le
bilan par société et les points d'attention (chiffres de base différente du CSV XBRL).
