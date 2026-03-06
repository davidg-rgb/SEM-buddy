"""ValueSERP API client for SERP data, ads, and related questions."""

from __future__ import annotations

import logging

import httpx

from src.utils.config import get_settings

logger = logging.getLogger(__name__)

VALUESERP_API_BASE = "https://api.valueserp.com/search"


class ValueSerpClient:
    """Client for ValueSERP search API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.serp_api_key

    def _params(self, extra: dict | None = None) -> dict:
        params: dict = {}
        if self.api_key:
            params["api_key"] = self.api_key
        if extra:
            params.update(extra)
        return params

    async def search(
        self,
        query: str,
        location: str = "Sweden",
        language: str = "sv",
        num: int = 10,
    ) -> dict:
        """Run a search query and return full SERP data.

        Returns the raw API response dict including organic_results, ads,
        related_questions, etc.
        """
        params = self._params({
            "q": query,
            "location": location,
            "hl": language,
            "gl": "se",
            "num": str(num),
        })

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(VALUESERP_API_BASE, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.error("ValueSERP search error for '%s': %s", query, exc)
            return {}
        except Exception as exc:
            logger.error("ValueSERP error for '%s': %s", query, exc)
            return {}

    async def get_ads(
        self,
        query: str,
        location: str = "Sweden",
        language: str = "sv",
    ) -> list[dict]:
        """Get currently running ads for a search query.

        Returns list of dicts with: position, title, link, description, displayed_link.
        """
        data = await self.search(query, location, language)
        ads: list[dict] = []

        for ad in data.get("ads", []):
            ads.append({
                "position": ad.get("position"),
                "title": ad.get("title", ""),
                "link": ad.get("link", ""),
                "description": ad.get("description", ""),
                "displayed_link": ad.get("displayed_link", ""),
            })

        return ads

    async def get_related_questions(
        self,
        query: str,
        location: str = "Sweden",
        language: str = "sv",
    ) -> list[str]:
        """Get People Also Ask questions for a query.

        Returns list of question strings.
        """
        data = await self.search(query, location, language)
        questions: list[str] = []

        for item in data.get("related_questions", []):
            question = item.get("question", "")
            if question:
                questions.append(question)

        return questions
