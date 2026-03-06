# Feature Landscape: SEM Master Polish Milestone

**Domain:** Google Ads campaign automation for Swedish market
**Researched:** 2026-03-06
**Focus:** What "done right" looks like for each area being polished

---

## Table Stakes

Features that must work correctly for the tool to be usable. Missing or broken = tool cannot be trusted.

### 1. Correct Swedish Characters in All Data Files

| Item | Status | Severity | Details |
|------|--------|----------|---------|
| Fix diacritics in `negative_keywords.json` | BROKEN | CRITICAL | Uses ASCII: "tjanster", "sjalv", "anstallning", "karriar", "lon", "lonestatistik", "arbetsformedlingen", "rad" |
| Fix diacritics in `ad_copy_patterns.json` | BROKEN | CRITICAL | Uses ASCII: "Foretag", "Tjanst", "Nojda", "Palitlig", "Radgivning", "Basta", "ars", "Behover", "hjalper" |
| Fix diacritics in `cta_phrases.json` | BROKEN | CRITICAL | Uses ASCII: "Fa offert", "Begar offert", "Bestall idag", "Kop nu", "Lagg i varukorg", "Las mer", "Utforska", "Begransat", "Nojd" |
| Fix diacritics in `industry_keywords.json` | LIKELY BROKEN | CRITICAL | Not inspected but same authoring pattern as other files |

**Correct forms (sampling):**

| Wrong (current) | Correct |
|-----------------|---------|
| tjanst / tjanster | tjanst / tjanster |
| sjalv | sjalv |
| Foretag | Foretag |
| Nojda | Nojda |
| Fa offert | Fa offert |
| Begar | Begar |
| Bestall | Bestall |
| Kop | Kop |
| Las mer | Las mer |
| Begransat | Begransat |
| Palitlig | Palitlig |
| Radgivning | Radgivning |
| lon | lon |
| karriar | karriar |
| anstallning | anstallning |

Wait -- let me be precise. The correct Swedish forms are:

| Wrong (current) | Correct Swedish |
|-----------------|----------------|
| tjanst | tjänst |
| tjanster | tjänster |
| sjalv | själv |
| Foretag | Företag |
| Nojda | Nöjda |
| Fa offert | Få offert |
| Begar | Begär |
| Bestall | Beställ |
| Kop | Köp |
| Las mer | Läs mer |
| Begransat | Begränsat |
| Palitlig | Pålitlig |
| Radgivning | Rådgivning |
| lon | lön |
| karriar | karriär |
| anstallning | anställning |
| lonestatistik | lönestatistik |
| arbetsformedlingen | arbetsförmedlingen |
| rad | råd |
| gor det sjalv | gör det själv |
| steg for steg | steg för steg |
| Basta | Bästa |
| ars | års |
| Behover | Behöver |
| hjalper | hjälper |
| Lagg i varukorg | Lägg i varukorg |
| Utforska | Utforska |
| Fa kontakt | Få kontakt |
| Nojd kund-garanti | Nöjd kund-garanti |
| Basta pris | Bästa pris |
| Halva priset | Halva priset |
| Fri prisuppskattning | Fri prisuppskattning |

**Why this is table stakes:** Google Ads displays these strings to real users. Showing "tjanst" instead of "tjänst" looks unprofessional and damages client credibility. Swedish speakers immediately notice missing diacritics -- å, ä, ö are distinct letters, not decorative accents.

**Confidence:** HIGH -- verified by reading actual data files and cross-referencing with Swedish language rules.

---

### 2. Google Ads Editor CSV Format Compliance

| Item | Status | Severity | Details |
|------|--------|----------|---------|
| UTF-8 BOM encoding | CORRECT | -- | Code uses `utf-8-sig`, which is correct for Google Ads Editor |
| Column headers match Google Ads Editor | MOSTLY CORRECT | MEDIUM | Headers align with standard names but need verification |
| Row Type column | NEEDS VERIFICATION | HIGH | Google Ads Editor may not use "Row Type" -- entities are typically in separate sheets or identified by which columns have values |
| Criterion Type values | CORRECT | -- | Uses "Broad", "Phrase", "Exact" -- matches Google Ads Editor format |
| Campaign Status default | CORRECT | -- | Defaults to "PAUSED" which is safe |
| Sitelinks missing Campaign column | PARTIAL | MEDIUM | Sitelinks need Campaign association to import correctly |

