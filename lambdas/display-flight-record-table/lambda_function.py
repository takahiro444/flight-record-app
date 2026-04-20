import json
import os
import psycopg2
from datetime import date, datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Enhancement: support per-user filtering via Cognito authorizer claims (sub/email)

def lambda_handler(event, context):
    # Extract claims if authorizer attached
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    # Support both claims (JWT authorizer) and jwt.claims (HTTP API style) if migrated later.
    claims = authorizer.get('claims') or authorizer.get('jwt', {}).get('claims', {}) or {}
    user_sub = claims.get('sub')
    user_email = claims.get('email') or claims.get('cognito:username')
    logger.info('[display-flight-record-table] Incoming request. has_user_sub=%s path=%s identitySource=%s', bool(user_sub), request_context.get('path'), authorizer.get('identitySource'))
    if claims:
        safe_claims = {k: claims[k] for k in ['sub','email','cognito:username'] if k in claims}
        logger.info('[display-flight-record-table] Claims subset: %s', safe_claims)
    else:
        logger.warning('[display-flight-record-table] No claims found in authorizer. Falling back to unfiltered query.')

    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT'],
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS']
    )
    cursor = conn.cursor()

    query_mode = 'filtered' if user_sub else 'unfiltered'
    if user_sub:
        cursor.execute("SELECT * FROM flight_record WHERE user_sub = %s ORDER BY date DESC", (user_sub,))
    else:
        cursor.execute("SELECT * FROM flight_record ORDER BY date DESC")

    rows = cursor.fetchall()
    colnames = [desc[0] for desc in cursor.description]
    result = [dict(zip(colnames, row)) for row in rows]

    cursor.close()
    conn.close()

    def default_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    # TODO implement
    response_body = {
        'records': result,
        'filtered': bool(user_sub),
        'user_sub': user_sub,
        'user_email': user_email,
        'row_count': len(result),
        'query_mode': query_mode
    }
    logger.info('[display-flight-record-table] Returning %d rows (mode=%s)', len(result), query_mode)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',  # Needed for CORS
            'Access-Control-Allow-Headers': 'Authorization,Content-Type,x-api-key',
            'Access-Control-Allow-Methods': 'GET,OPTIONS',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(response_body, default=default_serializer)
    }
