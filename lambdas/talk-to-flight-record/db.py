import json
import os
import pg8000
import boto3
from typing import Any, Dict, List, Tuple
from config import settings

_secrets_cache: Dict[str, Dict[str, Any]] = {}


def _load_secret() -> Dict[str, Any]:
    if not settings.db_secret_arn:
        raise RuntimeError("DB_SECRET_ARN not set in environment")
    if settings.db_secret_arn in _secrets_cache:
        return _secrets_cache[settings.db_secret_arn]
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=settings.db_secret_arn)
    secret_dict = json.loads(resp["SecretString"])
    _secrets_cache[settings.db_secret_arn] = secret_dict
    return secret_dict


def get_connection():
    """Create a DB connection.

    Local testing convenience: if environment variables for a direct connection are set,
    use them instead of Secrets Manager.

    Set the following to use a direct connection (e.g., via SSH/SSM port forward):
      - DB_DIRECT_HOST (required)
      - DB_DIRECT_PORT (optional, defaults to 5432)
      - DB_DIRECT_NAME or DB_NAME (required)
      - DB_DIRECT_USER or DB_USER (required)
      - DB_DIRECT_PASSWORD or DB_PASSWORD (required)
    """

    direct_host = os.environ.get("DB_DIRECT_HOST")
    if direct_host:
        database = os.environ.get("DB_DIRECT_NAME") or os.environ.get("DB_NAME")
        user = os.environ.get("DB_DIRECT_USER") or os.environ.get("DB_USER")
        password = os.environ.get("DB_DIRECT_PASSWORD") or os.environ.get("DB_PASSWORD")
        port = int(os.environ.get("DB_DIRECT_PORT", "5432"))

        missing = [k for k, v in {
            "DB_DIRECT_NAME/DB_NAME": database,
            "DB_DIRECT_USER/DB_USER": user,
            "DB_DIRECT_PASSWORD/DB_PASSWORD": password,
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required env vars for direct DB connection: {', '.join(missing)}")

        return pg8000.connect(
            host=direct_host,
            port=port,
            database=database,
            user=user,
            password=password,
            timeout=settings.db_connect_timeout,
            application_name=settings.db_app_name,
        )

    s = _load_secret()
    # pg8000 uses 'database' param name; supports application_name.
    conn = pg8000.connect(
        host=s["host"],
        port=int(s.get("port", 5432)),
        database=s["database"],
        user=s["user"],
        password=s["password"],
        timeout=settings.db_connect_timeout,
        application_name=settings.db_app_name,
    )
    return conn

# ------------------------ Query Helpers ----------------------------

def mileage_range(user_sub: str, start_date: str, end_date: str) -> Dict[str, Any]:
    sql = """
    SELECT COALESCE(SUM(flight_mileage),0) AS total_miles,
           COUNT(*) AS flight_count
      FROM flight_record
     WHERE user_sub = %s AND date >= %s AND date < %s
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, (user_sub, start_date, end_date))
    total_miles, flight_count = cur.fetchone()
    cur.close(); conn.close()
    return {
        "total_miles": int(total_miles),
        "flight_count": int(flight_count),
        "start_date": start_date,
        "end_date": end_date,
    }


def monthly_summary(user_sub: str, year: int) -> Dict[str, Any]:
    sql = """
    SELECT EXTRACT(MONTH FROM date)::int AS month,
           COALESCE(SUM(flight_mileage),0) AS total_miles,
           COUNT(*) AS flight_count
      FROM flight_record
     WHERE user_sub = %s AND EXTRACT(YEAR FROM date) = %s
     GROUP BY month
     ORDER BY month
    """
    conn = get_connection(); cur = conn.cursor()
    cur.execute(sql, (user_sub, year))
    rows = cur.fetchall()
    cur.close(); conn.close()
    months = [
        {"month": r[0], "total_miles": int(r[1]), "flight_count": int(r[2])}
        for r in rows
    ]
    return {
        "year": year,
        "months": months,
        "year_total_miles": sum(m["total_miles"] for m in months),
        "year_flight_count": sum(m["flight_count"] for m in months),
    }


def longest_flights(user_sub: str, limit: int = 5, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    base = ["user_sub = %s"]
    params: List[Any] = [user_sub]
    if start_date:
        base.append("date >= %s"); params.append(start_date)
    if end_date:
        base.append("date < %s"); params.append(end_date)
    where_clause = " AND ".join(base)
    sql = f"""
    SELECT date, flight_iata, flight_mileage, flight_duration
      FROM flight_record
     WHERE {where_clause}
     ORDER BY flight_mileage DESC NULLS LAST
     LIMIT %s
    """
    params.append(limit)
    conn = get_connection(); cur = conn.cursor()
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    cur.close(); conn.close()
    flights = [
        {
            "date": str(r[0]),
            "flight_iata": r[1],
            "flight_mileage": r[2],
            "flight_duration": r[3]
        } for r in rows
    ]
    return {"limit": limit, "count": len(flights), "flights": flights}


def stats_overview(user_sub: str) -> Dict[str, Any]:
    sql = """
    SELECT MIN(date) AS first_date,
           MAX(date) AS last_date,
           COUNT(*) AS total_flights,
           COALESCE(SUM(flight_mileage),0) AS total_miles
      FROM flight_record
     WHERE user_sub = %s
    """
    conn = get_connection(); cur = conn.cursor()
    cur.execute(sql, (user_sub,))
    first_date, last_date, total_flights, total_miles = cur.fetchone()
    cur.close(); conn.close()
    avg_miles = int(total_miles) / total_flights if total_flights else 0
    return {
        "first_flight_date": str(first_date) if first_date else None,
        "last_flight_date": str(last_date) if last_date else None,
        "total_flights": int(total_flights),
        "total_miles": int(total_miles),
        "average_miles_per_flight": avg_miles,
    }


def recent_flights(user_sub: str, limit: int = 10) -> Dict[str, Any]:
    """
    Return the most recent flights for a user.

    NOTE: Schema divergence:
    Analytical helpers above assume columns: date, flight_mileage, flight_duration, flight_iata, etc.
    Ingestion lambda (retrieve_store_flight_data.py) documents schema with: id, flight_date, origin, destination,
    aircraft_type, user_sub, user_email, created_at.
    This helper uses that ingestion-oriented subset.
    If both schemas exist (legacy vs new), consider creating a VIEW or migrating to a unified column set.
    """
    # Prefer lowercase 'date' column; if missing, fallback to flight_date.
    # Select columns that exist per introspection: date, departure_iata, arrival_iata, airline_name, flight_iata
    sql_date = """
    SELECT date AS d, departure_iata, arrival_iata, airline_name, flight_iata
      FROM flight_record
     WHERE user_sub = %s
     ORDER BY d DESC
     LIMIT %s
    """
    sql_flight_date = """
    SELECT flight_date AS d, departure_iata, arrival_iata, airline_name, flight_iata
      FROM flight_record
     WHERE user_sub = %s
     ORDER BY d DESC
     LIMIT %s
    """
    sql_Date_quoted = """
    SELECT "Date" AS d, departure_iata, arrival_iata, airline_name, flight_iata
      FROM flight_record
     WHERE user_sub = %s
     ORDER BY d DESC
     LIMIT %s
    """
    conn = get_connection(); cur = conn.cursor()
    rows: List[Tuple] = []
    try:
        cur.execute(sql_date, (user_sub, limit))
        rows = cur.fetchall()
    except Exception:
        # Fallback when 'date' column doesn't exist; clear failed transaction first.
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            cur.execute(sql_flight_date, (user_sub, limit))
            rows = cur.fetchall()
        except Exception:
            # Final fallback: case-sensitive quoted column "Date"
            try:
                conn.rollback()
            except Exception:
                pass
            cur.execute(sql_Date_quoted, (user_sub, limit))
            rows = cur.fetchall()
    finally:
        cur.close(); conn.close()
    flights = [
        {
            "date": str(r[0]),
            "departure_iata": r[1],
            "arrival_iata": r[2],
            "airline_name": r[3],
            "flight_iata": r[4],
        }
        for r in rows
    ]
    return {"limit": limit, "count": len(flights), "flights": flights}


def list_flight_record_columns() -> Dict[str, Any]:
    """
    Introspect the flight_record table and return available columns.
    Useful for diagnosing schema mismatches across environments.
    """
    sql = """
    SELECT column_name, data_type
      FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'flight_record'
     ORDER BY ordinal_position
    """
    conn = get_connection(); cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {
        "columns": [{"name": r[0], "type": r[1]} for r in rows],
        "has_date": any(r[0] == 'date' for r in rows),
        "has_flight_date": any(r[0] == 'flight_date' for r in rows),
        "has_Date_quoted": any(r[0] == 'Date' for r in rows),
    }


def get_db_settings() -> Dict[str, Any]:
    """
    Return key PostgreSQL settings to confirm connectivity and configuration.
    Includes server_version, current_user, search_path, timezone, and ssl status.
    """
    queries = {
        "server_version": "SHOW server_version",
        "current_user": "SELECT current_user",
        "search_path": "SHOW search_path",
        "TimeZone": "SHOW TimeZone",
        "ssl": "SHOW ssl",
    }
    conn = get_connection(); cur = conn.cursor()
    out: Dict[str, Any] = {}
    for key, q in queries.items():
        cur.execute(q)
        val = cur.fetchone()
        out[key] = val[0] if val else None
    # Also return connection target info for visibility, preferring direct mode env if set
    cur.close(); conn.close()

    direct_host = os.environ.get("DB_DIRECT_HOST")
    if direct_host:
        out["database"] = os.environ.get("DB_DIRECT_NAME") or os.environ.get("DB_NAME")
        out["host"] = direct_host
        try:
            out["port"] = int(os.environ.get("DB_DIRECT_PORT", "5432"))
        except Exception:
            out["port"] = 5432
        out["user"] = os.environ.get("DB_DIRECT_USER") or os.environ.get("DB_USER")
    else:
        # Fallback to Secrets Manager only when direct mode is not used
        secret = _load_secret()
        out["database"] = secret.get("database")
        out["host"] = secret.get("host")
        out["port"] = int(secret.get("port", 5432))
        out["user"] = secret.get("user")
    return out
