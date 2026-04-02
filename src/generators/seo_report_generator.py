"""Swedish SEO analysis report generator — Markdown, PDF, and XLSX."""

from __future__ import annotations

import logging
from datetime import date

from src.models.seo import (
    IssueSeverity,
    LighthouseResult,
    PageSeoData,
    SeoAnalysisResult,
    SeoCompetitorAnalysis,
    SeoIssue,
    SeoScorecard,
)

logger = logging.getLogger(__name__)


def generate_seo_report(result: SeoAnalysisResult) -> str:
    """Generate a complete markdown SEO report in Swedish."""
    sections = [
        f"# SEO-analys — {_domain_from_result(result)}\n",
        f"**Datum:** {date.today().isoformat()}\n",
        f"**Läge:** {'Hela webbplatsen' if result.mode == 'site' else 'Enskild sida'}\n",
        "---\n",
        _summary_section(result),
        "---\n",
        _scorecard_section(result.scorecard),
        "---\n",
        _critical_issues_section(result.scorecard.issues),
        "---\n",
        _technical_section(result),
        "---\n",
        _on_page_section(result),
        "---\n",
        _content_section(result),
        "---\n",
        _links_section(result),
        "---\n",
        _schema_section(result),
    ]

    if result.competitor_analysis:
        sections.extend([
            "---\n",
            _competitor_section(result.competitor_analysis),
        ])

    sections.extend([
        "---\n",
        _action_plan_section(result.scorecard.issues),
        "---\n",
        "*Rapport genererad av SEM Master — SEO-analys*\n",
    ])

    report = "\n".join(sections)
    logger.info("Generated SEO report (%d chars)", len(report))
    return report


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _domain_from_result(result: SeoAnalysisResult) -> str:
    if result.site_data:
        return result.site_data.domain
    if result.page_data:
        from urllib.parse import urlparse
        return urlparse(result.page_data.url).netloc
    return "Okänd"


def _summary_section(result: SeoAnalysisResult) -> str:
    sc = result.scorecard
    high = [i for i in sc.issues if i.severity == IssueSeverity.HIGH]
    top_issues = high[:3] if high else sc.issues[:3]

    lines = [
        "## Sammanfattning\n",
        sc.summary_sv,
        "",
    ]

    if top_issues:
        lines.append("**Viktigaste åtgärderna:**\n")
        for i, issue in enumerate(top_issues, 1):
            lines.append(f"{i}. **{issue.title}** — {issue.impact_estimate}")
        lines.append("")

    return "\n".join(lines)


def _scorecard_section(scorecard: SeoScorecard) -> str:
    lines = [
        "## SEO-poäng\n",
        f"**Totalt: {scorecard.overall_score:.0f}/100 ({_grade(scorecard.overall_score)})**\n",
        "| Kategori | Poäng | Betyg | Problem |",
        "|----------|-------|-------|---------|",
    ]

    for cs in scorecard.category_scores:
        grade = _grade(cs.score)
        lines.append(f"| {cs.label} | {cs.score:.0f}/100 | {grade} | {cs.issues_found} |")

    lines.append("")
    return "\n".join(lines)


def _critical_issues_section(issues: list[SeoIssue]) -> str:
    high = [i for i in issues if i.severity == IssueSeverity.HIGH]
    if not high:
        return "## Kritiska problem\n\nInga kritiska problem hittades.\n"

    lines = [
        "## Kritiska problem\n",
        f"**{len(high)} kritisk{'a' if len(high) > 1 else 't'} problem kräver omedelbar åtgärd:**\n",
    ]

    for issue in high:
        urls = ", ".join(issue.affected_urls[:3])
        more = f" (+{len(issue.affected_urls) - 3} till)" if len(issue.affected_urls) > 3 else ""
        lines.extend([
            f"### {issue.title}\n",
            f"**Beskrivning:** {issue.description}\n",
            f"**Berörda sidor:** {urls}{more}\n",
            f"**Åtgärd:** {issue.fix_suggestion}\n",
            f"**Förväntad effekt:** {issue.impact_estimate}\n",
            f"**Insats:** {_effort_label(issue.effort)}\n",
        ])

    return "\n".join(lines)


