"""SEM Master utilities."""

from .config import get_settings, Settings, PROJECT_ROOT, DATA_DIR, CLIENTS_DIR
from .swedish_nlp import (
    get_stopwords,
    split_compound_word,
    generate_diacritics_variants,
    get_shorter_synonym,
    count_display_chars,
)

__all__ = [
    "get_settings",
    "Settings",
    "PROJECT_ROOT",
    "DATA_DIR",
    "CLIENTS_DIR",
    "get_stopwords",
    "split_compound_word",
    "generate_diacritics_variants",
    "get_shorter_synonym",
    "count_display_chars",
]


def __getattr__(name: str):
    if name in ("extract_text_from_pdf", "extract_brand_info"):
        from .pdf_reader import extract_text_from_pdf, extract_brand_info
        return {"extract_text_from_pdf": extract_text_from_pdf, "extract_brand_info": extract_brand_info}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
