from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel


class SearchItem(BaseModel):
    reason: str
    "Votre raisonnement de pourquoi cette recherche est importante pour la requête et le résultat attendu."

    query: str
    "La requête à utiliser pour la recherche."


T = TypeVar("T", bound=SearchItem)


class SearchPlan(BaseModel, Generic[T]):  # noqa: UP046
    searches: list[T]
    """Une liste de recherches à effectuer pour mieux répondre à la requête."""


class FileSearchItem(SearchItem):
    filenames: list[str] | None = None
    "Liste optionnelle des fichiers à cibler pour cette recherche."


class WebSearchItem(SearchItem):
    pass


class FileSearchPlan(SearchPlan[FileSearchItem]):
    pass


class WebSearchPlan(SearchPlan[WebSearchItem]):
    pass


class FileSearchResult(BaseModel):
    file_name: str
    "Le nom du fichier contenant les résultats de la recherche."


class SourceDocument(BaseModel):
    """A single aggregated research source, built programmatically from a
    search-result file (no LLM, no MCP).

    Produced by the report_writer aggregation step right after the search phase
    so the writer never has to load files itself. The stable ``source_id`` is
    what chapter writers use to cite material inline (e.g. ``[S3]``).
    """

    source_id: str
    "Identifiant stable de la source pour les citations inline (ex: `S1`, `S2`)."

    file_name: str
    "Nom de base du fichier de résultat de recherche."

    topic: str
    "Sujet lisible dérivé du nom de fichier (= terme de recherche)."

    content: str
    "Contenu textuel complet du résumé de recherche."

    doc_ids: list[str] = []
    "Citations `[document_id:chunk_index]` extraites du contenu (peut être vide)."


class Chapter(BaseModel):
    """One planned chapter of the report (issue #196, writer décomposé)."""

    title: str
    "Titre du chapitre."

    objective: str
    "Objectif du chapitre en 1-2 phrases (ce qu'il doit couvrir)."

    source_ids: list[str] = []
    "Sources prioritaires (ids `[S#]`) — une INDICATION pour le rédacteur, pas un filtre."


class ReportOutline(BaseModel):
    """Structured report plan produced by the outline step (D1)."""

    title: str
    "Titre du rapport."

    chapters: list[Chapter]
    "Chapitres ordonnés à rédiger."


class FileFinalReport(BaseModel):
    absolute_file_path: str
    "Le chemin absolu du fichier contenant le rapport final."

    short_summary: str
    "Le résumé court du rapport final."

    follow_up_questions: list[str]
    "Les questions suivantes à explorer."


@dataclass
class ResearchInfo:
    temp_dir: str
    output_dir: str
    max_search_plan: str = "1"
    vector_store_name: str | None = None
    vector_store_id: str | None = None
    search_results: list[str] = field(default_factory=list)
    """List of filenames resulting from research (e.g., .txt, .md, .pdf files)."""


class ReportData(BaseModel):
    file_name: str
    """The name of the file containing the final report."""

    research_topic: str
    """The main research topic following naming rules : no space (use `_` instead) or special caracter)."""

    short_summary: str
    """A short 2-3 sentence summary of the findings."""

    markdown_report: str
    """The final report"""

    follow_up_questions: list[str]
    """Suggested topics to research further"""
