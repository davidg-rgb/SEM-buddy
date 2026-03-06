# Requirements - v0.2.0 Polish & Verify

## Data Quality

- [ ] **DQ-01**: Fix all Swedish diacritics in negative_keywords.json, cta_phrases.json, ad_copy_patterns.json, industry_keywords.json (å, ä, ö instead of ASCII approximations)
- [ ] **DQ-02**: Fix all Swedish diacritics in report_generator.py hardcoded strings ("för" not "for", "sökord" not "sokord", etc.)
- [ ] **DQ-03**: Remove broken `_DIACRITICS_MAP` dict (duplicate key bug), fix `generate_diacritics_variants` to correctly generate å/ä/ö variants
- [ ] **DQ-04**: Implement consistent Swedish section headers in report generator ("Sammanfattning", "Affärsanalys", "Kampanjstruktur", etc.)

## NLP & Keywords

- [ ] **NLP-01**: Replace suffix-based compound splitter with dictionary-based approach using simplemma (greedy decomposition) + pyenchant (Hunspell sv_SE validation)
- [ ] **NLP-02**: Add keyword variation expansion: compound splits, plural/singular forms, diacritics variants as keyword suggestions

## Exports

- [ ] **EXP-01**: Remove fabricated `Row Type` column from all 7 CSV row generator functions in csv_exporter.py
- [ ] **EXP-02**: Add `Campaign` column to sitelink and callout CSV rows (apply extensions to all campaigns)
- [ ] **EXP-03**: Refactor CSV export to produce per-entity-type files: 01_campaigns.csv through 07_callouts.csv
- [ ] **EXP-04**: Add PDF report generation using markdown-pdf library (Markdown -> HTML -> PDF with Swedish char support)
- [ ] **EXP-05**: Generate README_import_order.txt with numbered import sequence for Google Ads Editor

## Infrastructure

- [ ] **INF-01**: Initialize git repository with baseline commit of current v0.1.0 state
- [ ] **INF-02**: Add pytest test suite covering: model validation, Swedish NLP, CSV export schema, data file diacritics, integration smoke test
- [ ] **INF-03**: Create JSON Schema files for validating structure of Swedish data files

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INF-01 | Phase 1 - Git Baseline | Pending |
| DQ-01 | Phase 2 - Swedish Diacritics | Pending |
| DQ-02 | Phase 2 - Swedish Diacritics | Pending |
| DQ-03 | Phase 2 - Swedish Diacritics | Pending |
| DQ-04 | Phase 2 - Swedish Diacritics | Pending |
| NLP-01 | Phase 3 - CSV Export & NLP | Pending |
| NLP-02 | Phase 3 - CSV Export & NLP | Pending |
| EXP-01 | Phase 3 - CSV Export & NLP | Pending |
| EXP-02 | Phase 3 - CSV Export & NLP | Pending |
| EXP-03 | Phase 3 - CSV Export & NLP | Pending |
| EXP-05 | Phase 3 - CSV Export & NLP | Pending |
| EXP-04 | Phase 4 - PDF Report | Pending |
| INF-02 | Phase 5 - Test Suite & Validation | Pending |
| INF-03 | Phase 5 - Test Suite & Validation | Pending |

## Future Requirements (Deferred)

- Character count warnings (25-30 char zone) for ad copy generator
- Advanced misspelling variants beyond diacritics
- CI/CD pipeline for automated testing

## Out of Scope

- Full NLP pipeline / ML-based compound splitter
- Direct Google Ads API campaign upload
- Multi-language support
- GUI/web interface
- Database for campaign history