**Google Ads Editor CSV Column Requirements (verified):**

For **Keywords:**
- Required: Campaign, Ad Group, Keyword
- Standard: Criterion Type (Broad/Phrase/Exact), Status, Final URL, Max CPC

For **Responsive Search Ads:**
- Required: Campaign, Ad Group
- Standard: Ad type, Headline 1-15, Headline 1-15 position, Description 1-4, Description 1-4 position, Final URL, Path 1, Path 2, Status

For **Campaigns:**
- Required: Campaign, Campaign Type, Budget
- Standard: Campaign Status, Budget type, Bid Strategy Type, Networks, Languages, Location

For **Ad Groups:**
- Required: Campaign, Ad Group
- Standard: Status, Max CPC, Ad Group Type

For **Negative Keywords:**
- Required: Campaign, Keyword, Criterion Type

**Key format rules:**
- First row must be column headers
- Multiple values separated by semicolons (e.g., "en;sv" for languages)
- UTF-8 encoding (BOM optional but recommended for Excel)
- Match Type values: Broad, Phrase, Exact, Negative broad, Negative phrase, Negative exact
- Use `#Original` suffix for editing existing items

**Confidence:** MEDIUM -- column names verified against Google support docs and Adobe bulksheet reference. The "Row Type" column approach needs testing against real Google Ads Editor import.

---

### 3. Working Compound Word Splitter

| Item | Status | Severity | Details |
|------|--------|----------|---------|
| Current implementation | BROKEN | HIGH | Only checks suffix list, misses most compounds |
| Linking morpheme handling | MINIMAL | HIGH | Only strips trailing "s", misses other fogemorfem |
| Suffix list too small | LIMITED | MEDIUM | 17 suffixes -- Swedish has hundreds of productive compound suffixes |

**What proper Swedish compound splitting looks like:**

Swedish compound words use linking morphemes (fogemorfem) between components:

| Morpheme | Example | Split |
|----------|---------|-------|
| -s- | företag**s**tjänst | företag + tjänst |
| -s- | blåbär**s**pannkaka | blåbär + pannkaka |
| (none) | kraft**verk** | kraft + verk |
| -e- (from -a) | hälso**dryck** (from hälsa) | hälsa + dryck |
| vowel drop | pannkaka (from panna) | pann + kaka |

**Rules for the -s- fogemorfem:**
- Inserted after each even-numbered word in multi-part compounds (except the final)
- Most common linking morpheme in Swedish
- Not always predictable -- native speakers rely on intuition

**Recommended approach for this tool's scope:**
A full NLP compound splitter (like SECOS or compound-word-splitter with Swedish dictionary) is overkill for an SEM tool. The practical need is:
1. Split compounds to generate keyword variations (e.g., "företagstjänst" -> also target "företag tjänst")
2. Understand compound structure for ad copy fitting (can we break at compound boundary to shorten?)

**Practical recommendation:** Use a dictionary-based approach with a Swedish word list (e.g., from enchant/hunspell sv_SE dictionary) rather than trying to implement linguistic rules. Try splitting at every position, check if both parts are valid Swedish words (accounting for -s- removal).

**Available Python libraries:**
- `compound-word-splitter` (PyPI) -- uses pyenchant, supports Swedish with sv_SE dictionary
- `SECOS` -- unsupervised, has pre-trained Swedish model
- Manual approach with hunspell sv_SE dictionary + greedy matching

**Confidence:** HIGH for the linguistic rules (verified against multiple Swedish grammar sources). MEDIUM for library recommendations (verified existence on PyPI but not tested).

---

### 4. Test Suite

| Item | Status | Severity | Details |
|------|--------|----------|---------|
| Unit tests | MISSING | CRITICAL | Zero test files exist |
| Integration tests | MISSING | HIGH | No CSV import validation |
| Data validation tests | MISSING | HIGH | No checks that data files contain valid Swedish |

**What a good test suite for this tool looks like:**

#### Unit Tests (pytest)

