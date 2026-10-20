# Verification record

Executed locally on 2026-10-19, Python 3.12, macOS ARM64. These are observed results, not deployment claims.

- **17 tests passed** with `TEST_DATABASE_URL` set to the local PostgreSQL 17 container. Without that
  variable: 16 passed, 1 integration test explicitly skipped.
- Ruff lint and formatting checks passed; compileall passed.
- CRMLS ingestion/cleaning/export exercised through isolated synthetic unit-test fixtures only: named
  columns, Residential filtering, invalid numbers/dates, price/PPSF/ratio semantics, date/coordinate flags,
  missing rates, schema failure before outputs, deterministic repeated CSV exports, and empty results.
- Streamlit AppTest verified public startup, vintage/metric/county changes, reference mode,
  authorized-local fixture mode, compatible filters and an incompatible county/subtype empty state.
  A filter-options dependency issue found during testing was corrected: option lists use the full feed,
  so selections do not silently disappear as earlier filters change.
- Real official Census bulk files fetched and validated: **174 county-year records**, all 58 California
  county FIPS in every 2022/2023/2024 vintage. Boundary count/key match/CRS and data ratios passed.
- Real FRED weekly CSV fetched: **667 monthly groups**. Raw and monthly caches remain ignored and
  outside the public deployment image. Missing-week tokens are excluded; rate alignment retains housing rows.
- GeoPandas tests covered reprojection, unmatched coordinates, absent CRS and ambiguous overlapping polygons.
- PostgreSQL 17 Docker service started; checksum-tracked migration, repeat upserts and read backend passed.
  SQL-derived ratios matched the validated public CSV. All three `sql/analytics.sql` statements executed,
  returning 174 ranking rows, 3 vintage aggregates and 174 county-vintage change rows.
- Docker public image built on Linux ARM64. A running container returned **ok** at `/_stcore/health`;
  its AppTest rendered 58 counties. The image contained no raw/processed/reference/cache data directories.
- Chrome visual verification at http://127.0.0.1:8501: public map/charts rendered, and selecting San Diego
  on the map updated the linked comparison chart to San Diego. Native controls/table alternatives are present.

## Not yet verified / limits

- No complete authorized CRMLS monthly source files have been supplied: full-feed integration, deduplication
  semantics, source-specific schema variations and memory/performance at source scale remain unverified.
- Reference summaries cannot validate underlying price distributions or reconstruct monthly/county records.
- No official IDX rubric was supplied. This implementation follows the requested reference workflow.
- No claim of WCAG conformance, full mobile browser QA, user research or measured adoption is made.
- GitHub Actions is configured; its remote result must be checked after publication, not inferred locally.
- Cloud target is Streamlit Community Cloud. A public deployment is not complete until its live URL is
  recorded and verified; local/container results alone do not establish that.
