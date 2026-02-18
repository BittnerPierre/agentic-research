from __future__ import annotations


def normalize_filenames(filenames: list[str] | None) -> list[str]:
    if not filenames:
        return []
    normalized: list[str] = []
    for name in filenames:
        cleaned = str(name).strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized
