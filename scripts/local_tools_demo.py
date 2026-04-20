#!/usr/bin/env python3
"""
Local tools demo without Strands SDK.
Combines stats_overview and monthly_summary(2024) for the given USER_SUB and prints a concise answer.

Env:
  USER_SUB (required)
  DB_DIRECT_* (optional, for local tunnel)
"""
import os
import sys
from datetime import datetime

BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "talk-to-flight-record-mcp-backend")
sys.path.insert(0, os.path.abspath(BACKEND_PATH))

from db import stats_overview, monthly_summary  # type: ignore


def _require(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def main() -> None:
    user_sub = _require("USER_SUB")
    year = int(os.environ.get("YEAR", "2024"))

    so = stats_overview(user_sub)
    ms = monthly_summary(user_sub, year)

    # Build a friendly summary
    months = ms.get("months", [])
    top3 = ", ".join(
        f"{m['month']:02d}:{m['total_miles']}mi/{m['flight_count']} flights" for m in months[:3]
    )
    ans = (
        f"You have {so['total_flights']} total flights and {so['total_miles']} total miles "
        f"from {so['first_flight_date']} to {so['last_flight_date']}. Average miles/flight: "
        f"{round(so['average_miles_per_flight'], 1)}.\n"
        f"For {year}, total {ms['year_total_miles']} miles across {ms['year_flight_count']} flights."
    )
    if top3:
        ans += f" First 3 months: {top3}."

    print(ans)


if __name__ == "__main__":
    main()
