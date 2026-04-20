import os
from dataclasses import dataclass

@dataclass
class Settings:
    db_secret_arn: str
    bedrock_model_id: str
    answer_max_tokens: int
    db_connect_timeout: int
    db_app_name: str
    log_level: str


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
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"),
        answer_max_tokens=_int_env("ANSWER_MAX_TOKENS", 800),
        db_connect_timeout=_int_env("DB_CONNECT_TIMEOUT_SECONDS", 3),
        db_app_name=os.environ.get("DB_APP_NAME", "email-parser-agent"),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )

settings = load_settings()
