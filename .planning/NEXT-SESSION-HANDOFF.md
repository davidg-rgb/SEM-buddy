# Next-Session Handoff — push completion + second ad-copy QA pass

> **Created:** 2026-05-21 (end of live-push session)
> **Supersedes:** the v0.3.4 finish-line handoff (now archived at `.planning/v0.3.6-finish-line-handoff.md` — every contract in it is green; v0.3.4 / v0.3.5 / v0.3.6 work all landed).
>
> **Tomorrow's plan, in order:**
> 1. Verify the quota has reset and read this doc + the §1 push-state snapshot.
> 2. Commit the three uncommitted fixes (§2) before anything else.
> 3. Bulk-delete the 17 partial campaigns sitting on `469-180-7001` (§3).
> 4. Run the second ad-copy QA review pass (§4) — block the push until this signs off.
> 5. Re-push (§5). With retry/backoff + partial_failure + bid-strategy override now in place, this should complete in one shot.
> 6. Grant admin access to klaus + kasper (§6).
> 7. Write up + commit (§7).

---

## 1. Push state at handoff

- **Target account**: `469-180-7001` (Etraveligroup Test account David Geborek Wågestrand)
- **Today's session burned through Google's per-account daily ops budget**. A read-only `search_stream` query at end-of-session returned `429 Resource has been exhausted. Retry in 84178 seconds.` ⇒ **quota cooldown ~23 hours** from approximately **2026-05-21 17:20 UTC**. Do not attempt any push or any GAQL query before **~2026-05-22 16:30 UTC** — the retry/backoff in `_safe_mutate` will spin its full 30→60→120→240 ladder against the wall and waste 12+ minutes before falling over.
- **What landed live**: campaign `23869105844` ("Flightnetwork - All Destinations [2026-05-21 17:18:46]") has the structure: 1 budget, 1 campaign (PAUSED, MAXIMIZE_CLICKS), CampaignCriteria, **963 ad groups**, **~9,894 keywords** (a handful trimmed by partial_failure on the `PGD flights` Healthcare-policy false-positive — surfaced as warnings, not errors). **Zero RSAs**, zero sitelinks, zero callouts, zero promotions, zero lead form. Hit `RESOURCE_EXHAUSTED` on the first RSA batch.
- **What's sitting on the account doing nothing**: 17 PAUSED campaigns total — 14 from 2026-05-20 smoke testing + 3 from today's session (one is the partial-success structure; the other two are stillborn from the bid-strategy and partial_failure-kwarg failures). Zero serving impact (all PAUSED) but they pollute the operator's review surface.

```
                               17:03:01  push #1 — bid-strategy / CONVERSION_TRACKING failure
2026-05-21 push attempts:  →   17:16:46  push #2 — partial_failure kwarg shape failure
                               17:18:46  push #3 — structure landed, RSAs blocked on quota ← the one to recover
```

---

## 2. Three uncommitted fixes that need to be committed FIRST

Currently uncommitted on `main` (run `git status` to confirm — modifieds are below). Commit these before touching anything else so the recovery path doesn't lose them on accident.

| File | What changed |
|---|---|
| `src/apis/campaign_pusher.py` | (a) `CampaignPusher.bid_strategy_override` → field that bypasses `case.yaml`'s smart-bidding selection. Required because the v0.3.3 `campaign_goals.target_roas=4.0` selects `MAXIMIZE_CONVERSION_VALUE`, which Google rejects with `CONVERSION_TRACKING_NOT_ENABLED` on a clean test account. (b) `_safe_mutate(..., partial_failure=True, warnings_sink=...)` — when set, the SDK call is wrapped in a `request={...}` dict (the only shape that accepts `partial_failure` across SDK versions); per-op policy errors land in `warnings_sink` instead of failing the whole batch. (c) `_safe_mutate(..., max_retries=4)` — exponential backoff (30→60→120→240s) on `RESOURCE_EXHAUSTED`. Keyword and RSA push paths now run with `partial_failure=True` + `warnings_sink=self.warnings`. |
| `src/cli/case_commands.py` | `--bid-strategy` flag on `sem case push` — accepts `clicks` / `MAXIMIZE_CLICKS` / `MANUAL_CPC` / etc. and threads through to `CampaignPusher.bid_strategy_override`. |
| `tests/test_campaign_pusher.py` | Fake `_FakeService` mutate methods accept the new request-dict calling convention (`request={"customer_id":..., "operations":..., "partial_failure":True}`) alongside the legacy kwargs. Response now carries `partial_failure_error=SimpleNamespace(code=0, ...)` so the warnings-sink path can be exercised by tests. **22 pusher tests pass**, all 196 across the relevant surface still green. |

