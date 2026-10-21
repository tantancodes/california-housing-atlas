# California Housing Atlas: editorial exploration redesign

## Starting point and scope

The previous implementation placed a 440px map beside a comparison chart. Clicking the map silently replaced the comparison dataset, the comparison showed only the current indicator, and there was no persistent county detail view. Up to 58 comparison bars could appear after an empty selection. Styling depended on internal Streamlit DOM selectors, including obsolete widget selectors.

This is an implementation review of the previous source, not a user-research finding. Browser access was unavailable during this redesign; no new before/after visual inspection or measured usability improvement is claimed.

## Principles and visual system

- Give geography the largest surface and introduce the statistical scope before the map.
- Separate looking at one county from choosing a comparison group.
- Keep published uncertainty next to estimates and avoid claims of annual change or statistical significance.
- Use warm off-white (`#F7F6F0`), charcoal (`#26342E`), muted neutral surfaces and one green accent (`#286C60`). Distinguish trend series with green/neutral tones and county names in tooltips.
- Use supported Streamlit theme options for native controls, sidebar, serif heading hierarchy, borders and radii. Local CSS targets only Atlas-owned markup and documented `st-key-…` container classes. No generated classes, internal widget selectors, hidden toolbars, remote fonts or extra dependencies.
- Keep native keyboard-operable selectors as alternatives to map interaction. Charts include text alternatives; comparison values and CSVs supply a non-map route to the evidence.

## Information architecture

1. **The big picture:** exact product title/subtitle, ACS scope, three county-level headline metrics, section links and full-width 610px choropleth. A data-derived range annotation reports the lowest/highest available point estimates.
2. **Explore a county:** independent county selector, outlined map geography, all three indicators, published 90% MOEs and point-estimate ranks. Rank 1 is highest; ties share a rank and missing values are excluded.
3. **Compare counties:** up to three counties, three horizontal charts, MOE whiskers, a formatted evidence table, signed differences against the first selected county, and comparison CSV. Fewer than two counties produce guidance rather than silently substituting all counties.
4. **Explore changes:** comparison-group lines across explicitly labeled five-year vintages. With no comparison group, use the county in focus. Adjacent vintages overlap; nominal dollar changes do not isolate market changes. The income/value scatter preserves the broader context and highlights the focused county.
5. **About the data:** definitions, limitations, full-snapshot CSV, source/licensing links, quality/provenance and optional locally cached national mortgage context.

## Interaction decisions

Year, indicator, comparison and focused-county controls use stable session keys. Changing vintage or indicator retains the focused county when present. A map selection callback resolves only known five-digit FIPS and updates the accessible county selector. It does not silently overwrite comparisons; an explicit “Add to comparison” action appears when there is space. Once three counties are selected, the user removes one in the sidebar before adding another.

County comparisons share the selected vintage. Each indicator's bar axis starts at zero and spans the full current California range including available upper MOE bounds; different units never share one numeric scale. Differences are signed arithmetic differences, with unavailable inputs remaining unavailable. These are descriptive point estimates, not significance tests.

The neutral map base preserves counties with missing estimates; colored polygons include only available values, and the selection outline is independent of the metric. Missing estimates never become zeros. An entirely unavailable metric retains the geography and displays an explanatory message.

## Before → after

| Before | Implemented change |
| --- | --- |
| Map shared a row with a similarly weighted chart | Full-width primary map followed by a coherent five-section journey |
| Map clicks changed the comparison group | Persistent focused county and explicit comparison membership |
| One-indicator bars, no detailed county context | Three-indicator comparison, MOEs, ranks and signed differences |
| Empty comparison became all counties | Explicit empty state; no substituted observations |
| Vintage represented as a bare ending year | Five-year period labels and visible overlapping-vintage caveats |
| Internal Streamlit selector overrides | Supported native theme plus owned HTML/container styles |
| Comparison-only download near the bottom | Comparison export plus prominent complete-snapshot export |

## Verification and limits

- Full local suite: **22 passed**, including the existing PostgreSQL integration test; five new product/data tests added.
- Ruff lint, formatting and Python compilation pass.
- Streamlit launched on `http://127.0.0.1:8506`; health endpoint returned `ok`.
- Bundled data: 174 real county-vintage rows (58 counties × 2022–2024); ratios verified against source columns. No observation generation or pipeline/database schema changes.
- New tests exercise focus persistence across vintage/indicator changes, explicit addition to comparisons, empty selections, exact signed differences, tied/missing ranks, FIPS resolution and missing-map geometry.
- Browser tooling reported no available browser and a connection startup failure after reset. **Desktop/mobile rendering, actual polygon clicks, hover placement, anchor scrolling and live visual deployment inspection remain unverified.** AppTest exercises Streamlit execution and widget behavior; it does not replace these browser checks.
- Native responsive columns and wrapping navigation are retained, but no mobile usability or screen-reader audit is claimed. Fixed-height map framing may need adjustment after device inspection. Color alone is not sufficient for distinguishing trend lines; names are available in the legend/tooltips and CSVs, but direct line labeling remains a possible improvement.
- Selections persist within the Streamlit session, not across new sessions or shareable URLs. No invented user testing, recruitment impact or official IDX-rubric compliance is claimed.

## Implementation

`atlas/dashboard.py` owns public exploration and presentation calculations; `atlas/style.py`, `atlas/styles.css` and `.streamlit/config.toml` define visual primitives. `app.py` retains public/reference/private routing. Existing ingestion, CRMLS, GeoPandas and SQL components are preserved. `tests/test_dashboard_exploration.py` adds focused regression coverage.
