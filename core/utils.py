import re
import unicodedata


MESES_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def _normalize_label(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    return normalized.encode("ascii", "ignore").decode("ascii")


def _normalize_year(raw_year: str) -> int:
    year = int(raw_year)
    return year + 2000 if year < 100 else year


def mes_sort_key(m: str) -> tuple[int, int]:
    """Converte formatos de mês suportados em `(ano, mês)` para ordenação cronológica."""
    if not isinstance(m, str):
        return (0, 0)

    raw = m.strip()
    numeric_match = re.fullmatch(r"(\d{1,2})/(\d{2,4})", raw)
    if numeric_match:
        month = int(numeric_match.group(1))
        year = _normalize_year(numeric_match.group(2))
        if 1 <= month <= 12:
            return (year, month)
        return (0, 0)

    named_match = re.fullmatch(r"([A-Za-zÀ-ÿ]+)\s+(\d{2,4})", raw)
    if named_match:
        month_name = _normalize_label(named_match.group(1))
        month = MESES_PT.get(month_name)
        if month:
            year = _normalize_year(named_match.group(2))
            return (year, month)

    return (0, 0)
