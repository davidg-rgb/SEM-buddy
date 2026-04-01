"""Tests for src/templates/manager.py — Template CRUD and client data stripping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.campaign import CampaignPlan
from src.models.client import ClientProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_templates_dir(tmp_path, monkeypatch):
    """Redirect TEMPLATES_DIR to a temp directory for every test."""
    templates_dir = tmp_path / "templates"
    monkeypatch.setattr("src.templates.manager.TEMPLATES_DIR", templates_dir)
    return templates_dir


# ---------------------------------------------------------------------------
# save_template
# ---------------------------------------------------------------------------


def test_save_template(sample_campaign_plan: CampaignPlan, sample_client: ClientProfile, tmp_path):
    """save_template returns a path that exists and the file contains the template name."""
    import src.templates.manager as mgr

    path = mgr.save_template("test-tmpl", sample_campaign_plan, sample_client, description="Test")

    assert isinstance(path, Path)
    assert path.exists()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == "test-tmpl"
    assert data["source_client"] == sample_client.business_name


def test_save_template_strips_client_data(
    sample_campaign_plan: CampaignPlan, sample_client: ClientProfile
):
    """Saved template replaces business name with {Foretag} and clears geo_targets."""
    import src.templates.manager as mgr

    path = mgr.save_template("strip-test", sample_campaign_plan, sample_client)
    data = json.loads(path.read_text(encoding="utf-8"))

    # geo_targets must be emptied in each campaign
    for campaign in data["campaigns"]:
        assert campaign["geo_targets"] == [], f"geo_targets not cleared: {campaign['geo_targets']}"

    # {Foretag} placeholder must appear somewhere in the serialised text
    raw = path.read_text(encoding="utf-8")
    assert "{Foretag}" in raw, "Expected {Foretag} placeholder in template file"

    # Original business name must NOT appear in campaigns/sitelinks/callouts
    business = sample_client.business_name
    for campaign in data["campaigns"]:
        for ag in campaign.get("ad_groups", []):
            for ad in ag.get("ads", []):
                for hl in ad.get("headlines", []):
                    assert business not in hl.get("text", ""), f"Business name leaked: {hl}"


# ---------------------------------------------------------------------------
# load_template
# ---------------------------------------------------------------------------


def test_load_template(sample_campaign_plan: CampaignPlan, sample_client: ClientProfile):
    """load_template returns a CampaignTemplate with the expected fields."""
    import src.templates.manager as mgr
    from src.templates.manager import CampaignTemplate

    mgr.save_template("load-test", sample_campaign_plan, sample_client, description="Load me")
    tmpl = mgr.load_template("load-test")

    assert isinstance(tmpl, CampaignTemplate)
    assert tmpl.name == "load-test"
    assert tmpl.source_client == sample_client.business_name
    assert len(tmpl.campaigns) == len(sample_campaign_plan.campaigns)


def test_load_template_not_found():
    """load_template raises FileNotFoundError for a nonexistent template name."""
    import src.templates.manager as mgr

    with pytest.raises(FileNotFoundError):
        mgr.load_template("nonexistent-template")


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------


def test_list_templates(sample_campaign_plan: CampaignPlan, sample_client: ClientProfile):
    """list_templates returns a list of dicts for every saved template."""
    import src.templates.manager as mgr

    mgr.save_template("alpha", sample_campaign_plan, sample_client, description="First")
    mgr.save_template("beta", sample_campaign_plan, sample_client, description="Second")

    result = mgr.list_templates()

    assert len(result) == 2
    names = {item["name"] for item in result}
    assert names == {"alpha", "beta"}

    for item in result:
        assert "name" in item
        assert "description" in item
        assert "created_at" in item
        assert "source_client" in item
        assert "source_industry" in item


def test_list_templates_empty_dir(monkeypatch, tmp_path):
    """list_templates returns [] when the templates directory does not exist."""
    import src.templates.manager as mgr

    # Point to a directory that definitely does not exist
    monkeypatch.setattr("src.templates.manager.TEMPLATES_DIR", tmp_path / "no-such-dir")

    result = mgr.list_templates()
    assert result == []


# ---------------------------------------------------------------------------
# delete_template
# ---------------------------------------------------------------------------


def test_delete_template(sample_campaign_plan: CampaignPlan, sample_client: ClientProfile):
    """delete_template removes the file; loading it afterwards raises FileNotFoundError."""
    import src.templates.manager as mgr

    mgr.save_template("del-test", sample_campaign_plan, sample_client)
    mgr.delete_template("del-test")

    assert not (mgr.TEMPLATES_DIR / "del-test.json").exists()

    with pytest.raises(FileNotFoundError):
        mgr.load_template("del-test")


def test_delete_template_not_found():
    """delete_template raises FileNotFoundError when the template does not exist."""
    import src.templates.manager as mgr

    with pytest.raises(FileNotFoundError):
        mgr.delete_template("ghost-template")
