# Methodology, sources and data rights

## Public Census data

US Census Bureau ACS five-year detailed tables **B25077** (median value, owner-occupied housing units)
and **B19013** (median household income), vintages 2022/2023/2024. E001 estimates and M001 published
90% margins of error are retained. We extract summary-level 050 California county rows from the official
pipe-delimited table-based files; the `GEO_ID` suffix is normalized to a five-character county FIPS.
Each vintage must contain 58 unique California counties. County names come from Census boundaries.

Official bulk pattern:
`https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat`

[ACS developer documentation](https://www.census.gov/data/developers/data-sets/acs-5year.html)
provides the survey/API context. The original direct API request in this environment returned a Missing Key
page; we instead use official credential-free bulk files. No mirror data is used in the shipped snapshot.

Boundaries: US Census Bureau `cb_2023_us_county_20m.zip`, California subset; 1:20,000,000 generalized
cartographic boundaries, transformed from their declared CRS into EPSG:4326. They are designed for thematic
mapping, not precise legal/parcel work. [Census boundary documentation](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html).

Census-produced statistical data and boundaries are US government public data. See Census
[policies](https://www.census.gov/about/policies.html) for usage/citation guidance. Cite US Census Bureau,
ACS 5-Year Estimates, B25077/B19013, relevant vintage, and cartographic boundaries 2023. Source URLs,
retrieval timestamp and input/output SHA256 hashes are included with the snapshot; no Census endorsement
is implied. No reference code license is applied to third-party datasets.

## Calculations and limits

- `value_to_income = median_home_value / median_household_income`, requiring both estimates positive.
  This is a ratio of county medians from different populations, not median household-level burden.
- A county's price/income indicator is not a median sale-price/income ratio; ACS contains no observed sales.
- Overview metrics are **unweighted medians of county estimates**. They are not statewide medians.
- Negative ACS sentinels, missing values and nonfinite values are unavailable. Top-coded/suppressed estimates
  are not replaced with assumed dollar values. MOEs remain available where reported; no ratio MOE or
  significance test is calculated. Charts must not imply precise rankings beyond sampling uncertainty.
- Five-year vintages overlap (2022 covers 2018–2022, 2024 covers 2020–2024). Nominal differences include
  inflation and composition shifts; they are not independent annual market changes or causal evidence.

## CRMLS local processing

Only caller-authorized local files. Required property type and feed-specific price/date columns; optional
columns may drift and are recorded. Residential filtering is stripped/case-insensitive. Nonpositive price,
area or original-list denominator, negative DOM/counts, infinite and nonnumeric values become missing.
Dates outside 1800–today or unparsable become missing. Timeline reversals are flagged and negative durations
are unavailable. Coordinate checks separately flag missing/world-range/California-bounding-box issues.
A bounding box does not prove California membership. Optional polygon joins are stricter and preserve
unmatched rows. There is no imputation, record synthesis or automatic price outlier deletion.

Listings use ListPrice and ListingContractDate; sold records use ClosePrice and CloseDate.
PPSF is the row-level valid feed price / valid positive LivingArea. Ratio statistics are calculated from
row-level valid ratios, never from a ratio of independent medians. Year/month aggregation uses event dates,
not source filename dates; snapshot months remain in lineage. Counts describe rows. Listing snapshots and
sold files may repeat properties; no unique-home/sales total or market inventory estimate is claimed.

## Mortgage data

[Freddie Mac via FRED MORTGAGE30US](https://fred.stlouisfed.org/series/MORTGAGE30US), percent,
weekly ending Thursday. Attribution: Freddie Mac, 30-Year Fixed Rate Mortgage Average in the United States
[MORTGAGE30US], retrieved from FRED, Federal Reserve Bank of St. Louis. The series is copyrighted by Freddie
Mac; consult its series notes and FRED terms for reuse. It is fetched explicitly into ignored local cache,
not redistributed in the public bundle or public download. Hosted public mode remains useful without it.

Duplicate weekly dates are rejected; valid positive finite weekly observations are averaged by calendar
month. A housing record receives that month's mean without dropping unmatched or invalid-date records.
This uses within-month information, so it is descriptive only, not an as-of predictive feature. The most
recent month may be partial. Weekly observation counts are exported. No interpolation or extrapolation.

## Reference aggregates

Pinned source/revision in `reference-audit.md`. Published CSV values are shown as **reported upstream**;
their source population/reporting period and cleaning cannot be independently verified. Source missingness
and post-Residential counts are not mixed. No synthetic histogram, county allocation, monthly trend,
individual record or PPSF estimate is reconstructed. The files remain ignored and outside deployment assets.
