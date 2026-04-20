import json
import os
import pg8000
import boto3
from typing import Any, Dict
from config import settings

_secrets_cache: Dict[str, Dict[str, Any]] = {}


def _load_secret() -> Dict[str, Any]:
    if not settings.db_secret_arn:
        raise RuntimeError("DB_SECRET_ARN not set in environment")
    if settings.db_secret_arn in _secrets_cache:
        print(f"[DEBUG] Using cached secret for {settings.db_secret_arn}")
        return _secrets_cache[settings.db_secret_arn]
    print(f"[DEBUG] Loading secret from Secrets Manager: {settings.db_secret_arn}")
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=settings.db_secret_arn)
    secret_dict = json.loads(resp["SecretString"])
    print(f"[DEBUG] Secret loaded successfully, keys: {list(secret_dict.keys())}")
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
    print(f"[DEBUG] Connecting to DB at {s['host']}:{s.get('port', 5432)}/{s['database']}")
    conn = pg8000.connect(
        host=s["host"],
        port=int(s.get("port", 5432)),
        database=s["database"],
        user=s["user"],
        password=s["password"],
        timeout=settings.db_connect_timeout,
        application_name=settings.db_app_name,
    )
    print(f"[DEBUG] Database connection successful")
    return conn