def _technical_section(result: SeoAnalysisResult) -> str:
    lines = ["## Teknisk SEO\n"]

    # Lighthouse scores
    lh = result.lighthouse
    if lh and lh.performance_score is not None:
        lines.extend([
            "### Lighthouse-poäng\n",
            "| Mått | Poäng |",
            "|------|-------|",
            f"| Prestanda | {lh.performance_score:.0f}/100 |",
            f"| Tillgänglighet | {lh.accessibility_score:.0f}/100 |" if lh.accessibility_score else "",
            f"| Bästa praxis | {lh.best_practices_score:.0f}/100 |" if lh.best_practices_score else "",
            f"| SEO | {lh.seo_score:.0f}/100 |" if lh.seo_score else "",
            "",
        ])

        cwv = lh.core_web_vitals
        if cwv.lcp_ms is not None or cwv.cls is not None:
            lines.extend([
                "### Core Web Vitals\n",
                "| Mått | Värde | Gräns | Status |",
                "|------|-------|-------|--------|",
            ])
            if cwv.lcp_ms is not None:
                status = "✓" if cwv.lcp_ms <= 2500 else "✗"
                lines.append(f"| LCP | {cwv.lcp_ms:.0f}ms | ≤2500ms | {status} |")
            if cwv.cls is not None:
                status = "✓" if cwv.cls <= 0.1 else "✗"
                lines.append(f"| CLS | {cwv.cls:.3f} | ≤0.1 | {status} |")
            if cwv.tbt_ms is not None:
                status = "✓" if cwv.tbt_ms <= 200 else "✗"
                lines.append(f"| TBT | {cwv.tbt_ms:.0f}ms | ≤200ms | {status} |")
            if cwv.fcp_ms is not None:
                lines.append(f"| FCP | {cwv.fcp_ms:.0f}ms | — | — |")
            if cwv.ttfb_ms is not None:
                status = "✓" if cwv.ttfb_ms <= 800 else "✗"
                lines.append(f"| TTFB | {cwv.ttfb_ms:.0f}ms | ≤800ms | {status} |")
            lines.append("")
    else:
        lines.append("*Lighthouse-analys ej tillgänglig. Installera Lighthouse CLI för prestandadata: `npm install -g lighthouse`*\n")

    # robots.txt / sitemap (site mode)
    if result.site_data:
        rt = result.site_data.robots_txt
        lines.append("### robots.txt\n")
        if rt.exists:
            lines.append(f"- **Status:** Finns")
            lines.append(f"- **Tillåter crawlning:** {'Ja' if rt.allows_crawling else 'Nej'}")
            lines.append(f"- **Sitemaps i robots.txt:** {len(rt.sitemap_urls)}")
        else:
            lines.append("- **Status:** Saknas")
        lines.append("")

        lines.append("### Sitemap\n")
        if result.site_data.sitemaps:
            for sm in result.site_data.sitemaps:
                if sm.exists:
                    lines.append(f"- **{sm.url}** — {sm.page_count} URL:er")
        else:
            lines.append("- Ingen sitemap hittad")
        lines.append("")

    return "\n".join(lines)


def _on_page_section(result: SeoAnalysisResult) -> str:
    lines = ["## On-page SEO\n"]

    pages = _get_pages(result)
    if not pages:
        lines.append("Ingen siddata tillgänglig.\n")
        return "\n".join(lines)

    lines.extend([
        "| Sida | Title | Längd | Meta-beskr. | H1 | Canonical |",
        "|------|-------|-------|-------------|----|-----------|\n",
    ])

    for p in pages[:20]:
        title_status = f"{p.title_length}t" if p.title else "Saknas"
        meta_status = f"{p.meta_description_length}t" if p.meta_description else "Saknas"
        h1_status = "✓" if p.h1_count == 1 else f"{p.h1_count} st" if p.h1_count > 1 else "Saknas"
        canonical = "✓" if p.canonical_url else "Saknas"
        short_url = p.url.replace("https://", "").replace("http://", "")[:40]
        lines.append(f"| {short_url} | {title_status} | {p.title_length} | {meta_status} | {h1_status} | {canonical} |")

    lines.append("")
    return "\n".join(lines)


def _content_section(result: SeoAnalysisResult) -> str:
    lines = ["## Innehållsanalys\n"]

    pages = _get_pages(result)
    if not pages:
        lines.append("Ingen siddata tillgänglig.\n")
        return "\n".join(lines)

    lines.extend([
        "| Sida | Ordantal | Bilder | Alt-text |",
        "|------|----------|--------|----------|",
    ])

    for p in pages[:20]:
        img_count = len(p.images)
        alt_ok = img_count - p.images_without_alt
        alt_status = f"{alt_ok}/{img_count}" if img_count else "—"
        wc_status = f"{p.word_count}"
        if p.word_count < 100:
            wc_status += " ⚠️"
        short_url = p.url.replace("https://", "").replace("http://", "")[:40]
        lines.append(f"| {short_url} | {wc_status} | {img_count} | {alt_status} |")

    lines.append("")

    # Thin pages
    thin = [p for p in pages if p.word_count < 300]
    if thin:
        lines.append(f"**Tunna sidor ({len(thin)} st):** Sidor med under 300 ord behöver mer innehåll.\n")

    return "\n".join(lines)


