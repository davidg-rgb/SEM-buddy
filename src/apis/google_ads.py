"""Google Ads API client using the official SDK with OAuth authentication.

GoogleAdsService wraps the google-ads SDK to provide keyword research and
campaign data retrieval targeting the Swedish market.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.auth import AuthError
from src.auth.google_ads_auth import get_google_ads_client
from src.apis.errors import GoogleAdsApiError, QuotaExceededError

logger = logging.getLogger(__name__)

# Swedish market geo/language constants
SWEDEN_GEO_ID = 2752
STOCKHOLM_GEO_ID = 1011766
GOTEBORG_GEO_ID = 1011762
MALMO_GEO_ID = 1011763
SWEDISH_LANG_ID = 1053


def _wrap_google_ads_error(exc: Exception) -> GoogleAdsApiError | QuotaExceededError:
    """Convert a google-ads SDK exception into a typed ApiError.

    Inspects the error code to detect quota exhaustion vs general API errors,
    and attaches a human-readable hint.
    """
    try:
        from google.ads.googleads.errors import GoogleAdsException  # type: ignore

        if isinstance(exc, GoogleAdsException):
            failure = exc.failure  # GoogleAdsFailure proto
            # Check first error for RESOURCE_EXHAUSTED / quota errors
            if failure and failure.errors:
                first_error = failure.errors[0]
                # Error code is a proto message; check its name-based attr
                error_code_detail = first_error.error_code
                if hasattr(error_code_detail, "quota_error") and str(
                    error_code_detail.quota_error
                ) not in ("", "UNSPECIFIED", "UNKNOWN"):
                    return QuotaExceededError()
                # Auth errors
                if hasattr(error_code_detail, "authentication_error") and str(
                    error_code_detail.authentication_error
                ) not in ("", "UNSPECIFIED", "UNKNOWN"):
                    hint = "Run 'sem auth login' to re-authenticate with Google Ads."
                    return GoogleAdsApiError(str(exc), hint=hint, failure=failure)
                # Authorization errors
                if hasattr(error_code_detail, "authorization_error") and str(
                    error_code_detail.authorization_error
                ) not in ("", "UNSPECIFIED", "UNKNOWN"):
                    hint = (
                        "Check that your Google account has access to this customer ID. "
                        "Verify via 'sem accounts list'."
                    )
                    return GoogleAdsApiError(str(exc), hint=hint, failure=failure)
            hint = "Check the Google Ads API documentation for details."
            return GoogleAdsApiError(str(exc), hint=hint, failure=failure)
    except ImportError:
        pass

    try:
        from google.api_core.exceptions import GoogleAPIError  # type: ignore

        if isinstance(exc, GoogleAPIError):
            hint = "A Google API error occurred. Check your network and credentials."
            return GoogleAdsApiError(str(exc), hint=hint)
    except ImportError:
        pass

    return GoogleAdsApiError(str(exc), hint="Unexpected Google Ads API error.")


class GoogleAdsService:
    """Service for Google Ads API operations using the official SDK.

    Initializes an authenticated client via the Phase 7 factory and exposes
    async methods for keyword research and campaign data retrieval.
    """

    def __init__(self, customer_id: str) -> None:
        """Initialize service for a specific customer account.

        Args:
            customer_id: Google Ads customer ID (hyphens stripped automatically).

        Raises:
            AuthError: If no stored tokens or developer token is missing.
        """
        self._customer_id = customer_id.replace("-", "")
        # get_google_ads_client raises AuthError — callers handle it
        self._client = get_google_ads_client(customer_id=self._customer_id)
        self._ga_service = self._client.get_service("GoogleAdsService")

    def _search(self, query: str) -> list:
        """Execute a GAQL query and return a list of result rows.

        This is the single entry point for all GAQL queries so that error
        wrapping happens once rather than in every method.

        Args:
            query: GAQL query string.

        Returns:
            List of GoogleAdsRow objects.

        Raises:
            GoogleAdsApiError: Wraps any SDK API error.
            QuotaExceededError: Wraps RESOURCE_EXHAUSTED / quota errors.
        """
        try:
            response = self._ga_service.search(
                customer_id=self._customer_id, query=query
            )
            return list(response)
        except Exception as exc:
            raise _wrap_google_ads_error(exc) from exc

    async def get_keyword_ideas(
        self,
        seeds: list[str],
        geo_id: int = SWEDEN_GEO_ID,
        language_id: int = SWEDISH_LANG_ID,
        page_size: int = 1000,
    ) -> list[dict]:
        """Get keyword suggestions from Keyword Planner.

        Args:
            seeds: Seed keywords for idea generation.
            geo_id: Google Ads geo target constant ID (default: Sweden 2752).
            language_id: Google Ads language constant ID (default: Swedish 1053).
            page_size: Maximum number of results to return.

        Returns:
            List of dicts with keys: text, avg_monthly_searches, competition,
            avg_cpc_micros, competition_index.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        try:
            kp_idea_service = self._client.get_service("KeywordPlanIdeaService")
            request = self._client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = self._customer_id
            request.language = f"languageConstants/{language_id}"
            request.geo_target_constants.append(f"geoTargetConstants/{geo_id}")
            request.keyword_seed.keywords.extend(seeds)
            request.page_size = page_size

            response = kp_idea_service.generate_keyword_ideas(request=request)

            results = []
            for idea in response:
                metrics = idea.keyword_idea_metrics
                results.append(
                    {
                        "text": idea.text,
                        "avg_monthly_searches": int(metrics.avg_monthly_searches),
                        "competition": metrics.competition.name,
                        "avg_cpc_micros": int(metrics.average_cpc_micros),
                        "competition_index": int(metrics.competition_index),
                    }
                )
            return results
        except (GoogleAdsApiError, QuotaExceededError):
            raise
        except Exception as exc:
            raise _wrap_google_ads_error(exc) from exc

    async def get_search_volumes(
        self,
        keywords: list[str],
        geo_id: int = SWEDEN_GEO_ID,
        language_id: int = SWEDISH_LANG_ID,
    ) -> list[dict]:
        """Get search volume and CPC data for specific keywords.

        Calls Keyword Planner and filters results to only keywords present
        in the input list.

        Args:
            keywords: Exact keyword list to retrieve volumes for.
            geo_id: Google Ads geo target constant ID (default: Sweden 2752).
            language_id: Google Ads language constant ID (default: Swedish 1053).

        Returns:
            List of dicts with keys: keyword, monthly_searches,
            avg_cpc_sek (float, SEK), competition.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        ideas = await self.get_keyword_ideas(
            seeds=keywords, geo_id=geo_id, language_id=language_id
        )
        keyword_set = set(keywords)
        results = []
        for idea in ideas:
            if idea["text"] in keyword_set:
                results.append(
                    {
                        "keyword": idea["text"],
                        "monthly_searches": idea["avg_monthly_searches"],
                        # Convert micros (1/1,000,000 of the currency unit) to SEK
                        "avg_cpc_sek": idea["avg_cpc_micros"] / 1_000_000,
                        "competition": idea["competition"],
                    }
                )
        return results

    async def get_campaigns(self, include_removed: bool = False) -> list[dict]:
        """Fetch all campaigns from the account.

        Args:
            include_removed: When False (default), excludes REMOVED campaigns.

        Returns:
            List of campaign dicts with keys: id, name, status,
            advertising_channel_type, campaign_budget.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        query = (
            "SELECT campaign.id, campaign.name, campaign.status, "
            "campaign.advertising_channel_type, campaign.campaign_budget "
            "FROM campaign"
        )
        if not include_removed:
            query += " WHERE campaign.status != 'REMOVED'"

        rows = self._search(query)
        results = []
        for row in rows:
            campaign = row.campaign
            results.append(
                {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "status": campaign.status.name,
                    "advertising_channel_type": campaign.advertising_channel_type.name,
                    "campaign_budget": campaign.campaign_budget,
                }
            )
        return results

    async def get_ad_groups(self, campaign_id: str) -> list[dict]:
        """Fetch ad groups for a campaign.

        Args:
            campaign_id: The campaign ID (numeric string, hyphens stripped).

        Returns:
            List of ad group dicts with keys: id, name, status, type.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        campaign_resource = (
            f"customers/{self._customer_id}/campaigns/{campaign_id}"
        )
        query = (
            "SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.type "
            f"FROM ad_group WHERE ad_group.campaign = '{campaign_resource}'"
        )
        rows = self._search(query)
        results = []
        for row in rows:
            ad_group = row.ad_group
            results.append(
                {
                    "id": str(ad_group.id),
                    "name": ad_group.name,
                    "status": ad_group.status.name,
                    "type": ad_group.type_.name,
                }
            )
        return results

    async def get_keywords(
        self, ad_group_id: Optional[str] = None
    ) -> list[dict]:
        """Fetch keywords, optionally filtered by ad group.

        Args:
            ad_group_id: Optional ad group ID to filter by.

        Returns:
            List of keyword dicts with keys: text, match_type, status.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        query = (
            "SELECT ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type, "
            "ad_group_criterion.status "
            "FROM ad_group_criterion "
            "WHERE ad_group_criterion.type = 'KEYWORD'"
        )
        if ad_group_id is not None:
            ad_group_resource = (
                f"customers/{self._customer_id}/adGroups/{ad_group_id}"
            )
            query += f" AND ad_group_criterion.ad_group = '{ad_group_resource}'"

        rows = self._search(query)
        results = []
        for row in rows:
            criterion = row.ad_group_criterion
            results.append(
                {
                    "text": criterion.keyword.text,
                    "match_type": criterion.keyword.match_type.name,
                    "status": criterion.status.name,
                }
            )
        return results

    async def get_ads(
        self, ad_group_id: Optional[str] = None
    ) -> list[dict]:
        """Fetch responsive search ads, optionally filtered by ad group.

        Args:
            ad_group_id: Optional ad group ID to filter by.

        Returns:
            List of ad dicts with keys: headlines, descriptions, status.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        query = (
            "SELECT ad_group_ad.ad.responsive_search_ad.headlines, "
            "ad_group_ad.ad.responsive_search_ad.descriptions, "
            "ad_group_ad.status "
            "FROM ad_group_ad "
            "WHERE ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'"
        )
        if ad_group_id is not None:
            ad_group_resource = (
                f"customers/{self._customer_id}/adGroups/{ad_group_id}"
            )
            query += f" AND ad_group_ad.ad_group = '{ad_group_resource}'"

        rows = self._search(query)
        results = []
        for row in rows:
            ad_group_ad = row.ad_group_ad
            rsa = ad_group_ad.ad.responsive_search_ad
            results.append(
                {
                    "headlines": [
                        ac.text for ac in rsa.headlines
                    ],
                    "descriptions": [
                        ac.text for ac in rsa.descriptions
                    ],
                    "status": ad_group_ad.status.name,
                }
            )
        return results

    async def get_account_info(self) -> dict:
        """Get basic account information.

        Returns:
            Dict with keys: id, name, currency, timezone.

        Raises:
            GoogleAdsApiError: On API errors.
            QuotaExceededError: When quota is exhausted.
        """
        query = (
            "SELECT customer.id, customer.descriptive_name, "
            "customer.currency_code, customer.time_zone "
            "FROM customer LIMIT 1"
        )
        rows = self._search(query)
        if not rows:
            return {}
        customer = rows[0].customer
        return {
            "id": str(customer.id),
            "name": customer.descriptive_name,
            "currency": customer.currency_code,
            "timezone": customer.time_zone,
        }