**Models (`test_models.py`):**
- Headline at exactly 30 chars passes validation
- Headline at 31 chars raises ValidationError
- Description at exactly 90 chars passes
- Description at 91 chars raises
- Path fields at 15 chars pass, 16 chars fail
- Sitelink text at 25 chars passes, 26 fails
- RSA requires minimum 3 headlines, 2 descriptions
- Campaign defaults to PAUSED status

**Swedish NLP (`test_swedish_nlp.py`):**
- Compound splitting: "företagstjänst" -> ["företag", "tjänst"]
- Compound splitting: unknown word returns [word]
- Diacritics variants: "bil" generates variants with Swedish chars where applicable
- Stopwords loading returns non-empty set
- Stopwords contain expected words ("och", "att", "det", "en")
- Character counting matches len() for Swedish text

**CSV Exporter (`test_csv_exporter.py`):**
- Exported CSV uses UTF-8 BOM encoding
- Campaign rows have required columns (Campaign, Campaign Type, Budget)
- Keyword rows have required columns (Campaign, Ad Group, Keyword, Criterion Type)
- RSA rows have Headline 1-3 minimum
- Match type values are "Broad", "Phrase", or "Exact"
- Swedish characters survive export/import cycle (write then read back)
- Empty plan produces no output (not a crash)

**Data Files (`test_data_files.py`):**
- All JSON files parse without errors
- All text in data files contains proper Swedish diacritics (no "tjanst", "sjalv", etc.)
- CTA phrases are within headline char limits (30 chars)
- Ad patterns produce output within char limits when filled
- Negative keyword lists are non-empty for each category
- No duplicate entries within categories

#### Integration Tests

**End-to-end (`test_integration.py`):**
- Build a minimal campaign plan, export to CSV, validate CSV structure
- Import exported CSV into pandas, verify all columns present
- Verify headline pinning positions are valid (1, 2, 3, or empty)
- Verify no row has conflicting entity types

**Confidence:** HIGH -- this is standard pytest practice for data transformation tools.

---

## Differentiators

Features that would make the tool notably better but are not blocking for basic usability.

### 5. Diacritics Variant Generation for Keywords

| Feature | Value | Complexity |
|---------|-------|------------|
| Generate both "tjänst" and "tjanst" as keyword variants | Captures misspelled searches | Low |
| Generate "å/a", "ä/a", "ö/o" swaps | Users search without diacritics on non-Swedish keyboards | Low |

**Current implementation bug:** The `_DIACRITICS_MAP` dict in `swedish_nlp.py` has a collision -- "a" is mapped to both "å" and "ä" (second assignment overwrites first). Only "a"->"ä" is active.

**Fix:** Use a list of tuples (already done in the `replacements` list below the dict), but the dict itself is dead code that should be removed.

**Why this is a differentiator:** Swedish users on international keyboards or mobile often search without diacritics. Generating both forms automatically is a real advantage.

**Confidence:** HIGH -- verified by reading `swedish_nlp.py` lines 62-88.

---

### 6. PDF Report Generation

| Feature | Value | Complexity |
|---------|-------|------------|
| Generate PDF reports alongside markdown | Professional client deliverable | Medium |
| Include campaign structure visualization | Easier to review | Medium |

Currently the report generator outputs markdown only. PDF would make it a polished client deliverable. This is a nice-to-have, not blocking.

**Confidence:** HIGH -- verified no PDF generation exists.

---

### 7. Keyword Variation Expansion

| Feature | Value | Complexity |
|---------|-------|------------|
| Compound word keyword expansion | "rörmokare Stockholm" also generates "rör mokare Stockholm" | Medium |
| Plural/singular forms | "tjänster" also generates "tjänst" | Medium |
| Common misspelling variants | Beyond diacritics -- Swedish-specific misspellings | Low |

**Confidence:** MEDIUM -- value depends on campaign size and keyword strategy.

---

### 8. Character Count Warnings (Not Just Rejections)

| Feature | Value | Complexity |
|---------|-------|------------|
| Warn when headline is 25-30 chars (tight but valid) | Helps copywriters leave room for dynamic insertion | Low |
| Suggest shorter synonym when over limit | Automated ad copy fitting | Medium |

