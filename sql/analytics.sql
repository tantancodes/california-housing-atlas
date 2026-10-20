-- Nominal county value/income comparisons. This is not household mortgage affordability.
SELECT county_fips, county, year, period, median_home_value,
       median_household_income, value_to_income, home_value_moe, income_moe
FROM county_affordability
ORDER BY year DESC, value_to_income DESC NULLS LAST;

-- Across-county unweighted median, never labeled a statewide home-price median.
SELECT year, COUNT(*) AS counties, COUNT(value_to_income) AS valid_ratios,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY value_to_income) AS median_county_ratio
FROM county_affordability
GROUP BY year ORDER BY year;

-- Adjacent vintages have overlapping samples. No significance or causal interpretation.
WITH change AS (
    SELECT county_fips, county, year, median_home_value,
           LAG(median_home_value) OVER (PARTITION BY county_fips ORDER BY year) AS prior_value
    FROM county_estimates
)
SELECT *, 100.0 * (median_home_value / NULLIF(prior_value, 0) - 1) AS nominal_change_percent
FROM change ORDER BY county_fips, year;
