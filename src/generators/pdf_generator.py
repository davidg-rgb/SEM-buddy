"""PDF report generation from markdown content."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_pdf_report(
    markdown_content: str,
    output_path: str,
    title: str = "Google Ads Strategy Report",
) -> str:
    """Convert markdown strategy report to PDF.

    Uses markdown-pdf library: Markdown -> HTML -> PDF.
    Handles Swedish characters correctly.

    Args:
        markdown_content: The markdown report string
        output_path: Path to write the PDF file
        title: PDF document title metadata

    Returns:
        The output path of the generated PDF
    """
    from markdown_pdf import MarkdownPdf, Section

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = MarkdownPdf(toc_level=2)
    pdf.add_section(Section(markdown_content, toc=False))
    pdf.meta["title"] = title
    pdf.meta["author"] = "SEM Master"
    pdf.save(str(out))

    logger.info("PDF report generated: %s", out)
    return str(out)
