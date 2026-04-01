"""Tests for report generator -- Swedish content, sections, XLSX export."""

from pathlib import Path

from src.generators.report_generator import (
    generate_strategy_report,
    export_keyword_xlsx,
)
from src.models.campaign import CampaignPlan
from src.models.client import ClientProfile
from src.models.competitor import CompetitorProfile
from src.models.research import DigitalPresence, SiteCrawl, GoogleBusinessProfile


class TestGenerateStrategyReport:
    def _make_report(self, sample_client, sample_campaign_plan):
        digital_presence = DigitalPresence(
            site_crawl=SiteCrawl(total_pages=5, primary_language="sv"),
            google_business=GoogleBusinessProfile(
                name=sample_client.business_name,
                rating=4.5,
                review_count=42,
            ),
        )
        competitors = [
            CompetitorProfile(
                name="Konkurrent AB",
                domain="konkurrent.se",
                top_keywords=["rörmokare", "VVS"],
            ),
        ]
        keyword_data = {
            "groups": {"rörmokare": [{"text": "rörmokare stockholm"}]},
            "negatives": ["jobb", "gratis"],
        }
        return generate_strategy_report(
            sample_client, digital_presence, competitors, sample_campaign_plan, keyword_data,
        )

    def test_report_is_non_empty(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        assert len(report) > 500

    def test_contains_business_name(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        assert sample_client.business_name in report

    def test_has_swedish_section_headers(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        expected_headers = [
            "Sammanfattning",
            "Affärsanalys",
            "Konkurrenslandskap",
            "Sökordsstrategi",
            "Kampanjstruktur",
            "Annonstext",
            "Budget",
            "Implementeringsplan",
        ]
        for header in expected_headers:
            assert header in report, f"Missing section header: '{header}'"

    def test_no_english_section_headers(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        english_headers = ["Executive Summary", "Business Analysis", "Keyword Strategy"]
        for header in english_headers:
            assert header not in report, f"Found English header: '{header}'"

    def test_includes_competitor_data(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        assert "Konkurrent AB" in report

    def test_includes_budget_info(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        assert "SEK" in report

    def test_includes_implementation_phases(self, sample_client, sample_campaign_plan):
        report = self._make_report(sample_client, sample_campaign_plan)
        assert "Fas 1" in report
        assert "Fas 4" in report


class TestExportKeywordXLSX:
    def test_creates_xlsx_file(self, tmp_output_dir):
        keyword_data = {
            "groups": {
                "rörmokare": [
                    {"text": "rörmokare stockholm", "monthly_searches": 1200, "match_type": "PHRASE"},
                ],
            }
        }
        output_path = str(Path(tmp_output_dir) / "keywords.xlsx")
        result = export_keyword_xlsx(keyword_data, output_path)
        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

    def test_creates_sheets_per_group(self, tmp_output_dir):
        import openpyxl

        keyword_data = {
            "groups": {
                "rörmokare": [{"text": "rörmokare"}],
                "vvs_jour": [{"text": "vvs jour"}],
            }
        }
        output_path = str(Path(tmp_output_dir) / "keywords.xlsx")
        export_keyword_xlsx(keyword_data, output_path)
        wb = openpyxl.load_workbook(output_path)
        assert len(wb.sheetnames) == 2

    def test_empty_groups_creates_placeholder(self, tmp_output_dir):
        import openpyxl

        keyword_data = {"groups": {}}
        output_path = str(Path(tmp_output_dir) / "keywords.xlsx")
        export_keyword_xlsx(keyword_data, output_path)
        wb = openpyxl.load_workbook(output_path)
        assert len(wb.sheetnames) >= 1