Commit message draft (use as a starting point):
```
fix(push): bid-strategy override + partial_failure + retry-with-backoff

Three production-hardening fixes that the 2026-05-21 live-push attempts surfaced:

1. --bid-strategy CLI override + CampaignPusher.bid_strategy_override
   bypasses the case.yaml's MAXIMIZE_CONVERSION_VALUE selection. Test
   accounts without a configured conversion action would otherwise fail
   immediately with CONVERSION_TRACKING_NOT_ENABLED. Use --bid-strategy
   clicks for the initial push; flip to TARGET_ROAS in the UI once
   conversion tracking is wired up.

2. partial_failure=True on AdGroupCriterion + AdGroupAd mutates. A
   single policy false-positive (PGD flights tripping Google's
   Healthcare-and-medicines filter on the IATA code) was blocking the
   other 9,893 keywords. With partial_failure on, the bad op surfaces
   as a warning and the batch keeps going. The SDK requires the
   request-dict shape (`request={"customer_id": ..., "operations": ...,
   "partial_failure": True}`); the kwarg shape works for other fields
   but not this one.

3. Exponential-backoff retry on RESOURCE_EXHAUSTED inside _safe_mutate
   (30/60/120/240s, 4 attempts). The per-account daily ops quota gets
   tight on a 17k-entity push; without backoff, the first 429 kills the
   whole run.

Co-Authored-By: ...
```

---

## 3. Account cleanup — delete the 17 partial campaigns

Run after quota resets. Two options:

**Option A — Ads UI bulk delete (5 min, manual)**: open https://ads.google.com/aw/campaigns?ocid=&__c=4691807001, select all 17 campaigns from the list below, change status to REMOVED, save.

**Option B — Scripted (recommended if time)**: write a one-shot `scripts/cleanup_test_account.py` that pages through `Customer.campaigns` matching `name LIKE 'Flightnetwork - All Destinations%'` and bulk-mutates each to REMOVED. ~30 lines. The campaign IDs to remove:

```
23860336215, 23860343253, 23860353003, 23860369383, 23860395288, 23860402014,
23863840980, 23863890696, 23865589133, 23865617183, 23865645974, 23869105844,
23870034697, 23870040121, 23870041123, 23870062483, 23870065114
```

Cost: each delete is one mutate op. 17 ops total — trivial against the daily quota.

---

## 4. Second ad-copy QA review pass — BLOCK the re-push until this signs off

The operator surfaced a screenshot showing the **first-iteration output** (likely v0.1/v0.2 baseline, NOT current v0.3.4 / v0.3.5 / v0.3.6 work). Reference path: `C:\Users\david\Downloads\first iteration.png`. The screenshot demonstrates exactly the pathology v0.3.x was built to fix — useful as a "what NOT to ship" baseline for the reviewer.

**What the first-iteration screenshot shows (the bar to NOT regress to):**

```
Title:        Petropavlovsk-Kamchats, - Call Us
URL:          www.flightnetwork.com/petropavlovsk-k/russian
Description:  Flightnetwork - local petropavlovsk-kamchats, russian federation
              expert. Contact us a. We offer petropavlovsk-kamchats, russian
              federation in 10 years of experience. Contact us. Fast Service.
              Free Quote. Trusted Local Company. Satisfaction Guaranteed.
Sitelinks:    Our Services | About Us | Contact Us | Get [...]
```

Specific failures the reviewer must verify are **gone** in the v0.3.6 output:

