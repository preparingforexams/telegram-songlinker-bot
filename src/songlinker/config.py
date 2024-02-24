from dataclasses import dataclass
from typing import Self

from bs_config import Env


@dataclass
class Config:
    app_version: str
    telegram_api_key: str
    songlinker_api_key: str
    sentry_dsn: str | None
    enable_telemetry: bool

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            app_version=env.get_string("APP_VERSION", default="dirty"),
            telegram_api_key=env.get_string("TELEGRAM_API_KEY", required=True),
            songlinker_api_key=env.get_string("SONGLINK_API_TOKEN", required=True),
            sentry_dsn=env.get_string("SENTRY_DSN"),
            enable_telemetry=env.get_bool("ENABLE_TELEMETRY", default=False),
        )
