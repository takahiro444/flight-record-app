"""Lambda handler example for storing flight data with user attribution.
Assumptions:
- API Gateway REST API uses Lambda Proxy integration so event.requestContext.authorizer.claims is populated.
- Cognito authorizer passes standard OIDC claims including: sub, email.
- RDS Postgres credentials provided via environment variables: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD.
- Table flight_record has (id serial pk, flight_date date, origin text, destination text, aircraft_type text, user_sub text, user_email text, created_at timestamptz default now()).

If columns user_sub / user_email were just added, run (once):
ALTER TABLE flight_record ADD COLUMN user_sub text;\n
ALTER TABLE flight_record ADD COLUMN user_email text;\n
CREATE INDEX IF NOT EXISTS idx_flight_record_user_sub ON flight_record(user_sub);

"""

import json
import os
import logging
from datetime import datetime

import psycopg2
import psycopg2.extras

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Connection reuse for performance (outside handler)
_pg_conn = None


def get_db_conn():
    global _pg_conn
    if _pg_conn and _pg_conn.closed == 0:
        return _pg_conn
    _pg_conn = psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", 5432)),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        connect_timeout=5,
    )
    _pg_conn.autocommit = True
    return _pg_conn


def extract_claims(event):
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    # For Cognito REST API authorizer with 'Token Source' = Authorization header
    claims = authorizer.get("claims", {}) or authorizer.get("jwt" , {}).get("claims", {}) if isinstance(authorizer.get("jwt"), dict) else {}
    user_sub = claims.get("sub")
    # email claim may be lowercase or have cognito: prefix depending on pool settings
    user_email = claims.get("email") or claims.get("cognito:username")
    return user_sub, user_email, claims


def parse_body(event):
    body = event.get("body")
    if body is None:
        return {}
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON body; returning empty dict")
        return {}


def validate_payload(payload):
    required = ["flight_date", "origin", "destination", "aircraft_type"]
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    # Basic date sanity
    try:
        datetime.strptime(payload["flight_date"], "%Y-%m-%d")
    except Exception:
        raise ValueError("flight_date must be YYYY-MM-DD")
    return True


def insert_record(conn, payload, user_sub, user_email):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        sql = """
        INSERT INTO flight_record (flight_date, origin, destination, aircraft_type, user_sub, user_email)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, flight_date, origin, destination, aircraft_type, user_sub, user_email, created_at
        """
        cur.execute(sql, (
            payload["flight_date"],
            payload["origin"],
            payload["destination"],
            payload["aircraft_type"],
            user_sub,
            user_email,
        ))
        return cur.fetchone()


def build_response(status, body, headers=None):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ALLOW_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Authorization,Content-Type,x-api-key",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
            **(headers or {}),
        },
        "body": json.dumps(body),
    }


def handler(event, context):
    logger.info("Event received: %s", json.dumps({k: event.get(k) for k in ["httpMethod", "path", "requestContext"]}))

    if event.get("httpMethod") == "OPTIONS":
        return build_response(200, {"ok": True})

    try:
        user_sub, user_email, claims = extract_claims(event)
        logger.info("Extracted claims: sub=%s email=%s", user_sub, user_email)

        if event.get("httpMethod") == "POST":
            payload = parse_body(event)
            validate_payload(payload)
            conn = get_db_conn()
            record = insert_record(conn, payload, user_sub, user_email)
            return build_response(201, {"record": record})

        elif event.get("httpMethod") == "GET":
            # Example: list records filtered by user_sub if present
            conn = get_db_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if user_sub:
                    cur.execute("SELECT id, flight_date, origin, destination, aircraft_type, user_sub, user_email, created_at FROM flight_record WHERE user_sub = %s ORDER BY flight_date DESC LIMIT 200", (user_sub,))
                else:
                    cur.execute("SELECT id, flight_date, origin, destination, aircraft_type, user_sub, user_email, created_at FROM flight_record ORDER BY flight_date DESC LIMIT 200")
                rows = cur.fetchall()
            return build_response(200, {"records": rows, "filtered": bool(user_sub)})

        else:
            return build_response(405, {"error": "Method not allowed"})

    except ValueError as ve:
        logger.warning("Validation error: %s", ve)
        return build_response(400, {"error": str(ve)})
    except psycopg2.Error as db_err:
        logger.exception("Database error")
        return build_response(500, {"error": "Database error", "detail": str(db_err)})
    except Exception as e:
        logger.exception("Unhandled error")
        return build_response(500, {"error": "Internal server error", "detail": str(e)})


# Local test harness (invoked manually, not by AWS Lambda runtime) ---------------------------------
if __name__ == "__main__":
    # Simulate a POST event with claims
    test_event = {
        "httpMethod": "POST",
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "12345678-aaaa-bbbb-cccc-1234567890ab",
                    "email": "pilot@example.com"
                }
            }
        },
        "body": json.dumps({
            "flight_date": "2025-11-14",
            "origin": "SEA",
            "destination": "SFO",
            "aircraft_type": "B738"
        })
    }
    print("Would insert (DB connection skipped in dry run mode)")
    # Dry run: comment out actual handler invocation unless DB env vars are set
    # print(handler(test_event, None))
    user_sub, user_email, _ = extract_claims(test_event)
    print("Extracted user_sub:", user_sub, "email:", user_email)
