# Next-Session Handoff — RSA resume on campaign 23867614686

> **✅ RESOLVED 2026-05-24.** The resume push is COMPLETE. See
> `.planning/v0.3.7-LIVE-PUSH.md` for the full write-up. Final live state:
> 963 ad groups, 9,880 keywords, 3,589 RSAs, 8 campaign assets, 943 promotions,
> PAUSED. Two resume ship-blockers (GAQL SELECT/WHERE; asset-skip enum-name)
> were fixed with regression tests; 951 duplicate assets cleaned. Code changes
> are UNCOMMITTED on `main` (branch + commit `campaign_pusher.py`,
> `tests/test_campaign_pusher.py`, `scripts/dedupe_campaign_assets.py`,
> `.planning/v0.3.7-LIVE-PUSH.md`, `CLAUDE.md`). The original handoff below is
> kept for the historical record — note it was WRONG that 0 RSAs had landed
> (2,960 were already live; partial_failure had pushed them).

---

> **Created:** 2026-05-22 22:30 (end of v0.3.7 push session)
> **Supersedes:** the prior `NEXT-SESSION-HANDOFF.md` (now archived as `.planning/v0.3.6-finish-line-handoff.md`)
>
> **Tomorrow's plan, in two commands:** verify quota → resume push.

---

## 1. Push state at handoff

**Live campaign:** `23867614686` ("Flightnetwork - All Destinations [2026-05-22 22:19:35]") on customer `469-180-7001`.
**Suffix used:** ` [2026-05-22 22:19:35]` (mandatory for `--resume` so plan entity names align with live ones).
**Status:** PAUSED.
**Quota state:** EXHAUSTED. Retry-in-seconds returned 85,348 ≈ 23.7 hours from ~2026-05-22 22:19 UTC. Don't query before ~2026-05-23 22:00 UTC.

**What landed:**

