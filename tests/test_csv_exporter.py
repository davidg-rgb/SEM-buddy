"""Tests for CSV export -- file count, columns, encoding, Swedish chars."""

from pathlib import Path

from src.generators.csv_exporter import export_campaign_plan
from src.models.campaign import CampaignPlan


class TestCSVExport:
    def test_produces_expected_files(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        out = Path(tmp_output_dir)

        expected = [
            "01_campaigns.csv",
            "02_ad_groups.csv",
            "03_keywords.csv",
            "04_responsive_search_ads.csv",
            "05_negative_keywords.csv",
            "06_sitelinks.csv",
            "07_callouts.csv",
            "README_import_order.txt",
        ]
        for fname in expected:
            assert (out / fname).exists(), f"Missing file: {fname}"

    def test_campaign_csv_columns(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        header = self._read_header(tmp_output_dir, "01_campaigns.csv")
        assert "Campaign" in header
        assert "Campaign Type" in header
        assert "Row Type" not in header

    def test_campaign_csv_preserves_radius(self, tmp_output_dir: str):
        """radius_km on GeoTarget must surface as a 'Location radius (km)' column."""
        from src.models.campaign import (
            Campaign, AdGroup, Keyword, ResponsiveSearchAd, AdHeadline, AdDescription, CampaignPlan,
        )
        from src.models.client import GeoTarget

        plan = CampaignPlan(
            campaigns=[
                Campaign(
                    name="Etraveli - Stockholm",
                    budget_sek_daily=100.0,
                    geo_targets=[GeoTarget(name="Stockholm", radius_km=50.0)],
                    ad_groups=[
                        AdGroup(
                            name="ag",
                            theme="flights",
                            keywords=[Keyword(text="billiga flyg")],
                            ads=[
                                ResponsiveSearchAd(
                                    headlines=[AdHeadline(text=f"h{i}") for i in range(3)],
                                    descriptions=[AdDescription(text=f"description {i}") for i in range(2)],
                                    final_url="https://etraveli.com",
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        export_campaign_plan(plan, tmp_output_dir)
        body = (Path(tmp_output_dir) / "01_campaigns.csv").read_text(encoding="utf-8-sig")
        assert "Location radius (km)" in body
        assert "Stockholm=50.0km" in body

    def test_keyword_csv_columns(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        header = self._read_header(tmp_output_dir, "03_keywords.csv")
        for col in ["Campaign", "Ad Group", "Keyword", "Criterion Type"]:
            assert col in header, f"Missing column: {col}"

    def test_sitelink_csv_has_campaign_column(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        header = self._read_header(tmp_output_dir, "06_sitelinks.csv")
        assert "Campaign" in header

    def test_callout_csv_has_campaign_column(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        header = self._read_header(tmp_output_dir, "07_callouts.csv")
        assert "Campaign" in header

    def test_utf8_bom_encoding(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        out = Path(tmp_output_dir)
        for csv_file in out.glob("*.csv"):
            raw = csv_file.read_bytes()
            assert raw[:3] == b"\xef\xbb\xbf", f"{csv_file.name} missing UTF-8 BOM"

    def test_swedish_chars_survive_roundtrip(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        out = Path(tmp_output_dir)
        campaigns_csv = (out / "01_campaigns.csv").read_text(encoding="utf-8-sig")
        assert "Rörmokare" in campaigns_csv

    def test_no_row_type_anywhere(self, sample_campaign_plan: CampaignPlan, tmp_output_dir: str):
        export_campaign_plan(sample_campaign_plan, tmp_output_dir)
        out = Path(tmp_output_dir)
        for csv_file in out.glob("*.csv"):
            content = csv_file.read_text(encoding="utf-8-sig")
            assert "Row Type" not in content, f"'Row Type' found in {csv_file.name}"

    # ---- helpers ----

    @staticmethod
    def _read_header(output_dir: str, filename: str) -> str:
        path = Path(output_dir) / filename
        return path.read_text(encoding="utf-8-sig").splitlines()[0]
