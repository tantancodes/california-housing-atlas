# Reference audit and feature checklist

Inspected https://github.com/Banks027/VisualizationDashBoard at commit
`09b25175ec828f0dba60f38900ee979d9bc0bbac`. Original clone in `/private/tmp/idx-reference`
was inspected read-only. No source code was copied into the implementation.
This is a reference-behavior inventory, **not an official IDX acceptance rubric**.

## File-by-file review

- **README.md:** describes monthly CRMLS listing/sold CSVs, Residential filtering, numeric/null/calculated
  summaries, coordinate checking, and FRED integration. Execution is terminal-oriented, not a dashboard.
  Dependencies mention pandas, NumPy and GeoPandas; there is no dependency manifest or test suite.
- **Wk1.py:** monthly filename selection, previous completed month, concatenation, positional property-type
  filtering. Missing imports/configuration make the file incomplete standalone. Filename logic accepts invalid
  month numbers and schemas are not compared. January rollover is handled in global code.
- **wk2-3.py:** named Residential filter, null percentages, ClosePrice/LivingArea/DOM descriptive statistics
  (10/25/50/75/90 percentiles), date-to-month grouping, monthly mean FRED merge, CSV exports.
  Hard-coded Windows paths; network IO at import; no feed-specific validation. Drops later transactions when
  rate data ends, and rejects unmatched mortgage months. Empty feeds make the main concat fragile.
- **wk4-5.py:** extends that processing with transformation log, row checkpoints, dtype/date/coordinate
  and numeric validation reports. The reporting calls are accidentally indented into `geographic_summary`,
  including a recursive self-call. These are intended functions, not evidence of a successful execution.
- **wk6_7.py:** coherent main pipeline. Coercion, Residential filtering, schema/missingness reports,
  descriptive distributions and optional matplotlib histogram/box images, FRED monthly means and unmatched
  report, invalid numeric/date/coordinate flags, >90%-missing noncore column removal, derived metrics,
  school-district GeoPandas join, segment summaries, IQR flags and filtered/before-after datasets.
  Pitfalls: stripped values are not used by its Residential mask; MarketPrice falls back from close to asking;
  listing PPSF uses ClosePrice; a single nonmissing CloseDate selects the whole frame's date convention;
  invalid numeric values remain in subsequent medians; spatial overlap can duplicate matches; missing
  boundary CRS is not rejected. Above-list percentage uses all rows rather than valid ratio observations.
- **IDXExchnage.ipynb:** markdown title plus a code cell **identical to wk6_7.py** (normalized whitespace).
  It contains a stream output but no separate interactive visualization. `__file__` requires adaptation in
  notebook environments; stored output is not independently verified source data.
- **Two calculated summary CSVs:** long format `section,item,metric,value`; source/residential counts,
  missingness, unique property types and numeric distribution summaries. Sold: 519,932 source rows and
  350,179 reported residential rows; listing: 893,594 and 567,549. No dates, county breakdowns, price-per-
  square-foot observations or complete source records. Missing percentages agree with **source** counts
  (e.g. 73,640 / 519,932 ≈ 14.16%), not residential counts. Distribution population/time scope is unproven.
  Sold ClosePrice ranges from zero to $989,500,000 and DOM includes negative values, so these are not clean
  market estimates. No LICENSE file was present in the inspected reference.

## Checklist: verified behavior vs implementation

| Feature | Evidence | Current implementation |
|---|---|---|
| Monthly listing/sold ingestion | Wk1 through wk6_7 | Implemented, anchored filename pattern, configurable dates/paths |
| Residential filtering and concat | All scripts | Implemented with stripped, case-insensitive named column |
| Schema/dtype/null reports | wk2-3 onward | Required fields enforced per file; optional drift recorded; input/clean missingness and dtype CSVs |
| Numeric/date/coordinate validation | wk4-5, wk6_7 | Implemented; invalid values masked per metric, flags retained; timeline checks |
| Price percentiles and distributions | wk2-3, wk6_7 | CSV statistics plus interactive histogram/box plot for local records |
| Derived metrics | wk6_7 | Feed-specific market price/PPSF, sold/original-list ratio, nonnegative timelines |
| FRED monthly rate alignment | wk2-3 onward | Implemented; unique-month left join, no dropped transactions, missing-match flags |
| Segment summaries | wk6_7 | County/subtype/MLS area/office CSVs where fields exist; never pool feeds |
| IQR sensitivity | wk6_7 | Flags retained; opt-in dashboard sensitivity and before/after summary output |
| School-district join | wk6_7 | Deferred: optional reference feature outside requested initial scope |
| Automatic >90%-null column deletion | wk6_7 | Deliberately replaced by reports; preserve schema and sparse but meaningful fields |
| Interactive dashboard | Proposed enhancement | Implemented in Streamlit; explicit data grains and limitations |
| Public Census mode | Proposed enhancement | Reproducible ACS ingestion with MOEs/FIPS and Census county polygons |
| County spatial join | Portfolio enhancement | GeoPandas join with CRS/ambiguity validation; preserves unmatched rows |
| PostgreSQL analytical storage | Portfolio enhancement | Optional migrations/loader and inspectable SQL; verification documented separately |
| Public hosting | Portfolio enhancement | Deployment configuration supplied; public URL not yet provisioned |

## Acceptance checks for this implementation

These criteria are derived from the user's requested workflow, not an invented IDX rubric:

1. Missing required input columns fail with the filename before exports begin.
2. Only valid monthly names in the configured range enter ingestion; row/file lineage and SHA256 are recorded.
3. Listing prices/dates and sold prices/dates stay separate; invalid numerics never enter valid-price medians.
4. Missing mortgage months remain visible; no invented observations or back/forward filling.
5. Repeat processing of identical inputs produces identical CSV bytes.
6. Summary-only mode never exposes invented monthly/geographic/property filters or derived property ratios.
7. Public mode uses public aggregate records, publishes provenance and labels home values accurately.
8. Dashboard boots, filters without exceptions and offers useful empty/error states; tests exercise both.
9. Private data is ignored by Git, not embedded in images, and disabled by default in hosted mode.

No official assignment rubric or complete CRMLS source datasets have been supplied. Full-feed accuracy,
licensing of source records and fulfillment of every official IDX requirement remain unverified.
