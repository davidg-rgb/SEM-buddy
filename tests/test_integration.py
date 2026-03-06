"""Integration smoke test -- build campaigns, export CSV, generate reports."""

from pathlib import Path

from src.models.client import ClientProfile
from src.models.campaign import CampaignPlan
from src.models.research import DigitalPresence, SiteCrawl, GoogleBusinessProfile
from src.models.competitor import CompetitorProfile
from src.generators.campaign_builder import build_campaigns
from src.generators.csv_exporter import export_campaign_plan
from src.generators.report_generator import generate_strategy_report
from src.generators.pdf_generator import generate_pdf_report


class TestIntegrationSmokeTest:
    def test_end_to_end(self, sample_client: ClientProfile, tmp_output_dir: str):
        # 1. Build keyword groups (hardcoded for test)
        keyword_groups = {
            "rörmokare": [
                {"text": "rörmokare stockholm", "monthly_searches": 1200},
                {"text": "rörmokare", "monthly_searches": 3500},
            ],
            "vvs_jour": [
                {"text": "VVS-jour", "monthly_searches": 800},
                {"text": "akut rörmokare", "monthly_searches": 400},
            ],
        }

        # 2. Build campaigns
        plan = build_campaigns(sample_client, keyword_groups)
        assert isinstance(plan, CampaignPlan)
        assert len(plan.campaigns) > 0

        # 3. Verify all headlines <= 30 chars
        for campaign in plan.campaigns:
            for ag in campaign.ad_groups:
                for ad in ag.ads:
                    for h in ad.headlines:
                        assert len(h.text) <= 30, f"Headline too long: '{h.text}' ({len(h.text)})"
                    for d in ad.descriptions:
                        assert len(d.text) <= 90, f"Description too long: '{d.text}' ({len(d.text)})"

        # 4. Export to CSV
        export_campaign_plan(plan, tmp_output_dir)
        out = Path(tmp_output_dir)
        csv_files = list(out.glob("*.csv"))
        assert len(csv_files) > 0, "No CSV files produced"
        for csv_file in csv_files:
            assert csv_file.stat().st_size > 0, f"Empty CSV: {csv_file.name}"

        # 5. Generate markdown report
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
        keyword_data = {"groups": keyword_groups, "negatives": ["jobb", "gratis"]}

        report = generate_strategy_report(
            sample_client, digital_presence, competitors, plan, keyword_data,
        )
        assert len(report) > 100, "Report too short"
        assert sample_client.business_name in report

        # 6. Generate PDF report
        pdf_path = str(out / "test_report.pdf")
        result_path = generate_pdf_report(report, pdf_path)
        pdf_file = Path(result_path)
        assert pdf_file.exists(), "PDF not created"
        assert pdf_file.stat().st_size > 0, "PDF is empty"
