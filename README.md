# California Housing Atlas

An auditable Python housing dashboard with a modular CRMLS processing pipeline and a reproducible,
public California county affordability explorer. Streamlit + pandas + Plotly + GeoPandas; optional PostgreSQL.

**This reproduces relevant behavior of a confirmed reference implementation; it does not certify compliance
with an unseen official IDX Exchange rubric. No private MLS observations are included.**

## Run locally

Python 3.12 is the tested runtime. From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501. The public view works immediately from the included **real Census** county
snapshot: 58 counties × ACS 2022, 2023 and 2024 five-year vintages (174 county-year records).
There are no fabricated property records. Test fixtures are deliberately synthetic and isolated under tests.

## Data modes

| Mode | Data grain | Supported analysis | Limitations |
|---|---|---|---|
| Public county atlas (default) | County × ACS five-year vintage | County choropleth, comparisons, value/income, period changes, public CSV download | Owner-occupied home values, not sale/list prices; no monthly or property-level inference |
| Reference summaries | Published field-level aggregate | Reported counts, quantiles and missingness | Population/period unverified; cannot recompute residential medians, PPSF or county/monthly trends |
| Authorized local CRMLS (opt-in) | Listing/sold feed record with monthly file lineage | Filters, price histogram/box plot, feed-specific medians/PPSF, monthly summaries, rate comparisons, quality reports | Requires authorized source files; repeated monthly snapshots are not unique homes/sales |

### Refresh public Census data

```bash
python -m atlas.cli public --years 2022 2023 2024
```

Downloads official Census table-based bulk files B19013 and B25077 and 2023 generalized county boundaries.
No API key is needed. Bulk files are read in chunks; only California county aggregates are retained.
Source URLs, retrieval time and SHA256 hashes are in `data/public/provenance.json`.
`data/cache` is ignored; only the small derived public snapshot and boundaries belong in Git.
The tested Census API required a key; public ingestion uses the official bulk distribution directly.

### Inspect the reference summaries

```bash
python -m atlas.cli reference
```

This downloads only two published calculated-summary CSVs at a pinned upstream commit, validates their
long-format schema, and records provenance. Select **Reference summaries** in the sidebar.
Reference assets are ignored by Git and excluded from the public image: the inspected repository has no
LICENSE file. Availability on GitHub is not treated as a blanket redistribution license.

### Process authorized CRMLS data locally

Place files outside the repository, or in ignored `data/raw/`, named exactly
`CRMLSListingYYYYMM.csv` and/or `CRMLSSoldYYYYMM.csv`.

```bash
python -m atlas.cli fred
python -m atlas.cli process \
  --input /absolute/path/to/authorized/crmls \
  --output data/processed \
  --start 2024-01 --end 2026-09 \
  --rates data/cache/mortgage.csv
ATLAS_ENABLE_PRIVATE=1 streamlit run app.py --server.address 127.0.0.1
```

Optional spatial county assignment (generalized display boundaries may leave coastal/border points unmatched):

```bash
python -m atlas.cli process --input /absolute/path/to/authorized/crmls \
  --output data/processed --start 2024-01 --end 2026-09 \
  --boundaries data/public/counties.geojson --rates data/cache/mortgage.csv
```

`--end` defaults to the last completed local calendar month. `--rates` is optional; there is no implicit
network request. A single available feed is supported. Missing required fields fail before output generation:

- Both feeds: `PropertyType`.
- Listing: `ListPrice`, `ListingContractDate`.
- Sold: `ClosePrice`, `CloseDate`.
- `LivingArea`, `DaysOnMarket`, coordinates, county, subtype and other fields are optional. Related metrics
  are unavailable when absent. Spatial joining requires Latitude/Longitude and declared polygon CRS.

The pipeline records optional schema drift and file hashes, filters Residential with whitespace/case
normalization, masks invalid numeric/date values, flags geographic/timeline/IQR issues and computes metrics.
Price-per-square-foot uses the feed's valid price divided by valid positive living area. Sold prices never
fall back to asking prices. FRED uses a many-to-one calendar-month join; unmatched observations are retained.

