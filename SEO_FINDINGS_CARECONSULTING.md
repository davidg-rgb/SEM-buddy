# SEO Analyzer — Test Run Findings

**Test site:** https://careconsulting.se/
**Date:** 2026-05-06
**Mode:** site (11 pages crawled, Lighthouse on)
**Result:** B (87/100)

This document has two parts:

1. **Site findings** — what the analyzer reported about careconsulting.se.
2. **Analyzer feedback** — bugs, false positives, and scoring-logic improvements I noticed while interpreting the report. These are the actionable items for the bot that built the tool.

---

## Part 1 — Site findings (careconsulting.se)

### Scorecard

| Category | Score | Grade |
|---|---|---|
| Technical | 97 | A |
| Links | 100 | A |
| On-page | 91 | A |
| Content | 68 | D |
| Schema | 67 | D |
| **Total** | **87** | **B** |

### Indexability — full picture

robots.txt explicitly blocks 4 paths (intentional):
```
Disallow: /tack
Disallow: /leva/betala
Disallow: /hantera
Disallow: /api/
```

10 pages are fully indexable (`200`, `index, follow`, self-canonical). Only `/hantera` carries `noindex, nofollow` plus a canonical pointing to `/` — also intentional (customer self-service page).

### Real issues to fix on the site

**Quick wins:**
- 7 pages have title tags 34–49 chars; extend to 50–60.
- 4 pages have meta descriptions 69–119 chars; extend to 120–160.
- Broken heading hierarchy on at least one page (H1→H3 jump).

**Performance (Lighthouse 80/100):**
- LCP 3990 ms (target ≤2500). Compress hero images, add CDN, lazy-load below-fold.
- TBT 305 ms (target ≤200). Code-split, defer non-critical JS.
- CLS 0.000 ✓, TTFB 187 ms ✓.

**Content:**
- 4 thin pages under 300 words: `/tjanster` (222), `/omdomen` (283), `/boka` (227), `/hantera` (129). The `/hantera` one is non-indexable so it doesn't count.

**Schema:**
- 8 of 11 pages have JSON-LD; LocalBusiness/Person entries missing required fields (`address`, `telephone`).
- `/trygghetsrummet`, `/integritetspolicy`, `/villkor` have no schema at all.

---

## Part 2 — Feedback for the analyzer (the actual ask)

These are issues I hit while reading the report. Fixing them is what would move the analyzer closer to "100/100 trustworthy."

### A. False positives in the critical-issues bucket

**Issue A1 — `noindex` flagged as critical without checking robots.txt context.**

The report flagged `/hantera` having `noindex, nofollow` as a **critical issue**. But that page is *also* `Disallow`'d in robots.txt, *not* in the sitemap, and has a canonical pointing to `/`. Every signal says the owner intentionally excluded it. The analyzer treated a deliberate exclusion as a bug.

**Recommendation:** before flagging `noindex` as critical, check:
- Is the URL listed in `robots.txt` Disallow? → not critical, downgrade to "info: confirm exclusion is intentional."
- Is the URL absent from the sitemap? → same downgrade.
- Is the canonical pointing somewhere else? → same.

If 2+ exclusion signals agree, it's almost certainly intentional. Critical should be reserved for cases where exclusion signals *conflict with* inclusion signals (e.g., `noindex` on a page that **is** in the sitemap, or that has internal links pointing at it as if it should rank).

**Issue A2 — robots.txt `Disallow` + meta `noindex` redundancy not reported.**

A page blocked in robots.txt cannot be crawled, so Googlebot never reads the meta `noindex`. This is a known gotcha: pages blocked by robots.txt can still appear in the index (URL only, no snippet) because Google can't see the noindex directive. The analyzer should flag this combination as a low-priority warning: *"Page is both Disallowed in robots.txt and has meta noindex — meta tag is unreachable. Pick one."*

**Issue A3 — non-self canonical on a non-indexable page is a passive signal, not a failure.**

`/hantera` has `canonical → /`. The analyzer's `is_self_canonical=False` flag implies a problem, but for a noindex page it's ~irrelevant. Suppress canonical warnings when `noindex` or robots.txt block is in effect.

### B. Action plan double-counts the same issue across pages

