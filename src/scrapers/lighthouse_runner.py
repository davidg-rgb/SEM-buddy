"""Lighthouse CLI subprocess wrapper for Core Web Vitals and performance scores."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

from src.models.seo import CoreWebVitals, LighthouseResult

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 60


def lighthouse_available() -> bool:
    """Check if the Lighthouse CLI is installed and on PATH."""
    return shutil.which("lighthouse") is not None


async def run_lighthouse(
    url: str,
    categories: list[str] | None = None,
) -> LighthouseResult:
    """Execute Lighthouse CLI and parse JSON output."""
    if not lighthouse_available():
        logger.info("Lighthouse CLI not found — skipping performance analysis")
        return LighthouseResult(url=url)

    if categories is None:
        categories = ["performance", "accessibility", "best-practices", "seo"]

    # Create temp file for JSON output
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_path = tmp.name
    tmp.close()

    cat_arg = ",".join(categories)
    cmd = [
        "lighthouse", url,
        f"--output=json",
        f"--output-path={tmp_path}",
        f"--only-categories={cat_arg}",
        "--chrome-flags=--headless --no-sandbox",
        "--quiet",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            logger.warning("Lighthouse timed out after %ds for %s", _TIMEOUT_SECONDS, url)
            return LighthouseResult(url=url)

        if proc.returncode != 0:
            logger.warning(
                "Lighthouse exited with code %d for %s: %s",
                proc.returncode, url, stderr.decode(errors="replace")[:500],
            )
            return LighthouseResult(url=url)

        # Parse JSON output
        output_path = Path(tmp_path)
        if not output_path.exists():
            logger.warning("Lighthouse output file not found")
            return LighthouseResult(url=url)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        return _parse_lighthouse_json(url, data)

    except FileNotFoundError:
        logger.warning("Lighthouse binary not found despite which() check")
        return LighthouseResult(url=url)
    except Exception as exc:
        logger.warning("Lighthouse failed for %s: %s", url, exc)
        return LighthouseResult(url=url)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def _parse_lighthouse_json(url: str, data: dict) -> LighthouseResult:
    """Parse Lighthouse JSON output into LighthouseResult model."""
    categories = data.get("categories", {})
    audits = data.get("audits", {})

    def _cat_score(name: str) -> float | None:
        cat = categories.get(name)
        if cat and cat.get("score") is not None:
            return round(cat["score"] * 100, 1)
        return None

    def _audit_value(audit_id: str) -> float | None:
        audit = audits.get(audit_id, {})
        val = audit.get("numericValue")
        return float(val) if val is not None else None

    cwv = CoreWebVitals(
        lcp_ms=_audit_value("largest-contentful-paint"),
        cls=_audit_value("cumulative-layout-shift"),
        fcp_ms=_audit_value("first-contentful-paint"),
        tbt_ms=_audit_value("total-blocking-time"),
        si_ms=_audit_value("speed-index"),
        ttfb_ms=_audit_value("server-response-time"),
    )

    # Parse opportunities
    opportunities = []
    for audit_id, audit in audits.items():
        details = audit.get("details", {})
        if details.get("type") == "opportunity" and audit.get("score", 1) < 1:
            opportunities.append({
                "title": audit.get("title", ""),
                "description": audit.get("description", ""),
                "savings_ms": details.get("overallSavingsMs", 0),
            })

    return LighthouseResult(
        url=url,
        performance_score=_cat_score("performance"),
        accessibility_score=_cat_score("accessibility"),
        best_practices_score=_cat_score("best-practices"),
        seo_score=_cat_score("seo"),
        core_web_vitals=cwv,
        opportunities=opportunities,
    )
