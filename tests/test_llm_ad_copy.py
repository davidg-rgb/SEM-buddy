"""Tests for the claude CLI subprocess wrapper.

Subprocess is mocked end-to-end — these tests do not invoke `claude` for real.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from src.generators import llm_ad_copy
from src.models.client import ClientProfile


def _envelope(payload: dict) -> str:
    """Mimic the JSON envelope `claude -p --output-format json` writes to stdout."""
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(payload),
            "session_id": "test-session",
        }
    )


def _run_ok(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=stdout, stderr="")


def _run_err(returncode: int, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout="", stderr=stderr)


class TestIsEnabled:
    def test_disabled_by_env_var(self, monkeypatch):
        monkeypatch.setenv("SEM_DISABLE_LLM", "1")
        assert llm_ad_copy.is_enabled() is False

    def test_disabled_when_claude_missing(self, monkeypatch):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        with patch.object(llm_ad_copy.shutil, "which", return_value=None):
            assert llm_ad_copy.is_enabled() is False

    def test_enabled_when_claude_present(self, monkeypatch):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"):
            assert llm_ad_copy.is_enabled() is True


class TestGenerateLlmAdCopy:
    def test_happy_path(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        envelope = _envelope(
            {
                "headlines": [
                    "Akut rörmokare i Stockholm",
                    "Boka VVS-hjälp idag",
                    "Snabb service dygnet runt",
                ],
                "descriptions": [
                    "Vi hjälper dig snabbt med akuta VVS-problem. Ring nu för fri offert.",
                    "Erfaren rörmokare i Stockholm. Boka tid online idag.",
                ],
            }
        )
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_ok(envelope)):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(
                sample_client, "rörmokare", ["rörmokare stockholm", "akut vvs"]
            )

        assert heads == [
            "Akut rörmokare i Stockholm",
            "Boka VVS-hjälp idag",
            "Snabb service dygnet runt",
        ]
        assert len(descs) == 2
        assert all(len(d) <= 90 for d in descs)
        assert all(len(h) <= 30 for h in heads)

    def test_drops_oversized_items(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        envelope = _envelope(
            {
                "headlines": [
                    "Bra rubrik",
                    "X" * 35,  # too long, must be dropped
                    "Annan rubrik",
                ],
                "descriptions": [
                    "Y" * 95,  # too long
                    "Kort men giltig beskrivning som passar.",
                ],
            }
        )
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_ok(envelope)):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])

        assert heads == ["Bra rubrik", "Annan rubrik"]
        assert descs == ["Kort men giltig beskrivning som passar."]

    def test_dedupes_repeated_strings(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        envelope = _envelope(
            {
                "headlines": ["Boka idag", "Boka idag", "Ring nu"],
                "descriptions": ["Samma text", "Samma text"],
            }
        )
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_ok(envelope)):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])

        assert heads == ["Boka idag", "Ring nu"]
        assert descs == ["Samma text"]

    def test_returns_empty_when_disabled_via_env(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.setenv("SEM_DISABLE_LLM", "1")
        with patch.object(llm_ad_copy.subprocess, "run") as mocked_run:
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert heads == []
        assert descs == []
        mocked_run.assert_not_called()

    def test_returns_empty_when_claude_missing(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        with patch.object(llm_ad_copy.shutil, "which", return_value=None), \
             patch.object(llm_ad_copy.subprocess, "run") as mocked_run:
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert (heads, descs) == ([], [])
        mocked_run.assert_not_called()

    def test_returns_empty_on_nonzero_exit(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_err(1, "boom")):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert (heads, descs) == ([], [])

    def test_returns_empty_on_timeout(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(
                 llm_ad_copy.subprocess,
                 "run",
                 side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
             ):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert (heads, descs) == ([], [])

    def test_returns_empty_on_envelope_error_flag(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        err_envelope = json.dumps(
            {"type": "result", "is_error": True, "result": "model refused"}
        )
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_ok(err_envelope)):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert (heads, descs) == ([], [])

    def test_returns_empty_on_malformed_envelope(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_ok("not json at all")):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert (heads, descs) == ([], [])

    def test_returns_empty_on_malformed_inner_payload(self, monkeypatch, sample_client: ClientProfile):
        monkeypatch.delenv("SEM_DISABLE_LLM", raising=False)
        bad = json.dumps(
            {
                "type": "result",
                "is_error": False,
                "result": "headlines: not actually json",
            }
        )
        with patch.object(llm_ad_copy.shutil, "which", return_value="/usr/bin/claude"), \
             patch.object(llm_ad_copy.subprocess, "run", return_value=_run_ok(bad)):
            heads, descs = llm_ad_copy.generate_llm_ad_copy(sample_client, "rörmokare", [])
        assert (heads, descs) == ([], [])


class TestPromptBuilding:
    def test_prompt_includes_business_and_theme(self, sample_client: ClientProfile):
        prompt = llm_ad_copy._build_prompt(sample_client, "akut rörmokare", ["jour vvs"])
        assert "Stockholms Rörmokare" in prompt
        assert "akut rörmokare" in prompt
        assert "jour vvs" in prompt
        assert "du" in prompt.lower()
        assert "max 30" in prompt
        assert "max 90" in prompt

    def test_prompt_with_target_geo_focuses_on_single_location(self, sample_client: ClientProfile):
        from src.models.client import GeoTarget

        # Drop "Stockholm" from the business name so we can check for geo leakage
        # in the actual ORT/ORTER lines, not in the FÖRETAG header.
        client = sample_client.model_copy(update={
            "business_name": "Rörmokare Sverige AB",
            "geographic_targets": [GeoTarget(name="Stockholm")],
        })
        target = GeoTarget(name="Malmö")
        prompt = llm_ad_copy._build_prompt(
            client, "rörmokare", ["jour vvs"], target_geo=target,
        )
        # The prompt switches to ORT (singular) and names Malmö
        assert "ORT: Malmö" in prompt
        # Adds the constraint that ads only run in this location
        assert "endast i detta område" in prompt
        # Does NOT use the plural ORTER form
        assert "ORTER:" not in prompt
        # Client's default Stockholm should not appear anywhere
        assert "Stockholm" not in prompt

    def test_prompt_without_target_geo_lists_client_cities(self, sample_client: ClientProfile):
        prompt = llm_ad_copy._build_prompt(sample_client, "rörmokare", ["jour vvs"])
        assert "ORTER:" in prompt
        assert "Stockholm" in prompt