The handlingsplan lists 7 separate "Title-tagg har för få tecken" entries — one per page. From a fix-effort perspective these are *one task* (the site's title-template is short by design or by CMS template). Recommendation: group identical issue-types into a single action item with a list of affected URLs underneath. Same goes for the 4 meta-description entries and 4 thin-content entries. This would also let the report show real "effort buckets" instead of inflated counts.

### C. Score weighting masks the real story

The site scored B (87/100) but two categories are D (Content 68, Schema 67). The current weighting (Content 20%, Schema 10%) means a site can get a B while having serious content gaps. Two suggestions:

- **Cap the overall grade at the lowest category grade** (or limit it to one grade above the worst category). A site with a D in Content shouldn't get a B overall — that's misleading.
- **Show "weakest link" prominently in the executive summary.** Right now the summary says "1 critical issue" (which was a false positive) but doesn't say "your content category is a D." That's the actually-true headline.

### D. Schema scoring is too binary

`/trygghetsrummet` only has `BreadcrumbList`. That's not "has schema" in any meaningful sense for a service page — it's missing `Service` or `MedicalBusiness`. The current check counts presence, not appropriateness. Recommendation:

- For service/product pages, expect `Service`/`Product` schema with required fields, not just any JSON-LD.
- For LocalBusiness, require `address`, `telephone`, `openingHours`. Currently the report flags missing fields as low priority — for a local business, that's the highest-impact schema check (drives map pack visibility).
- Add a "schema-appropriateness" sub-score: did the page pick the right schema type for its content?

### E. Lighthouse per-page coverage

Lighthouse appears to be run only on the homepage (single LCP/TBT number). For a site crawl, performance can vary wildly per template. Either:
- Sample 3 pages (homepage + one service page + one content page) and report each, OR
- Be explicit that Lighthouse numbers are homepage-only.

Currently the report shows one set of CWV numbers without saying which URL they're from, which is misleading.

### F. Missing checks I'd expect at 100/100

The categories cover most ground, but a "complete" SEO analyzer would also check:

- **Internal anchor text quality** — are internal links using descriptive anchors or "läs mer" / "klicka här"?
- **Image weight** — total image bytes per page, not just alt-text count. Largest contributor to LCP.
- **Mobile vs desktop CWV** — Google ranks on mobile; the current single CWV number doesn't say which.
- **HTTPS redirect chain** — does `http://` → `https://` work cleanly without a 302 hop?
- **`hreflang` coverage** — for Swedish sites with potential international expansion (and the model already supports `hreflang_tags`).
- **Broken link check (4xx/5xx in internal links)** — `total_internal_links: 336` but no check that any of them resolve.
- **Duplicate title/meta-description detection across pages** — easy template smell.
- **Structured data validity** (run through Schema.org/Google Rich Results test rules, not just presence).
- **Open Graph completeness** for social sharing.

### G. "Snabba vinster" sort order

The report orders quick wins by descending impact, but several "title too short" entries beat "broken heading hierarchy" — heading hierarchy is a stronger signal and a one-time fix. Recommendation: factor in **fix-uniqueness** (one fix → many pages = bigger leverage) when computing impact/effort ratio, so structural fixes float to the top.

### H. Report hygiene

Small things in `seo_report.md`:
- The On-page table has a blank header row (`| Sida | Title | Längd | Meta-beskr. | H1 | Canonical |` followed by a blank line, then data starts on the next row). Looks like a templating bug.
- Title length column says `48t` (presumably "tecken") but the next column is unlabelled but shows the same number — duplicate data. Drop one.
- Meta-beskr. column shows `129t` etc. but the column header says "Meta-beskr." — should be "Meta-beskr. (tecken)" or similar.

### I. Tactical: what would actually move careconsulting.se to 95+?

Ordered by leverage:

1. **LCP fix** (3990→<2500 ms): single biggest score lever. Compress hero image, defer the largest JS bundle.
2. **Add `Service` schema with full LocalBusiness fields** to `/tjanster`, `/leva`, `/trygghetsrummet`. Closes Schema D → A.
3. **Lengthen titles to 55 chars** across all 7 short ones. Single CMS template change.
4. **Expand thin pages** `/tjanster`, `/omdomen`, `/boka` to 350+ words.
5. **Fix heading hierarchy** wherever H1→H3 jump exists.
6. **Reduce TBT** via code-splitting (defer Calendly / chat widget / analytics).

Items 1–3 alone should push the site to ~95.

---

## Summary for the bot

The analyzer is solid — accurate crawl, clean Swedish output, good action-plan format. The two highest-ROI improvements:

1. **Context-aware indexability scoring** (don't flag intentional exclusions as critical). Section A above.
2. **Group repeated issues in the action plan** so effort estimates aren't inflated. Section B.

Everything else in Part 2 is incremental polish.
