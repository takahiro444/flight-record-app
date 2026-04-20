#!/usr/bin/env python3
"""
Quick DB connectivity sanity check using existing db.py helpers.
Requires DB_DIRECT_* env vars and USER_SUB.
"""
import os
import sys

BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "lambdas", "talk-to-flight-record-mcp-backend")
sys.path.insert(0, os.path.abspath(BACKEND_PATH))

from db import get_db_settings, stats_overview, monthly_summary  # type: ignore


def _require(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def main() -> None:
    user_sub = _require("USER_SUB")
    year = int(os.environ.get("YEAR", "2024"))

    print("Checking DB settings...")
    try:
        s = get_db_settings()
        # Hide sensitive fields
        redacted = dict(s)
        for k in ("user",):
            if k in redacted and redacted[k]:
                redacted[k] = "***"
        print({k: redacted[k] for k in ("server_version", "search_path", "TimeZone", "ssl", "database", "host", "port", "user") if k in redacted})
    except Exception as e:
        print("DB settings error:", repr(e))
        raise

    print("\nRunning stats_overview...")
    try:
        so = stats_overview(user_sub)
        print(so)
    except Exception as e:
        print("stats_overview error:", repr(e))
        raise

    print(f"\nRunning monthly_summary({year})...")
    try:
        ms = monthly_summary(user_sub, year)
        # truncate months for brevity
        preview = dict(ms)
        preview["months"] = preview.get("months", [])[:3]
        print(preview)
    except Exception as e:
        print("monthly_summary error:", repr(e))
        raise


if __name__ == "__main__":
    main()
