# Portfolio case study draft

## Problem

A reference housing-processing workflow needed a reproducible implementation and a usable visual interface.
The source monthly MLS observations were unavailable, so the product needed to make aggregate evidence
useful without fabricating individual records or disguising public home values as transaction prices.

## Users and design

Intended users: students, researchers, policy staff and housing analysts. These are product hypotheses,
not findings from interviews. The default public journey compares California counties, while a clearly
separate local-only mode supports authorized MLS analysis. Explicit units, period labels, valid counts,
source information and visible limitations take priority over decorative KPIs.

## Implementation

Independent modular Python pipeline, Streamlit/Plotly frontend, official Census bulk ingestion, GeoPandas
county operations, and optional PostgreSQL with migrations and inspectable analytical SQL. Distinct data
contracts prevent conflation of property records, field summaries and county-year estimates.

## Decisions and challenges

- Corrected feed-specific price/date semantics rather than copying the upstream fallback logic.
- Preserved unmatched mortgage records instead of deleting transactions beyond available rate coverage.
- Chose official Census bulk tables after a direct API request returned a key requirement.
- Kept missingness and IQR sensitivity visible; no fabricated distributions from published quantiles.
- Deferred Next.js and PostGIS because they do not yet solve a demonstrated need at this scale.

## Observed engineering results

174 real public county-year estimates across all 58 California counties; tested deterministic fixture
exports, spatial validation, Streamlit filters and SQL/Python parity. Exact test results and operational
checks are in `verification.md`. These are engineering results, not user/business impact metrics.

## Remaining work

Authorized full-feed verification, official assignment comparison when available, broader
mobile/accessibility evaluation, usability testing and profiling.
The public release is live at https://california-housing-atlas.streamlit.app/; deployment interactions
and public CSV output were checked directly. Add screenshots and a short narrated demo
from the final deployed public-data app. Do not include private MLS records or claim employer endorsement.
