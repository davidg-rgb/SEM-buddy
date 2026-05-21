"""Google Ads API client using the official SDK with OAuth authentication.

GoogleAdsService wraps the google-ads SDK to provide keyword research and
campaign data retrieval targeting the Swedish market.

DryRunGoogleAdsService overrides every method with synthetic data for use in
dry-run demos or testing without API credentials.
"""

from __future__ import annotations

import logging
import random
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
            if failure and failure.errors:
                first_error = failure.errors[0]
                error_code_detail = first_error.error_code

                # The error_code proto is a `oneof` — only the actively-set
                # variant has a meaningful value. Use WhichOneof to find it
                # rather than reading every sub-field (which all default to 0
                # / UNSPECIFIED but read as such inconsistently).
                active_field: str | None = None
                if hasattr(error_code_detail, "WhichOneof"):
                    try:
                        active_field = error_code_detail.WhichOneof("error_code")
                    except Exception:
                        active_field = None

                if active_field == "quota_error":
                    return QuotaExceededError()
                if active_field == "authentication_error":
                    hint = "Run 'sem auth login' to re-authenticate with Google Ads."
                    return GoogleAdsApiError(str(exc), hint=hint, failure=failure)
                if active_field == "authorization_error":
                    hint = (
                        "Check that your Google account has access to this customer ID. "
                        "Verify via 'sem accounts list'."
                    )
                    return GoogleAdsApiError(str(exc), hint=hint, failure=failure)
                # Field validation errors surface the failing path so callers
                # can fix the request shape (e.g. missing required field).
                if active_field in ("field_error", "request_error"):
                    msg = first_error.message
                    path = ".".join(
                        e.field_name
                        for e in (first_error.location.field_path_elements or [])
                    )
                    detail = f"{msg} (field={path})" if path else msg
                    return GoogleAdsApiError(
                        detail,
                        hint="Inspect the failing field path and fix the request.",
                        failure=failure,
                    )
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


# ---------------------------------------------------------------------------
# Swedish keyword expansion helpers (used by DryRunGoogleAdsService)
# ---------------------------------------------------------------------------

# Common Swedish prefixes/suffixes for keyword expansion in dry-run mode
_SWEDISH_MODIFIERS = [
    "stockholm",
    "bästa",
    "billig",
    "professionell",
    "akut",
    "pris",
    "erbjudande",
    "nära mig",
    "anlita",
    "jämför",
    "online",
    "snabb",
]

# Swedish RSA headlines (max 30 chars) — reusable across synthetic ads
_SWEDISH_HEADLINES = [
    "Ring oss idag",          # 14
    "Gratis offert",          # 14
    "Bästa priset",           # 13
    "Erfarna experter",       # 17
    "Snabb leverans",         # 15
    "Kvalitet garanteras",    # 21
    "Kontakta oss nu",        # 16
    "Boka tid online",        # 16
    "Vi löser problemet",     # 20
    "Nöjda kunder",           # 13
    "20 års erfarenhet",      # 18
    "Certifierade proffs",    # 21
]

# Swedish RSA descriptions (max 90 chars)
_SWEDISH_DESCRIPTIONS = [
    "Vi erbjuder professionell service till konkurrenskraftiga priser. Kontakta oss idag!",  # 84
    "Över 500 nöjda kunder. Boka en kostnadsfri konsultation och få ett skräddarsytt erbjudande.",  # 90 – trim
    "Snabb och pålitlig service i hela Sverige. Certifierade experter redo att hjälpa dig.",  # 86
    "Jämför priser och spara pengar. Vi matchar konkurrenternas priser — ring oss nu!",  # 81
]

# Ensure descriptions fit within 90 chars
_SWEDISH_DESCRIPTIONS = [d[:90] for d in _SWEDISH_DESCRIPTIONS]


def _seed_rng_for_keywords(seeds: list[str]) -> random.Random:
    """Return a seeded RNG based on a stable hash of the seed list."""
    seed_hash = hash(tuple(sorted(seeds))) % (2**31)
    return random.Random(seed_hash)


def _expand_keywords(seeds: list[str], rng: random.Random) -> list[str]:
    """Expand a seed list with Swedish modifier combinations."""
    results = list(seeds)  # always include the originals
    for seed in seeds:
        modifiers = rng.sample(_SWEDISH_MODIFIERS, k=min(4, len(_SWEDISH_MODIFIERS)))
        for mod in modifiers:
            # Alternate prefix/suffix placement
            if rng.random() > 0.5:
                results.append(f"{seed} {mod}")
            else:
                results.append(f"{mod} {seed}")
    # Deduplicate while preserving order, cap at 15
    seen: set[str] = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
        if len(unique) >= 15:
            break
    return unique


# ---------------------------------------------------------------------------
# DryRunGoogleAdsService
# ---------------------------------------------------------------------------


