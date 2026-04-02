"""Tests for SEO report generation."""

from datetime import datetime

import pytest

from src.analysis.seo_analyzer import analyze_page_seo, analyze_site_seo
from src.generators.seo_report_generator import generate_seo_report, export_seo_xlsx
from src.models.seo import SeoAnalysisResult, SeoScorecard
from src.scrapers.seo_scraper import generate_synthetic_page_data, generate_synthetic_site_data
from src.analysis.seo_competitor import generate_synthetic_competitor_data


class TestMarkdownReport:
    def _make_single_result(self) -> SeoAnalysisResult:
        page = generate_synthetic_page_data("https://example.se")
        scorecard = analyze_page_seo(page)
        return SeoAnalysisResult(
            mode="single",
            analyzed_at=datetime.now(),
            page_data=page,
            scorecard=scorecard,
        )

    def _make_site_result(self) -> SeoAnalysisResult:
        site = generate_synthetic_site_data("https://example.se")
        scorecard = analyze_site_seo(site)
        return SeoAnalysisResult(
            mode="site",
            analyzed_at=datetime.now(),
            site_data=site,
            scorecard=scorecard,
        )

    def test_single_page_report(self):
        result = self._make_single_result()
        report = generate_seo_report(result)
        assert len(report) > 500
        assert "Sammanfattning" in report
        assert "SEO-poäng" in report
        assert "Handlingsplan" in report

    def test_site_report(self):
        result = self._make_site_result()
        report = generate_seo_report(result)
        assert "Sammanfattning" in report
        assert "Hela webbplatsen" in report

    def test_report_contains_all_sections(self):
        result = self._make_single_result()
        report = generate_seo_report(result)
        expected_sections = [
            "Sammanfattning",
            "SEO-poäng",
            "Kritiska problem",
            "Teknisk SEO",
            "On-page SEO",
            "Innehållsanalys",
            "Länkstruktur",
            "Schema",
            "Handlingsplan",
        ]
        for section in expected_sections:
            assert section in report, f"Missing section: {section}"

    def test_report_contains_scorecard_table(self):
        result = self._make_single_result()
        report = generate_seo_report(result)
        assert "| Kategori | Poäng | Betyg | Problem |" in report

    def test_report_with_competitors(self):
        result = self._make_single_result()
        comp_analysis = generate_synthetic_competitor_data(
            ["https://rival.se"], result.scorecard
        )
        result.competitor_analysis = comp_analysis
        report = generate_seo_report(result)
        assert "Konkurrentjämförelse" in report
        assert "rival.se" in report

    def test_report_without_competitors(self):
        result = self._make_single_result()
        report = generate_seo_report(result)
        assert "Konkurrentjämförelse" not in report

    def test_action_plan_sorted(self):
        result = self._make_single_result()
        report = generate_seo_report(result)
        assert "Handlingsplan" in report
        # Should have at least one checklist item
        assert "- [ ]" in report

    def test_report_has_swedish_content(self):
        result = self._make_single_result()
        report = generate_seo_report(result)
        # Check for Swedish words
        swedish_words = ["poäng", "problem", "åtgärd", "sida"]
        found = sum(1 for w in swedish_words if w.lower() in report.lower())
        assert found >= 2


class TestXlsxExport:
    def test_export_creates_file(self, tmp_path):
        page = generate_synthetic_page_data("https://example.se")
        scorecard = analyze_page_seo(page)
        result = SeoAnalysisResult(
            mode="single",
            analyzed_at=datetime.now(),
            page_data=page,
            scorecard=scorecard,
        )
        output_path = str(tmp_path / "test.xlsx")
        path = export_seo_xlsx(result, output_path)
        assert path == output_path
        assert (tmp_path / "test.xlsx").exists()

    def test_export_has_correct_sheets(self, tmp_path):
        import openpyxl

        page = generate_synthetic_page_data("https://example.se")
        scorecard = analyze_page_seo(page)
        result = SeoAnalysisResult(
            mode="single",
            analyzed_at=datetime.now(),
            page_data=page,
            scorecard=scorecard,
        )
        output_path = str(tmp_path / "test.xlsx")
        export_seo_xlsx(result, output_path)

        wb = openpyxl.load_workbook(output_path)
        sheet_names = wb.sheetnames
        assert "Översikt" in sheet_names
        assert "Problem" in sheet_names
        assert "Sidor" in sheet_names

    def test_export_with_competitors(self, tmp_path):
        import openpyxl

        page = generate_synthetic_page_data("https://example.se")
        scorecard = analyze_page_seo(page)
        comp = generate_synthetic_competitor_data(["https://rival.se"], scorecard)
        result = SeoAnalysisResult(
            mode="single",
            analyzed_at=datetime.now(),
            page_data=page,
            scorecard=scorecard,
            competitor_analysis=comp,
        )
        output_path = str(tmp_path / "test.xlsx")
        export_seo_xlsx(result, output_path)

        wb = openpyxl.load_workbook(output_path)
        assert "Konkurrenter" in wb.sheetnames