1. **Truncation typo in the destination name** — "Petropavlovsk-Kamchats" missing the `-ky`. ✅ v0.3.4 fix 3.2 closes this via `accepted_proposal.json::PKC` rename to "Petropavlovsk-Kamchatsky".
2. **Sentence-pause hyphen in the headline** ("Kamchats, - Call Us") — v0.3.3 banned ` - ` headline pauses.
3. **Lowercase destination tokens in the description** ("petropavlovsk-kamchats, russian federation"). Should never happen — name is title-cased by the resolver, attribute substitution always uses the canonical title-case form.
4. **Truncated mid-sentence description** ("Contact us a." — the "a" is the orphaned "a." from "[Contact us a]bout…" being chopped). v0.3.3 `_fit_to_limit` rejects mid-clause truncation at the ≥50% budget guard.
5. **Service-business templates** that don't apply to OTAs ("X years of experience", "Local Company", "Satisfaction Guaranteed", "Free Quote", "Trusted Local Company"). All scrubbed in patterns.json v3 (the legacy Swedish-care-services patterns are out; OTA-specific patterns are in).
6. **Generic CTAs** ("Call Us") instead of OTA-appropriate ones ("Lock in 60 seconds" / "Compare 800+ airlines" / "Save up to 46% to Bali"). v0.3.2 pinned per-variant H3 CTAs.
7. **URL path with mid-word break** (`/petropavlovsk-k/russian`) — path1/path2 are now derived from the destination name's title-cased token, max 15 chars each, no mid-word breaks.
8. **Generic sitelinks** ("Our Services" / "About Us") instead of destination-specific or OTA-specific ones. v0.3.x ships 4 OTA-flavoured global sitelinks (operator-confirmable).

**Reviewer workflow** (target: 30–40 min):

1. **Regenerate the stratified sample** to get a fresh 32-ad-group set:
   ```
   python -m scripts.stratified_rsa_sample
   # → clients/etraveli/exports/catalog/QA-SAMPLE-v034.md
   ```

2. **Run the gates** to confirm v0.3.4 contracts still hold post-commit:
   ```
   python -m scripts.audit_v034         # Missions 2/3/4a/4b — must return 0 failures
   python -m scripts.spell_check_rsas   # must return 0 flagged tokens
   python -m pytest tests/test_rsa_variants.py tests/test_catalog_campaign_builder.py \
                    tests/test_catalog_bid_rules.py tests/test_campaign_pusher.py -q
   ```

3. **Spawn the `sem-ad-copy` skill / a reviewer agent** with this prompt:
   ```
   Audit the attached 32-ad-group QA sample (.planning/.../QA-SAMPLE-v034.md)
   against the operator's "first-iteration" failure list in
   .planning/NEXT-SESSION-HANDOFF.md §4. For each of the 8 specific failures
   listed there, report whether the v0.3.6 output exhibits the same pathology.
   Sample 8 ad groups across the 5 strata (long-name / short-name / high-disc
   / low-disc / no-price) and rate each on:
     1. Destination name correctness (no truncation typos)
     2. No sentence-pause ` - ` in headlines
     3. Title-case consistency
     4. No mid-clause truncations
     5. No service-business templates leaking through
     6. CTAs are OTA-appropriate (not 'Call Us' / 'Get Quote')
     7. URL paths are clean (no mid-word breaks)
     8. Sitelinks make sense for travel/OTA context
   For each finding, quote the offending text + ad-group ID. Severity:
   BLOCK (do not push) / FLAG (push but log) / PASS.
   ```

