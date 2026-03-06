# Research Summary - v0.2.0 Polish Milestone

## Critical Findings

### 1. Swedish Diacritics Broken Everywhere
All 4 data files + report_generator.py use ASCII approximations. "Få offert" is "Fa offert", "tjänst" is "tjanst" etc. This is the #1 priority - everything downstream is affected.

### 2. CSV Exporter Has 3 Breaking Issues
- **`Row Type` column is fabricated** - Google Ads Editor does NOT use this. Must be removed from all 7 row generators.
- **Sitelinks/callouts missing `Campaign` column** - will fail on import.
- **Single-file approach has column collisions** - recommend splitting to per-entity-type CSV files.

### 3. `_DIACRITICS_MAP` Has Duplicate Key Bug
`"a"` is mapped twice - `"a"->"å"` is overwritten by `"a"->"ä"`. Dead code that should be removed.

### 4. Compound Splitter Is Too Basic
Only 18 hardcoded suffixes. Recommend: `simplemma>=1.1` (greedy decomposition) + `pyenchant>=3.2` (dictionary validation via Hunspell sv_SE).

### 5. No PDF Generation Exists
`pypdf` is for reading, not writing. Recommend `markdown-pdf>=1.13` (MD->HTML->PDF, UTF-8 Swedish support confirmed).

## Stack Additions

**Production:** `simplemma>=1.1`, `pyenchant>=3.2`, `markdown-pdf>=1.13`
**Dev:** `pytest-datadir>=1.5`, `syrupy>=4.6`

## Build Order (from research consensus)

1. Init git (baseline before any changes)
2. Fix Swedish diacritics in ALL data files + report_generator.py
3. Fix `_DIACRITICS_MAP` bug + improve compound splitter
4. Fix CSV exporter (remove Row Type, add Campaign to extensions, split files)
5. Add PDF generation
6. Add test suite
7. End-to-end validation

## Anti-Features (Don't Build)
- Full NLP pipeline / ML compound splitter
- Direct Google Ads API upload
- Multi-language support
- GUI/web interface
