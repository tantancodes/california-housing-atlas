from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from atlas.io import DataError
from atlas.mortgage import fetch_rates, monthly_rates
from atlas.pipeline import PipelineConfig, run_pipeline
from atlas.reference import fetch_reference


def main() -> int:
    parser = argparse.ArgumentParser(description="California Housing Atlas reproducible ingestion")
    sub = parser.add_subparsers(dest="command", required=True)
    ref = sub.add_parser("reference", help="Download published aggregate summaries (no property records)")
    ref.add_argument("--output", type=Path, default=Path("data/reference"))
    fred = sub.add_parser("fred", help="Download FRED weekly mortgage CSV")
    fred.add_argument("--output", type=Path, default=Path("data/cache/mortgage.csv"))
    process = sub.add_parser("process", help="Process authorized local monthly CRMLS files")
    process.add_argument("--input", type=Path, required=True)
    process.add_argument("--output", type=Path, default=Path("data/processed"))
    process.add_argument("--start", default="2024-01")
    process.add_argument("--end", default=None)
    process.add_argument(
        "--boundaries", type=Path, help="Optional county polygons for a GeoPandas spatial join"
    )
    process.add_argument("--rates", type=Path, help="Optional previously downloaded FRED CSV")
    public = sub.add_parser("public", help="Download public ACS county estimates and Census boundaries")
    public.add_argument("--years", type=int, nargs="+", default=[2022, 2023, 2024])
    public.add_argument("--source", choices=["bulk"], default="bulk")
    public.add_argument("--output", type=Path, default=Path("data/public"))
    db = sub.add_parser("database", help="Migrate PostgreSQL and load public ACS county estimates")
    db.add_argument("--input", type=Path, default=Path("data/public/acs_counties.csv"))
    args = parser.parse_args()
    try:
        if args.command == "reference":
            fetch_reference(args.output)
            print(f"Validated reference summaries: {args.output}")
        elif args.command == "fred":
            fetch_rates(args.output)
            rates = monthly_rates(pd.read_csv(args.output))
            rates.to_csv(args.output.with_name("mortgage_monthly.csv"), index=False)
            print(f"Validated {len(rates)} mortgage months")
        elif args.command == "process":
            rates = monthly_rates(pd.read_csv(args.rates)) if args.rates else None
            manifest = run_pipeline(
                PipelineConfig(args.input, args.output, args.start, args.end, args.boundaries), rates
            )
            print(json.dumps(manifest, indent=2))
        elif args.command == "public":
            from atlas.public import fetch_public

            fetch_public(args.years, args.output, args.source)
            print(f"Validated public data: {args.output}")
        elif args.command == "database":
            from atlas.database import load_public

            print(load_public(args.input))
    except (DataError, OSError, ValueError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