Outputs per feed: `records.csv`, `validation.csv`, `input_missingness.csv`, `clean_missingness.csv`, `dtypes.csv`,
`numeric_summary.csv`, `invalid_coordinates.csv`, `monthly.csv`, available `by_*.csv` segment tables,
`flags.csv`, `iqr_bounds.csv`, `iqr_sensitivity.csv`. `manifest.json` records active feeds, row counts,
file/schema lineage, duplicate snapshot keys when available, undated rows and unmatched mortgage records.
Use a new output directory for each production run; exports are deterministic but the entire multi-file
output is not an atomic transaction. Input files must remain stable during processing.

## Optional PostgreSQL

The default public app reads a small, versioned CSV. PostgreSQL is supported when persistent SQL storage
is useful, without forcing a service dependency on Community Cloud. Start Docker Desktop first:

```bash
export POSTGRES_PASSWORD=atlas_local_only
# Development-only password; configure a separate secret for any hosted database.
docker compose --profile database up -d db
export DATABASE_URL=postgresql://atlas:atlas_local_only@127.0.0.1:5432/atlas
python -m atlas.cli database
ATLAS_PUBLIC_BACKEND=postgres streamlit run app.py --server.address 127.0.0.1
```

The loader validates public data, applies checksum-tracked migrations under an advisory transaction lock,
and upserts county-year keys. Queries are parameterized. See `sql/analytics.sql` for ratio rankings,
across-county medians and nominal period changes. PostGIS is deferred: 58 cached county polygons and batch
GeoPandas joins do not currently justify a spatial database service. No private feeds enter this database loader.

## Verify

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m compileall -q atlas app.py
# With the local development DB above (or an isolated PostgreSQL test database):
TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -q
```

Without `TEST_DATABASE_URL`, the integration test is explicitly skipped. CI supplies an isolated PostgreSQL
17 service, runs the complete suite and never fetches private feeds. See [verification](docs/verification.md)
for actual results, browser checks and remaining release limitations.

## Deployment

Target: **Streamlit Community Cloud**, entrypoint `app.py`, branch `main`, Python **3.12**.
`requirements.txt` installs the locked dependencies and the local package. The bundled Census snapshot
works without credentials. Leave `ATLAS_ENABLE_PRIVATE` disabled; do not upload CRMLS files or reference assets.
See [deployment instructions](docs/deployment.md) for the exact cloud settings and container alternative.
Public deployment is complete only when a live URL has been verified; configuration alone is not deployment.

## Structure

```text
app.py                    Streamlit entrypoint and reference/local feed views
atlas/
  cli.py                  Explicit ingestion and database commands
  pipeline.py             CRMLS ingestion, validation, metrics and CSV reports
  mortgage.py             FRED parsing and monthly alignment
  reference.py            Published aggregate-summary contract
  public.py               Census bulk ingestion, FIPS and spatial joins
  dashboard.py            Linked public county map/charts
  database.py             Optional transactional PostgreSQL adapter
  io.py                   Bounded downloads and provenance
sql/                      Migration and inspectable analytical SQL
data/public/              Reproducible public county snapshot and provenance
tests/                    Calculation, ingestion, spatial, UI and SQL tests
docs/                     Audit, PRD, methodology, deployment and verification
.github/workflows/ci.yml   Lint, formatting, tests and PostgreSQL integration
```

## Interpretation and provenance

- ACS **B25077** is owner-occupied home value; **B19013** is household income. These medians describe
  different populations. Their ratio is contextual, not an affordability eligibility rule or typical buyer budget.
- ACS ending years represent five-year windows; adjacent vintages overlap. Dollar comparisons are nominal,
  with no inflation adjustment. Published 90% margins of error are shown; ratio uncertainty is not estimated.
- Missing, suppressed and negative sentinel values are unavailable. Chart statistics use valid values with
  explicit counts. IQR flags indicate sensitivity, not proof of error; observations remain by default.
- FRED MORTGAGE30US is a national weekly Freddie Mac benchmark. Monthly means are descriptive and may
  include an incomplete latest month. No mortgage forward/backfill, predictive model or causal claim is made.
- MLS data is neither supplied nor licensed by this project. Do not publish employer-owned code or data
  without permission. This repository contains an independent implementation and public Census aggregates.

See [reference audit/checklist](docs/reference-audit.md), [product brief](docs/product.md),
[methodology and sources](docs/methodology.md), and [architecture](docs/architecture.md).
