"""
Alternative DB connection using direct env var credentials (bypasses Secrets Manager).
Useful for local testing when DB_SECRET_ARN is not available.
Requires: DB_HOST, DB_USER, DB_PASSWORD env vars (DB_NAME and DB_PORT optional).
"""
import os
import psycopg2
import logging

logger = logging.getLogger(__name__)

def get_connection_direct():
    """
    Connect to database using environment variable credentials.
    """
    logger.info("[DB] Connecting with direct credentials using psycopg2")
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            port=int(os.environ.get('DB_PORT', 5432)),
            database=os.environ.get('DB_NAME', 'postgres'),
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            connect_timeout=30,
            application_name="agentcore-email-parser",
        )
        logger.info("[DB] psycopg2 connection successful")
        return conn
    except Exception as e:
        logger.error(f"[DB] Connection failed: {type(e).__name__}: {str(e)}")
        raise