Currently the model hard-rejects at 30/90 chars. A warning zone would help the ad copy generator produce better initial output.

**Confidence:** HIGH -- standard Google Ads best practice.

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

### Do NOT Build: Full NLP Pipeline

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full Swedish morphological analyzer | Massive scope, diminishing returns for SEM | Use dictionary lookup + simple suffix rules |
| ML-based compound splitter | Requires training data, complex deployment | Use hunspell dictionary + greedy match |
| Automatic Swedish text generation | Quality can't be guaranteed for ads | Use templates with slot filling |

### Do NOT Build: Google Ads API Integration

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Direct campaign upload via API | Complex auth, billing responsibility, error-prone | Export CSV for manual import via Google Ads Editor |
| Bid management automation | High financial risk, requires monitoring | Set manual/maximize clicks, let Google optimize |
| Performance tracking | Separate concern, Google Ads does this natively | Focus on campaign generation only |

### Do NOT Build: Multi-Language Support

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Generalized i18n framework | This tool is specifically for Swedish market | Keep Swedish-specific approach |
| Language detection | Input is always Swedish | Assume Swedish |
| Translation features | Out of scope | Keep monolingual |

### Do NOT Build: Over-Engineered Configuration

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| GUI/web interface for settings | Adds maintenance burden, this is a CLI/skill tool | Use JSON config files |
| Plugin system for data sources | YAGNI for a focused tool | Hard-code the integrations |
| Database for campaign history | File-based output is sufficient | Export CSVs to a folder |

---

## Feature Dependencies

```
Fix Swedish diacritics in data files
    |
    v
Compound word splitter works correctly
    |
    v
Keyword variation generation (uses splitter + diacritics)
    |
    v
Ad copy generation uses correct Swedish
    |
    v
CSV export produces valid Google Ads Editor file
    |
    v
Test suite validates entire pipeline
```

Key dependency: Diacritics must be fixed FIRST. Everything downstream (compound splitting, keyword generation, ad copy) depends on correct Swedish text in the data files.

---

## MVP Polish Checklist

For the polish milestone, prioritize in this order:

1. **Fix all Swedish diacritics in data files** (table stakes, blocks everything else)
2. **Fix `_DIACRITICS_MAP` collision bug** in `swedish_nlp.py` (quick win)
3. **Add basic test suite** (validates fixes, prevents regressions)
4. **Verify CSV format against Google Ads Editor** (table stakes for the deliverable)
5. **Improve compound word splitter** (use dictionary-based approach)
6. **Remove dead `_DIACRITICS_MAP` dict** (cleanup)

Defer to post-polish:
- PDF report generation (nice but not blocking)
- Advanced keyword expansion (depends on use patterns)
- Character count warnings (refinement)

---

## Sources

- [Google Ads Editor CSV columns](https://support.google.com/google-ads/editor/answer/57747?hl=en) -- official column reference
- [Prepare a CSV file](https://support.google.com/google-ads/editor/answer/56368?hl=en) -- encoding and format rules
- [Import a CSV file](https://support.google.com/google-ads/editor/answer/30564?hl=en) -- import behavior and #Original columns
- [Adobe bulksheet reference for Google Ads](https://experienceleague.adobe.com/en/docs/advertising/search-social-commerce/campaign-management/management/bulksheets/bulksheet-data-formats/bulksheet-data-google) -- comprehensive column listing with required/optional
- [Swedish compound words and joint morphemes](https://duolinguists.wordpress.com/2022/03/04/compound-words-and-joint-morphemes-in-swedish/) -- fogemorfem rules and examples
- [Compound word splitting - Swedish (Findwise)](https://findwise.com/labs/sample/compound-word-splitting-swedish) -- algorithmic approaches
- [compound-word-splitter on PyPI](https://pypi.org/project/compound-word-splitter/) -- Python library with Swedish support
- [SECOS compound splitter](https://github.com/riedlma/SECOS) -- unsupervised splitter with Swedish model
- [Swedish alphabet (Wikipedia)](https://en.wikipedia.org/wiki/Swedish_alphabet) -- å, ä, ö as distinct letters
- Codebase files: `src/utils/swedish_nlp.py`, `src/generators/csv_exporter.py`, `data/swedish/*.json`
