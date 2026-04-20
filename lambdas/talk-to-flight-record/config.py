import os
from dataclasses import dataclass

@dataclass
class Settings:
    db_secret_arn: str
    bedrock_model_id: str
    max_tool_rows: int
    enable_streaming: bool
    log_level: str
    stage: str
    mcp_enable_planning: bool
    plan_max_tokens: int
    answer_max_tokens: int
    cost_log_enabled: bool
    db_connect_timeout: int
    db_app_name: str
    rate_limit_enable: bool
    rate_limit_user_daily_calls: int


def load_settings() -> Settings:
    def _int_env(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None or raw.strip() == "":
            return default
        try:
            return int(raw)
        except Exception:
            return default

    return Settings(
        db_secret_arn=os.environ.get("DB_SECRET_ARN", ""),
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
        max_tool_rows=_int_env("MAX_TOOL_ROWS", 100),
        enable_streaming=os.environ.get("ENABLE_STREAMING", "false").lower() == "true",
        log_level=os.environ.get("LOG_LEVEL", "info"),
        stage=os.environ.get("STAGE", "dev"),
        mcp_enable_planning=os.environ.get("MCP_ENABLE_PLANNING", "true").lower() == "true",
        plan_max_tokens=_int_env("PLAN_MAX_TOKENS", 300),
        answer_max_tokens=_int_env("ANSWER_MAX_TOKENS", 400),
        cost_log_enabled=os.environ.get("COST_LOG_ENABLED", "true").lower() == "true",
        db_connect_timeout=_int_env("DB_CONNECT_TIMEOUT_SECONDS", 3),
        db_app_name=os.environ.get("DB_APP_NAME", "flight-mcp"),
        rate_limit_enable=os.environ.get("RATE_LIMIT_ENABLE", "true").lower() == "true",
        rate_limit_user_daily_calls=_int_env("RATE_LIMIT_USER_DAILY_CALLS", 100),
    )

settings = load_settings()
