"""SpyFu API client for competitor keyword and ad intelligence."""

from __future__ import annotations

import logging

import httpx

from src.utils.config import get_settings

logger = logging.getLogger(__name__)

SPYFU_API_BASE = "https://www.spyfu.com/apis/"


class SpyFuClient:
    """Client for SpyFu competitive intelligence API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = getattr(settings, "spyfu_api_key", None)
        self._base_url = SPYFU_API_BASE

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": "SEMMaster/1.0",
        }

    def _params(self, extra: dict | None = None) -> dict:
        params: dict = {}
        if self.api_key:
            params["api_key"] = self.api_key
        if extra:
            params.update(extra)
        return params

    async def get_competitor_keywords(self, domain: str) -> list[dict]:
        """Get top paid keywords for a domain.

        Returns list of dicts with: keyword, position, cpc, monthly_searches, ad_spend.
        """
        url = f"{self._base_url}url_api/paid_keywords"
        params = self._params({
            "q": domain,
            "r": "50",
            "sc": "se",
        })

        try:
            async with httpx.AsyncClient(headers=self._headers(), timeout=20) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", data) if isinstance(data, dict) else data:
                if isinstance(item, dict):
                    results.append({
                        "keyword": item.get("term", item.get("keyword", "")),
                        "position": item.get("rank", item.get("position")),
                        "cpc": item.get("costPerClick", item.get("cpc")),
                        "monthly_searches": item.get("searchVolume", item.get("monthly_searches")),
                        "ad_spend": item.get("adSpend", item.get("ad_spend")),
                    })
            return results

        except httpx.HTTPError as exc:
            logger.error("SpyFu API error for %s: %s", domain, exc)
            return []
        except Exception as exc:
            logger.error("SpyFu error for %s: %s", domain, exc)
            return []

    async def get_ad_history(self, domain: str) -> list[dict]:
        """Get historical ad copy for a domain.

        Returns list of dicts with: keyword, ad_title, ad_description, first_seen, last_seen.
        """
        url = f"{self._base_url}url_api/ad_history"
        params = self._params({
            "q": domain,
            "r": "50",
            "sc": "se",
        })

        try:
            async with httpx.AsyncClient(headers=self._headers(), timeout=20) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", data) if isinstance(data, dict) else data:
                if isinstance(item, dict):
                    results.append({
                        "keyword": item.get("term", item.get("keyword", "")),
                        "ad_title": item.get("title", item.get("ad_title", "")),
                        "ad_description": item.get("description", item.get("ad_description", "")),
                        "first_seen": item.get("firstSeen", item.get("first_seen", "")),
                        "last_seen": item.get("lastSeen", item.get("last_seen", "")),
                    })
            return results

        except httpx.HTTPError as exc:
            logger.error("SpyFu ad history error for %s: %s", domain, exc)
            return []
        except Exception as exc:
            logger.error("SpyFu ad history error for %s: %s", domain, exc)
            return []

    async def get_domain_stats(self, domain: str) -> dict:
        """Get domain-level stats: monthly spend estimate, keyword count, etc.

        Returns dict with: monthly_budget, paid_keywords_count, organic_keywords_count,
        paid_clicks, organic_clicks.
        """
        url = f"{self._base_url}url_api/domain_stats_us"
        params = self._params({
            "q": domain,
            "sc": "se",
        })

        try:
            async with httpx.AsyncClient(headers=self._headers(), timeout=20) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if isinstance(data, dict):
                return {
                    "monthly_budget": data.get("monthlyBudget", data.get("monthly_budget")),
                    "paid_keywords_count": data.get("paidKeywordsCount", data.get("paid_keywords_count")),
                    "organic_keywords_count": data.get("organicKeywordsCount", data.get("organic_keywords_count")),
                    "paid_clicks": data.get("paidClicks", data.get("paid_clicks")),
                    "organic_clicks": data.get("organicClicks", data.get("organic_clicks")),
                }
            return {}

        except httpx.HTTPError as exc:
            logger.error("SpyFu domain stats error for %s: %s", domain, exc)
            return {}
        except Exception as exc:
            logger.error("SpyFu domain stats error for %s: %s", domain, exc)
            return {}
