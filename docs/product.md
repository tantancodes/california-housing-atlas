# Product brief: California Housing Atlas

## Problem and audience

A public, explainable county housing explorer for students, researchers, policy staff and housing analysts.
These are intended users, not interview findings. No user research or adoption evidence is claimed.

Three concrete problems:
1. Comparing counties requires reconciling geography identifiers, units and reporting periods.
2. Asking prices, sale prices, owner-estimated values and affordability ratios are easily conflated.
3. Attractive housing charts often conceal missing data, sampling uncertainty and data provenance.

## Initial product contract

Public data is the default. A user chooses a five-year ACS vintage and indicator, sees all 58 counties,
selects counties using the map or an accessible selector, compares values across published periods,
reads the source and uncertainty, and downloads the selected aggregate rows.

An IDX analyst separately runs the local processing CLI against authorized monthly files, reviews the
quality reports, and opens a private local dashboard. They compare listing and sold feeds separately,
filter available geography/date/subtype fields and inspect distribution/timeline/rate context.
Published reference CSVs are a third, aggregate-only evidence view, with no invented transaction detail.

## Priorities and trade-offs

| Capability | User value | Effort/risk | Priority |
|---|---|---|---|
| Validated reference workflow and lineage | Trustworthy deliverable | Medium/schema variation | P0 |
| Separate listing/sold semantics and honest empty states | Avoid misleading findings | Low | P0 |
| Public county map, FIPS, ACS estimates/MOEs | Reproducible public exploration | Medium/source availability | P0 |
| Linked comparison/time charts and download | Answer place-comparison questions | Medium/map event behavior | P1 |
| Mortgage context | Explain macro background | Low/temporal interpretation | P1 |
| Optional PostgreSQL analytical layer | Inspectable SQL and persistent analytical storage | Medium/deployment | P1 |
| Real public monthly sale/asking-price data | Timely market exploration | High/licensing/coverage | P2 |
| PostGIS service-side point queries | Useful only at larger scale | High/unnecessary now | Deferred |
| Next.js and separate API | No demonstrated current user benefit | High/adds duplicate contracts | Deferred |
| School district overlays | Specialized local analysis | Medium/source/overlaps | Deferred |

## Journeys

- Compare places: public mode → ACS vintage → value/income → select Alameda and Los Angeles → compare
  chart/table → inspect MOEs → download county estimates. Clear the map selection to return to sidebar choices.
- Audit evidence: reference mode → sold feed → reported price quantiles → read warnings → inspect upstream
  missingness. No claim of validated residential medians or current market totals.
- Review private feed: CLI → manifest/validation → local-only dashboard → choose feed and filters → examine
  medians with valid counts, IQR sensitivity, missing rate matches. Private records are never downloadable in UI.

## Acceptance and success criteria (targets, not measured adoption)

- All 58 counties match the boundary FIPS set for each public vintage; zero duplicate county-year keys.
- All important numeric, date, ratio, rate-merge and spatial-join tests pass in CI.
- Three documented data modes start without unhandled exceptions; empty filters give an explicit state.
- No raw feed, credentials, reference assets or cache included in the public container.
- Sources, period, units and limitations visible before a user interprets a chart.
- Keyboard county controls offer an alternative to map gestures; charts have accompanying tables.
- Target: a user completes the comparison journey in under two minutes in usability testing (not yet measured).
- Target: warm public dashboard render under two seconds locally; actual hosted performance not yet measured.

## Visual and interaction system

Warm neutral canvas (#F6F7F2), ink sidebar (#1B2E2D), forest accents (#286C60),
Georgia display typography and a system sans-serif for controls. Original CSS draws on the map-first,
restrained design patterns of [Felt](https://felt.com/) and [CARTO](https://carto.com/); no third-party
stylesheets, fonts or assets are copied or loaded. Shared styles live in `atlas/styles.css` and the
Plotly template in `atlas/style.py`. These are packaged with the app, including container/cloud installs.

A horizontal legend and muted sequential green scale keep the county map prominent. The main map and
comparison sit side by side on desktop; native Streamlit columns stack on small screens. Numbered section
labels, thin borders, and whitespace establish hierarchy. Labels, hover information and data tables convey
meaning beyond color. Native keyboard controls and visible focus states remain available. Reduced-motion
preferences are respected. Source/period context and statistical limitations remain visible.

No fabricated user/business metrics or decorative KPI changes. Native responsive components and basic
viewport checks alone do not establish WCAG conformance or replace device/screen-reader testing.
