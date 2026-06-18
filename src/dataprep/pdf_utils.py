"""PDF parsing helpers for dataprep ingestion."""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

MAX_CHARS_PER_PAGE = 20_000


@dataclass
class ParsedPdfDocument:
    text: str
    page_count: int
    extracted_pages: int
    extracted_chars: int
    title: str | None = None


def is_pdf_path(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def looks_like_pdf_bytes(raw_data: bytes) -> bool:
    return raw_data.startswith(b"%PDF-")


def extract_pdf_text_from_path(path: Path) -> ParsedPdfDocument:
    with open(path, "rb") as f:
        return extract_pdf_text_from_bytes(f.read(), source_name=path.name)


def extract_pdf_text_from_bytes(raw_data: bytes, source_name: str) -> ParsedPdfDocument:
    reader = PdfReader(io.BytesIO(raw_data))
    page_texts: list[str] = []
    page_count = len(reader.pages)

    for index, page in enumerate(reader.pages, start=1):
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:
            logger.warning(
                "[pdf] Failed to extract page %s/%s from %s: %s",
                index,
                page_count,
                source_name,
                exc,
            )
            continue

        cleaned = _normalize_pdf_text(extracted)
        if not cleaned:
            continue
        if len(cleaned) > MAX_CHARS_PER_PAGE:
            logger.info(
                "[pdf] Truncating page %s/%s from %s to %s chars",
                index,
                page_count,
                source_name,
                MAX_CHARS_PER_PAGE,
            )
            cleaned = cleaned[:MAX_CHARS_PER_PAGE].rstrip()
        page_texts.append(f"## Page {index}\n\n{cleaned}")

    if not page_texts:
        raise ValueError(f"No readable text extracted from PDF: {source_name}")

    text = "\n\n".join(page_texts)
    metadata = reader.metadata or {}
    raw_title = metadata.get("/Title") if isinstance(metadata, dict) else None
    title = _normalize_title(str(raw_title)) if raw_title else None

    parsed = ParsedPdfDocument(
        text=text,
        page_count=page_count,
        extracted_pages=len(page_texts),
        extracted_chars=len(text),
        title=title or None,
    )
    logger.info(
        "[pdf] Parsed %s: pages=%s, extracted_pages=%s, extracted_chars=%s",
        source_name,
        parsed.page_count,
        parsed.extracted_pages,
        parsed.extracted_chars,
    )
    return parsed


def _normalize_pdf_text(text: str) -> str:
    normalized = text.replace("\x00", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