4. **Cross-check the PKC ad group specifically** (the destination from the first-iteration screenshot — the operator's mental anchor). Spot-check command:
   ```
   python -c "
   import csv, sys
   sys.stdout.reconfigure(encoding='utf-8')
   with open('clients/etraveli/exports/catalog/04_responsive_search_ads.csv', encoding='utf-8-sig') as f:
       for r in csv.DictReader(f):
           if r['Ad Group'].endswith('(PKC)') and 'text=1' in r['Final URL']:
               for i in range(1, 16):
                   h = r.get(f'Headline {i}', '')
                   if h: print(f'H{i}: {h}')
               for i in range(1, 5):
                   d = r.get(f'Description {i}', '')
                   if d: print(f'D{i}: {d}')
               break"
   ```

5. **Sign-off bar**: zero BLOCK findings + ≤2 FLAG findings → green-light the push. Anything more → fix the pattern pack first.

---

## 5. Re-push

After §2 (commit) + §3 (cleanup) + §4 (reviewer sign-off):

```
SEM_DISABLE_LLM=1 sem case push etraveli \
    --auto-suffix \
    --skip-lead-forms \
    --bid-strategy clicks \
    --yes
```

Expected duration: **8–15 minutes** (mostly rate-limit backoff time on RSAs even with fresh quota — the 4,580 RSA batches at 200/op = 23 calls, each likely waits 30–60s if quota tightens). The retry/backoff in `_safe_mutate` handles this automatically; the operator just waits.

Expected push report at completion:
```
Budgets:        1
Campaigns:      1
Campaign criteria: 1+
Ad groups:      963
Keywords:       9,890 ± a few (partial_failure may drop 1–4 on policy)
RSAs:           4,580
Assets:         8 (4 sitelinks + 4 callouts) + 943 promotions = 951
Asset links:    ~960
```

If RSAs still get blocked: the `BidApplyReport`-style "resume" path is option B from yesterday's notes — write `sem case push-ads <slug>` that queries existing ad groups by name and pushes only the missing RSAs. ~30–45 min of work; cleanest fallback if quota stays angry.

---

## 6. Grant admin access (brief deliverable)

Two emails per the brief:
- `klaus.thorup@etraveligroup.com`
- `kasper.engelheim-hove@etraveligroup.com`

Both should be invited as **ADMIN** on customer `469-180-7001`. The function exists at `src/apis/google_ads.py::invite_admin(customer_id, email, access_role='ADMIN')` (verified by `tests/test_account_provisioning.py`). Quickest path:

```
python -c "
from src.apis.google_ads import invite_admin
invite_admin('469-180-7001', 'klaus.thorup@etraveligroup.com', access_role='ADMIN')
invite_admin('469-180-7001', 'kasper.engelheim-hove@etraveligroup.com', access_role='ADMIN')
"
```

Confirm each prints a resource name on success.

---

## 7. Write-up + commit at the end

1. Commit the §2 fixes (use the draft message in §2).
2. After the re-push completes, write `.planning/v0.3.7-LIVE-PUSH.md` documenting:
   - The 3 push attempts on 2026-05-21 + their failure modes
   - The 3 fixes that closed each failure
   - The final push numbers (entity counts, partial_failure warnings, retry-backoff invocations)
   - The QA reviewer's verdict + sample findings
   - Operator-confirmable items (IATA-accredited claim — still unresolved per the v0.3.4 doc §"What's NOT in this fix")
3. Commit the doc + memory entry (`v037-live-push.md`).
4. Optional but recommended: add `scripts/cleanup_test_account.py` from §3-Option-B.

---

## 8. Smoke commands when re-entering tomorrow

```bash
# 0. Confirm quota has reset (this should NOT 429 — if it does, wait longer)
SEM_DISABLE_LLM=1 python -c "
from src.auth.google_ads_auth import get_google_ads_client
c = get_google_ads_client(customer_id='4691807001')
ga = c.get_service('GoogleAdsService')
list(ga.search_stream(customer_id='4691807001',
    query='SELECT customer.id FROM customer LIMIT 1'))
print('quota OK')
"

# 1. Read the current state (this doc + the archived 0.3.6 handoff for any v0.3.4-6 detail)
cat .planning/NEXT-SESSION-HANDOFF.md
cat .planning/v0.3.6-finish-line-handoff.md  # context only, completed

# 2. Verify tests still pass after the uncommitted fixes
python -m pytest tests/test_campaign_pusher.py tests/test_rsa_variants.py \
                 tests/test_catalog_campaign_builder.py tests/test_catalog_bid_rules.py -q

# 3. After commit + cleanup + reviewer sign-off, the one-line live push:
SEM_DISABLE_LLM=1 sem case push etraveli \
    --auto-suffix --skip-lead-forms --bid-strategy clicks --yes
```

---

## 9. Operator-owned items (NOT for the next session to decide)

- **`IATA-accredited agent` / `IATA-accredited since 2007`** claim — present in 100% of social_proof variants across 963 ad groups. Still pending operator confirmation with the FN account team. If not defensible per market, it's an FTC/ASA risk and must be patched out of `data/en/ad_copy_patterns.json::social_proof` before the operator's review.
- **Whether to promote the operator-curated bid strategy** (`TARGET_ROAS=4.0`) — requires manual conversion-action setup in the Ads UI first. Until then we ship with `MAXIMIZE_CLICKS`.

---

*Total estimated time for tomorrow's session: ~90 minutes (commit 5 min + cleanup 10 min + reviewer pass 30 min + push 15 min + admin grants 5 min + write-up 20 min). The bones are done; tomorrow is mostly verification + the one-shot push.*