| Entity | Pushed | Status |
|---|---|---|
| CampaignBudget | 1 | ✅ |
| Campaign (PAUSED) | 1 | ✅ |
| CampaignCriterion (lang+geo) | 1+ | ✅ |
| AdGroups | 963 (expected) | ✅ (push reached RSA phase, so all earlier phases completed) |
| Keywords | ~9,894 minus partial_failure drops | ✅ (probably; couldn't confirm — quota locked) |
| RSAs | **0** | ❌ blocked on RESOURCE_EXHAUSTED |
| Sitelinks | 0 | not yet |
| Callouts | 0 | not yet |
| Promotions | 0 | not yet |
| Lead form | n/a | `--skip-lead-forms` set |

**The retry-backoff worked exactly as designed**: AdGroupAdService returned RESOURCE_EXHAUSTED on attempt 1; backed off 30s → retry → exhausted → 60s → retry → exhausted → 120s → retry → exhausted → 240s → retry → exhausted → gave up. The exhaustion is a hard daily cap, not transient throttling, so backoff can't help. Resume mode is the answer.

---

## 2. Tomorrow's resume push

Single command. The `--resume` capability we built today queries the live campaign once, snapshots existing ad groups + keywords + RSAs + asset types, then pushes ONLY what's missing.

**Pre-flight (one read query — bail if it 429s):**

```bash
cd "D:/Second Brain/03 Projects/SEM Master"
SEM_DISABLE_LLM=1 PYTHONPATH="D:/Second Brain/03 Projects/SEM Master" python -u -c "
from src.auth.google_ads_auth import get_google_ads_client
c = get_google_ads_client(customer_id='4691807001')
ga = c.get_service('GoogleAdsService')
list(ga.search(customer_id='4691807001',
    query='SELECT customer.id FROM customer LIMIT 1'))
print('quota OK')
"
```

**Resume push:**

```bash
cd "D:/Second Brain/03 Projects/SEM Master"
SEM_DISABLE_LLM=1 PYTHONPATH="D:/Second Brain/03 Projects/SEM Master" python -u -c "
import sys
sys.argv = ['sem', 'case', 'push', 'etraveli',
           '--resume', '23867614686',
           '--name-suffix', ' [2026-05-22 22:19:35]',
           '--skip-lead-forms',
           '--bid-strategy', 'clicks',
           '--yes']
from src.cli.app import main
main()
"
```

**Expected resume behaviour:**
1. Build plan in-memory (~10s)
2. Query live state: 1 query each for ad_group, ad_group_criterion, ad_group_ad, campaign_criterion, campaign_asset (~5 ops total)
3. Surface a warning: "Resume mode: snapshot has 963 ad groups, ~9,890 keywords, 0 RSAs already live"
4. Skip budget/campaign/criteria creation (campaign id already known)
5. AdGroups phase: skip all 963 (all exist) — warning "skipped 963 existing ad groups, pushing 0 new"
6. Keywords phase: skip all (all exist) — warning "skipped ~9,890 existing keywords, pushing 0 new"
7. RSAs phase: push all 4,580 (none exist) — main work
8. Sitelinks: push 4
9. Callouts: push 4
10. Promotions: push 943 + 943 asset links

**Expected report at completion:**
```
Ad groups:      0 (all 963 already live)
Keywords:       0 (all ~9,890 already live)
RSAs:           4,580
Assets:         8 (4 sitelinks + 4 callouts) + 943 promotions = 951
Asset links:    ~960
```

**Expected duration:** 10–20 min, dominated by RSA mutations + their retry/backoff ladder if daily quota dips again. If RSAs get killed again partway through, re-run the same `--resume` command — the next pass will skip the RSAs that DID land and only push what's still missing.

---

## 3. If quota still 429s tomorrow

The 85,348-second retry-in lands at approximately 2026-05-23 22:00 UTC. If queries 429 before that, just wait. The error message itself tells you when (`Retry in X seconds`).

In the worst case (Google's daily test-account caps stay angry for multiple days), the resume command is fully idempotent — run it any time, day after day, and each pass picks up where the prior pass left off.

---

## 4. Verify the result (after resume completes)

```bash
cd "D:/Second Brain/03 Projects/SEM Master"
SEM_DISABLE_LLM=1 PYTHONPATH="D:/Second Brain/03 Projects/SEM Master" python -u -c "
from src.auth.google_ads_auth import get_google_ads_client
c = get_google_ads_client(customer_id='4691807001')
ga = c.get_service('GoogleAdsService')
CID = '23867614686'
print('Live entity inventory:')
for label, q in [
    ('ad_groups',     f'SELECT ad_group.id FROM ad_group WHERE campaign.id = {CID}'),
    ('keywords',      f'SELECT ad_group_criterion.resource_name FROM ad_group_criterion WHERE campaign.id = {CID} AND ad_group_criterion.type = \"KEYWORD\"'),
    ('RSAs',          f'SELECT ad_group_ad.resource_name FROM ad_group_ad WHERE campaign.id = {CID}'),
    ('campaign_assets', f'SELECT campaign_asset.field_type FROM campaign_asset WHERE campaign.id = {CID}'),
]:
    rows = list(ga.search(customer_id='4691807001', query=q))
    print(f'  {label}: {len(rows)}')
"
```

Expected: 963 ad_groups, ~9,890 keywords, 4,580 RSAs, ~951 campaign_assets.

---

## 5. v0.3.7 bundle status

Already committed on `main` as `0951406`:
- Push hardening (bid-strategy override, partial_failure, retry-backoff)
- Ad-copy emitter polish (FLAG-1 hyphen title-case, FLAG-2 path grow, FLAG-3 case-insensitive dedup)
- Resume capability + 5 new tests (99/99 critical tests passing)
- Cleanup script (17 partial campaigns removed today)

**Outstanding follow-ups** (after resume push completes):
1. Write `.planning/v0.3.7-LIVE-PUSH.md` documenting the 2026-05-22 → 2026-05-23 push split, the resume verification, and the final entity counts
2. Save memory entry `v037-live-push.md`
3. Operator decisions still open (NOT blocking the push):
   - IATA-accredited claim — moot, fictitious case (per user)
   - Switch to TARGET_ROAS in Ads UI once conversion tracking is configured

---

## 6. Cheat sheet — files touched this session

| Path | Purpose |
|---|---|
| `src/generators/ad_copy_generator.py` | `_title_case_word` (hyphen-aware), `_grow_path_segment`, `_PATH_GENERIC_GEO_PREFIXES`, casefold dedup in 4 `_add` closures |
| `src/apis/campaign_pusher.py` | `_ResumeState`, `_build_resume_state`, `_extract_text_n`, `resume_campaign_id` field, resume-aware phase methods |
| `src/cli/case_commands.py` | `--resume <id>` flag + numeric-id normalisation |
| `tests/test_campaign_pusher.py` | 5 resume tests + `_FakeService.search` stub |
| `scripts/cleanup_test_account.py` | Idempotent bulk-REMOVE for partial campaigns |

---

*Total estimated time tomorrow: ~25 min (quota check 1 min + resume push 10–20 min + verification 2 min + write-up 5 min).*
