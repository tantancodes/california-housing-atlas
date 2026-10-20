CREATE TABLE IF NOT EXISTS county_estimates (
    county_fips char(5) NOT NULL CHECK (county_fips ~ '^06[0-9]{3}$'),
    county text NOT NULL,
    year smallint NOT NULL CHECK (year BETWEEN 2009 AND 2100),
    period text NOT NULL,
    median_home_value numeric CHECK (median_home_value > 0),
    home_value_moe numeric CHECK (home_value_moe >= 0),
    median_household_income numeric CHECK (median_household_income > 0),
    income_moe numeric CHECK (income_moe >= 0),
    PRIMARY KEY (county_fips, year)
);
CREATE INDEX IF NOT EXISTS county_estimates_year_idx ON county_estimates (year);
CREATE OR REPLACE VIEW county_affordability AS
SELECT *, median_home_value / NULLIF(median_household_income, 0) AS value_to_income
FROM county_estimates;
