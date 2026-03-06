"""PDF text extraction utilities."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_text_from_pdf(path: str | Path) -> str:
    """Extract all text from a PDF file."""
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_brand_info(path: str | Path) -> dict:
    """Extract brand-relevant content from a PDF.

    Returns a dict with keys: full_text, headings, urls, emails, phone_numbers.
    """
    import re

    text = extract_text_from_pdf(path)

    # Extract headings (lines that are short and likely titles)
    lines = text.splitlines()
    headings = [
        line.strip()
        for line in lines
        if line.strip() and len(line.strip()) < 80 and not line.strip().endswith(".")
    ][:20]

    urls = re.findall(r"https?://[^\s<>\"]+", text)
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone_numbers = re.findall(r"(?:\+46|0)[\d\s-]{7,12}", text)

    return {
        "full_text": text,
        "headings": headings,
        "urls": list(set(urls)),
        "emails": list(set(emails)),
        "phone_numbers": list(set(phone_numbers)),
    }