class DryRunGoogleAdsService(GoogleAdsService):
    """Mock service returning synthetic data for dry-run mode.

    No credentials required. Overrides every async method of GoogleAdsService
    with deterministic synthetic data suitable for demos, testing, and pipeline
    dry-runs.

    All randomness is seeded so that the same inputs always produce the same
    outputs.
    """

    def __init__(self, customer_id: str) -> None:
        """Initialize without calling the parent auth setup.

        Args:
            customer_id: Google Ads customer ID (hyphens stripped).
        """
        self._customer_id = customer_id.replace("-", "")
        self._client = None
        self._ga_service = None
        logger.info("Dry-run mode — using synthetic Google Ads data")

    # ------------------------------------------------------------------
    # Synthetic data helpers
    # ------------------------------------------------------------------

    def _make_rng(self, *parts: str) -> random.Random:
        """Stable RNG seeded from customer_id + extra context parts."""
        seed = hash((self._customer_id,) + parts) % (2**31)
        return random.Random(seed)

    # ------------------------------------------------------------------
    # Keyword Planner methods
    # ------------------------------------------------------------------

    async def get_keyword_ideas(
        self,
        seeds: list[str],
        geo_id: int = SWEDEN_GEO_ID,
        language_id: int = SWEDISH_LANG_ID,
        page_size: int = 1000,
    ) -> list[dict]:
        """Return synthetic keyword ideas for the given seeds."""
        rng = _seed_rng_for_keywords(seeds)
        expansions = _expand_keywords(seeds, rng)

        results = []
        for text in expansions:
            results.append(
                {
                    "text": text,
                    "avg_monthly_searches": rng.randint(50, 12000),
                    "competition": rng.choice(["LOW", "MEDIUM", "HIGH"]),
                    "avg_cpc_micros": rng.randint(2_000_000, 25_000_000),
                    "competition_index": rng.randint(10, 90),
                }
            )
        return results

    async def get_search_volumes(
        self,
        keywords: list[str],
        geo_id: int = SWEDEN_GEO_ID,
        language_id: int = SWEDISH_LANG_ID,
    ) -> list[dict]:
        """Return synthetic search volume data for each keyword."""
        rng = _seed_rng_for_keywords(keywords)
        results = []
        for kw in keywords:
            results.append(
                {
                    "keyword": kw,
                    "monthly_searches": rng.randint(100, 5000),
                    "avg_cpc_sek": round(rng.uniform(2.0, 25.0), 2),
                    "competition": rng.choice(["LOW", "MEDIUM", "HIGH"]),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Campaign structure methods
    # ------------------------------------------------------------------

    async def get_campaigns(self, include_removed: bool = False) -> list[dict]:
        """Return synthetic campaigns (1 Search, 1 Display, 1 Paused)."""
        campaigns = [
            {
                "id": f"{self._customer_id}_c1",
                "name": "Söknätverkskampanj - Brand",
                "status": "ENABLED",
                "advertising_channel_type": "SEARCH",
            },
            {
                "id": f"{self._customer_id}_c2",
                "name": "Displaykampanj - Remarketing",
                "status": "ENABLED",
                "advertising_channel_type": "DISPLAY",
            },
            {
                "id": f"{self._customer_id}_c3",
                "name": "Söknätverkskampanj - Generisk",
                "status": "PAUSED",
                "advertising_channel_type": "SEARCH",
            },
        ]
        if not include_removed:
            campaigns = [c for c in campaigns if c["status"] != "REMOVED"]
        return campaigns

    async def get_ad_groups(self, campaign_id: str) -> list[dict]:
        """Return 2 synthetic ad groups per campaign."""
        return [
            {
                "id": f"{campaign_id}_ag1",
                "name": "Varumärke - Exakt",
                "status": "ENABLED",
                "type": "SEARCH_STANDARD",
            },
            {
                "id": f"{campaign_id}_ag2",
                "name": "Generisk - Bred",
                "status": "ENABLED",
                "type": "SEARCH_STANDARD",
            },
        ]

    async def get_keywords(
        self, ad_group_id: Optional[str] = None
    ) -> list[dict]:
        """Return synthetic keywords (4-6 per ad group)."""
        rng = self._make_rng("keywords", ad_group_id or "all")
        swedish_terms = [
            "tandläkare stockholm",
            "bästa tandvård",
            "akut tandläkare",
            "tandvård billig",
            "tandimplantat pris",
            "tandhygienist stockholm",
        ]
        count = rng.randint(4, 6)
        match_types = ["EXACT", "PHRASE", "BROAD"]
        results = []
        for i, term in enumerate(swedish_terms[:count]):
            results.append(
                {
                    "text": term,
                    "match_type": match_types[i % len(match_types)],
                    "status": "ENABLED",
                }
            )
        return results

    async def get_ads(
        self, ad_group_id: Optional[str] = None
    ) -> list[dict]:
        """Return 1-2 synthetic responsive search ads per ad group."""
        rng = self._make_rng("ads", ad_group_id or "all")
        count = rng.randint(1, 2)
        ads = []
        for _ in range(count):
            headlines = rng.sample(_SWEDISH_HEADLINES, k=3)
            descriptions = rng.sample(_SWEDISH_DESCRIPTIONS, k=2)
            ads.append(
                {
                    "headlines": headlines,
                    "descriptions": descriptions,
                    "status": "ENABLED",
                }
            )
        return ads

    async def get_account_info(self) -> dict:
        """Return synthetic account info for dry-run mode."""
        return {
            "id": self._customer_id,
            "name": "Dry-Run Test Account",
            "currency": "SEK",
            "timezone": "Europe/Stockholm",
        }


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def get_ads_service(customer_id: str, dry_run: bool = False) -> GoogleAdsService:
    """Return a GoogleAdsService or DryRunGoogleAdsService based on dry_run flag."""
    if dry_run:
        return DryRunGoogleAdsService(customer_id)
    return GoogleAdsService(customer_id)


# ---------------------------------------------------------------------------
# Customer / account provisioning (C12 + C13)
# ---------------------------------------------------------------------------


def _normalize_customer_id(raw: str) -> str:
    return raw.replace("-", "").strip()


def _format_customer_id(numeric_id: str | int) -> str:
    """Insert hyphens into a numeric customer ID: 4691807001 → 469-180-7001."""
    s = str(numeric_id).replace("-", "")
    if len(s) != 10 or not s.isdigit():
        return str(numeric_id)
    return f"{s[:3]}-{s[3:6]}-{s[6:]}"


def create_customer_client(
    mcc_id: str,
    descriptive_name: str,
    *,
    currency_code: str = "SEK",
    time_zone: str = "Europe/Stockholm",
) -> str:
    """Create a new ad account under the configured MCC.

    Returns the new customer ID in XXX-XXX-XXXX format. Wraps the
    `CustomerService.create_customer_client` RPC.

    Raises:
        GoogleAdsApiError: On API failures (auth, quota, name conflict).
    """
    try:
        from src.auth.google_ads_auth import get_google_ads_client
    except Exception as exc:  # pragma: no cover - defensive
        raise GoogleAdsApiError(
            f"Failed to import google-ads auth helper: {exc}",
            hint="Run `pip install -e .[dev]` to install google-ads.",
        ) from exc

    clean_mcc = _normalize_customer_id(mcc_id)
    try:
        client = get_google_ads_client()
        customer_service = client.get_service("CustomerService")
        new_customer = client.get_type("Customer")
        new_customer.descriptive_name = descriptive_name
        new_customer.currency_code = currency_code
        new_customer.time_zone = time_zone
        response = customer_service.create_customer_client(
            customer_id=clean_mcc,
            customer_client=new_customer,
        )
        # response.resource_name is "customers/{numeric_id}"
        resource = response.resource_name
        numeric = resource.rsplit("/", 1)[-1]
        formatted = _format_customer_id(numeric)
        logger.info(
            "Created customer client '%s' under MCC %s -> %s",
            descriptive_name, mcc_id, formatted,
        )
        return formatted
    except (GoogleAdsApiError, QuotaExceededError):
        raise
    except Exception as exc:
        raise _wrap_google_ads_error(exc) from exc


def invite_admin(
    customer_id: str,
    email: str,
    *,
    access_role: str = "ADMIN",
) -> str:
    """Invite an email address to a customer with the given access role.

    `access_role` must be one of ADMIN, STANDARD, READ_ONLY, EMAIL_ONLY.
    Returns the invitation resource name on success.

    Raises:
        GoogleAdsApiError: On API failures.
        ValueError: If `access_role` is invalid.
    """
    allowed_roles = {"ADMIN", "STANDARD", "READ_ONLY", "EMAIL_ONLY"}
    if access_role.upper() not in allowed_roles:
        raise ValueError(
            f"Invalid access_role {access_role!r}; must be one of {sorted(allowed_roles)}"
        )

    try:
        from src.auth.google_ads_auth import get_google_ads_client
    except Exception as exc:  # pragma: no cover - defensive
        raise GoogleAdsApiError(
            f"Failed to import google-ads auth helper: {exc}",
        ) from exc

    clean_id = _normalize_customer_id(customer_id)
    try:
        client = get_google_ads_client(customer_id=clean_id)
        invitation_service = client.get_service("CustomerUserAccessInvitationService")
        op = client.get_type("CustomerUserAccessInvitationOperation")
        invitation = op.create
        invitation.email_address = email
        # Role is a proto enum on the request type. The string-based field
        # name on newer SDKs is `access_role`.
        AccessRoleEnum = client.get_type("AccessRoleEnum")
        invitation.access_role = getattr(AccessRoleEnum.AccessRole, access_role.upper())
        response = invitation_service.mutate_customer_user_access_invitation(
            customer_id=clean_id,
            operation=op,
        )
        resource_name = response.result.resource_name
        logger.info(
            "Invited %s as %s to %s -> %s", email, access_role, customer_id, resource_name,
        )
        return resource_name
    except (GoogleAdsApiError, QuotaExceededError):
        raise
    except ValueError:
        raise
    except Exception as exc:
        raise _wrap_google_ads_error(exc) from exc


__all__ = [
    "GoogleAdsService",
    "DryRunGoogleAdsService",
    "get_ads_service",
    "create_customer_client",
    "invite_admin",
]