def _links_section(result: SeoAnalysisResult) -> str:
    lines = ["## Länkstruktur\n"]

    pages = _get_pages(result)
    if not pages:
        lines.append("Ingen siddata tillgänglig.\n")
        return "\n".join(lines)

    total_internal = sum(len(p.internal_links) for p in pages)
    total_external = sum(len(p.external_links) for p in pages)

    lines.extend([
        f"- **Totalt interna länkar:** {total_internal}",
        f"- **Totalt externa länkar:** {total_external}",
        f"- **Sidor analyserade:** {len(pages)}",
    ])

    if result.site_data and result.site_data.orphan_pages:
        lines.append(f"- **Föräldralösa sidor:** {len(result.site_data.orphan_pages)}")
        for orphan in result.site_data.orphan_pages[:5]:
            lines.append(f"  - {orphan}")

    lines.append("")
    return "\n".join(lines)


def _schema_section(result: SeoAnalysisResult) -> str:
    lines = ["## Schema & Strukturerad data\n"]

    pages = _get_pages(result)
    pages_with_schema = [p for p in pages if p.schema_markup]

    if not pages_with_schema:
        lines.extend([
            "Ingen strukturerad data (JSON-LD) hittades på webbplatsen.\n",
            "**Rekommendation:** Lägg till relevant JSON-LD schema för att möjliggöra rich snippets i sökresultaten.\n",
            "Vanliga schema-typer:",
            "- **LocalBusiness** — för lokala företag (namn, adress, telefon, öppettider)",
            "- **Product** — för produktsidor",
            "- **FAQPage** — för FAQ-sidor",
            "- **Service** — för tjänstebeskrivningar",
            "",
        ])
    else:
        lines.append(f"{len(pages_with_schema)} av {len(pages)} sidor har strukturerad data:\n")
        for p in pages_with_schema:
            types = ", ".join(s.schema_type for s in p.schema_markup)
            short_url = p.url.replace("https://", "").replace("http://", "")[:40]
            lines.append(f"- **{short_url}** — {types}")
        lines.append("")

    return "\n".join(lines)


def _competitor_section(analysis: SeoCompetitorAnalysis) -> str:
    lines = ["## Konkurrentjämförelse\n"]

    if not analysis.competitors:
        lines.append("Inga konkurrenter analyserades.\n")
        return "\n".join(lines)

    # Score comparison table
    lines.extend([
        "### Poängjämförelse\n",
        "| Domän | Total | On-page | Teknisk | Innehåll | Länkar | Schema |",
        "|-------|-------|---------|---------|----------|--------|--------|",
    ])

    # Client row
    csc = analysis.client_scorecard
    cat_scores = {cs.category.value: cs.score for cs in csc.category_scores}
    lines.append(
        f"| **{_short_domain(analysis.client_url)}** (du) | **{csc.overall_score:.0f}** | "
        f"{cat_scores.get('on_page', 0):.0f} | {cat_scores.get('technical', 0):.0f} | "
        f"{cat_scores.get('content', 0):.0f} | {cat_scores.get('links', 0):.0f} | "
        f"{cat_scores.get('schema', 0):.0f} |"
    )

    # Competitor rows
    for comp in analysis.competitors:
        ccs = {cs.category.value: cs.score for cs in comp.scorecard.category_scores}
        lines.append(
            f"| {comp.domain} | {comp.scorecard.overall_score:.0f} | "
            f"{ccs.get('on_page', 0):.0f} | {ccs.get('technical', 0):.0f} | "
            f"{ccs.get('content', 0):.0f} | {ccs.get('links', 0):.0f} | "
            f"{ccs.get('schema', 0):.0f} |"
        )

    lines.append("")

    # Gaps
    if analysis.gaps:
        lines.extend([
            "### Förbättringsområden (gap mot konkurrenter)\n",
            "| Område | Ditt värde | Konkurrentens värde | Konkurrent | Rekommendation |",
            "|--------|-----------|--------------------|-----------:|----------------|",
        ])
        for gap in analysis.gaps:
            lines.append(
                f"| {gap.area} | {gap.client_value} | {gap.competitor_value} | "
                f"{gap.competitor_domain} | {gap.recommendation} |"
            )
        lines.append("")

    # Advantages
    if analysis.advantages:
        lines.append("### Dina styrkor\n")
        for adv in analysis.advantages:
            lines.append(f"- {adv}")
        lines.append("")

    return "\n".join(lines)


