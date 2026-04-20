"""Simple DynamoDB-backed rate limiting for Bedrock calls.

Table design (proposed):
  Name: flight-record-rate-limit (configure via env RATE_LIMIT_TABLE)
  PK: pk (string) -> user_sub or phase key
  SK: sk (string) -> YYYY-MM-DD
  Attributes: calls (number), updated_at (ISO8601)

Implements a daily per-user counter. If calls >= limit, further Bedrock invocations fall back.
Fail-open behavior on missing table or transient errors (to avoid hard outages).
"""

import os
import datetime
import boto3
from botocore.exceptions import ClientError
from config import settings

_dynamo = boto3.client("dynamodb")
_table_name = os.environ.get("RATE_LIMIT_TABLE", "flight-record-rate-limit")


def check_and_increment(key: str) -> bool:
    """Return True if under limit (and increment). False if limit exceeded.

    key can be a user_sub or synthetic phase key.
    """
    if not settings.rate_limit_enable:
        return True
    if not key:
        return True
    limit = settings.rate_limit_user_daily_calls
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    now_iso = datetime.datetime.utcnow().isoformat()
    try:
        _dynamo.update_item(
            TableName=_table_name,
            Key={"pk": {"S": key}, "sk": {"S": today}},
            UpdateExpression="SET #c = if_not_exists(#c, :zero) + :inc, updated_at = :now",
            ExpressionAttributeNames={"#c": "calls"},
            ExpressionAttributeValues={":inc": {"N": "1"}, ":zero": {"N": "0"}, ":now": {"S": now_iso}, ":limit": {"N": str(limit)}},
            ConditionExpression="attribute_not_exists(#c) OR #c < :limit",
            ReturnValues="UPDATED_NEW",
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        return True  # fail-open on other errors