def _action_plan_section(issues: list[SeoIssue]) -> str:
    lines = ["## Handlingsplan\n"]

    if not issues:
        lines.append("Inga åtgärder behövs — utmärkt SEO!\n")
        return "\n".join(lines)

    lines.append("Prioriterad lista sorterad efter effekt/insats-kvot (snabba vinster först):\n")

    # Sort: high impact + low effort first
    priority_key = {
        ("high", "low"): 0,
        ("high", "medium"): 1,
        ("medium", "low"): 2,
        ("high", "high"): 3,
        ("medium", "medium"): 4,
        ("low", "low"): 5,
        ("medium", "high"): 6,
        ("low", "medium"): 7,
        ("low", "high"): 8,
    }

    sorted_issues = sorted(
        issues,
        key=lambda i: priority_key.get((i.severity.value, i.effort), 9),
    )

    # Group by priority tier
    quick_wins = [i for i in sorted_issues if i.effort == "low" and i.severity.value in ("high", "medium")]
    high_impact = [i for i in sorted_issues if i not in quick_wins and i.severity == IssueSeverity.HIGH]
    medium_priority = [i for i in sorted_issues if i not in quick_wins and i not in high_impact and i.severity == IssueSeverity.MEDIUM]
    low_priority = [i for i in sorted_issues if i.severity == IssueSeverity.LOW]

    if quick_wins:
        lines.append("### Snabba vinster (hög effekt, låg insats)\n")
        for issue in quick_wins:
            lines.append(f"- [ ] **{issue.title}** — {issue.fix_suggestion} _{issue.impact_estimate}_")
        lines.append("")

    if high_impact:
        lines.append("### Hög prioritet\n")
        for issue in high_impact:
            lines.append(f"- [ ] **{issue.title}** — {issue.fix_suggestion} _{issue.impact_estimate}_ (Insats: {_effort_label(issue.effort)})")
        lines.append("")

    if medium_priority:
        lines.append("### Medium prioritet\n")
        for issue in medium_priority:
            lines.append(f"- [ ] **{issue.title}** — {issue.fix_suggestion} _{issue.impact_estimate}_")
        lines.append("")

    if low_priority:
        lines.append("### Låg prioritet\n")
        for issue in low_priority:
            lines.append(f"- [ ] {issue.title} — {issue.fix_suggestion}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------


def export_seo_pdf(result: SeoAnalysisResult, output_path: str) -> str:
    """Export SEO report as PDF."""
    from src.generators.pdf_generator import generate_pdf_report

    markdown_content = generate_seo_report(result)
    domain = _domain_from_result(result)
    title = f"SEO-analys — {domain}"
    return generate_pdf_report(markdown_content, output_path, title=title)


def export_seo_xlsx(result: SeoAnalysisResult, output_path: str) -> str:
    """Export SEO data to multi-sheet XLSX."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    from pathlib import Path

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    def _write_headers(ws, headers):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill

    # Sheet 1: Översikt
    ws = wb.create_sheet("Översikt")
    _write_headers(ws, ["Kategori", "Poäng", "Betyg", "Problem"])
    for row_idx, cs in enumerate(result.scorecard.category_scores, 2):
        ws.cell(row=row_idx, column=1, value=cs.label)
        ws.cell(row=row_idx, column=2, value=round(cs.score, 1))
        ws.cell(row=row_idx, column=3, value=_grade(cs.score))
        ws.cell(row=row_idx, column=4, value=cs.issues_found)
    total_row = len(result.scorecard.category_scores) + 2
    ws.cell(row=total_row, column=1, value="TOTALT")
    ws.cell(row=total_row, column=2, value=round(result.scorecard.overall_score, 1))
    ws.cell(row=total_row, column=3, value=_grade(result.scorecard.overall_score))
    ws.cell(row=total_row, column=1).font = Font(bold=True)

    # Sheet 2: Problem
    ws = wb.create_sheet("Problem")
    _write_headers(ws, ["Allvarlighet", "Kategori", "Problem", "Beskrivning", "Åtgärd", "Effekt", "Insats", "Berörda sidor"])
    for row_idx, issue in enumerate(result.scorecard.issues, 2):
        ws.cell(row=row_idx, column=1, value=issue.severity.value)
        ws.cell(row=row_idx, column=2, value=issue.category.value)
        ws.cell(row=row_idx, column=3, value=issue.title)
        ws.cell(row=row_idx, column=4, value=issue.description)
        ws.cell(row=row_idx, column=5, value=issue.fix_suggestion)
        ws.cell(row=row_idx, column=6, value=issue.impact_estimate)
        ws.cell(row=row_idx, column=7, value=_effort_label(issue.effort))
        ws.cell(row=row_idx, column=8, value=", ".join(issue.affected_urls[:5]))

    # Sheet 3: Sidor
    pages = _get_pages(result)
    ws = wb.create_sheet("Sidor")
    _write_headers(ws, ["URL", "Title", "Title-längd", "Meta-beskr.", "Meta-längd", "H1", "Ordantal", "Bilder", "Alt saknas", "Interna länkar", "Schema"])
    for row_idx, p in enumerate(pages, 2):
        ws.cell(row=row_idx, column=1, value=p.url)
        ws.cell(row=row_idx, column=2, value=p.title)
        ws.cell(row=row_idx, column=3, value=p.title_length)
        ws.cell(row=row_idx, column=4, value=p.meta_description[:80] if p.meta_description else "")
        ws.cell(row=row_idx, column=5, value=p.meta_description_length)
        ws.cell(row=row_idx, column=6, value=p.h1)
        ws.cell(row=row_idx, column=7, value=p.word_count)
        ws.cell(row=row_idx, column=8, value=len(p.images))
        ws.cell(row=row_idx, column=9, value=p.images_without_alt)
        ws.cell(row=row_idx, column=10, value=len(p.internal_links))
        ws.cell(row=row_idx, column=11, value=", ".join(s.schema_type for s in p.schema_markup) or "—")

    # Sheet 4: Konkurrenter (if available)
    if result.competitor_analysis and result.competitor_analysis.competitors:
        ws = wb.create_sheet("Konkurrenter")
        _write_headers(ws, ["Domän", "Total poäng", "On-page", "Teknisk", "Innehåll", "Länkar", "Schema"])
        ca = result.competitor_analysis
        # Client row
        csc = {cs.category.value: cs.score for cs in ca.client_scorecard.category_scores}
        ws.cell(row=2, column=1, value=f"{_short_domain(ca.client_url)} (du)")
        ws.cell(row=2, column=2, value=round(ca.client_scorecard.overall_score, 1))
        ws.cell(row=2, column=3, value=round(csc.get("on_page", 0), 1))
        ws.cell(row=2, column=4, value=round(csc.get("technical", 0), 1))
        ws.cell(row=2, column=5, value=round(csc.get("content", 0), 1))
        ws.cell(row=2, column=6, value=round(csc.get("links", 0), 1))
        ws.cell(row=2, column=7, value=round(csc.get("schema", 0), 1))
        for row_idx, comp in enumerate(ca.competitors, 3):
            ccs = {cs.category.value: cs.score for cs in comp.scorecard.category_scores}
            ws.cell(row=row_idx, column=1, value=comp.domain)
            ws.cell(row=row_idx, column=2, value=round(comp.scorecard.overall_score, 1))
            ws.cell(row=row_idx, column=3, value=round(ccs.get("on_page", 0), 1))
            ws.cell(row=row_idx, column=4, value=round(ccs.get("technical", 0), 1))
            ws.cell(row=row_idx, column=5, value=round(ccs.get("content", 0), 1))
            ws.cell(row=row_idx, column=6, value=round(ccs.get("links", 0), 1))
            ws.cell(row=row_idx, column=7, value=round(ccs.get("schema", 0), 1))

    # Auto-width all sheets
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    logger.info("Exported SEO data to %s", out)
    return str(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pages(result: SeoAnalysisResult) -> list[PageSeoData]:
    if result.site_data and result.site_data.pages:
        return result.site_data.pages
    if result.page_data:
        return [result.page_data]
    return []


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    elif score >= 50:
        return "E"
    return "F"


def _effort_label(effort: str) -> str:
    return {"low": "Låg", "medium": "Medel", "high": "Hög"}.get(effort, effort)


def _short_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc or url
