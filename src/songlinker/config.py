from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from bs_nats_updater import NatsConfig

if TYPE_CHECKING:
    from bs_config import Env


@dataclass(frozen=True, kw_only=True)
class Config:
    app_version: str
    nats: NatsConfig
    telegram_api_key: str
    songlinker_api_key: str
    sentry_dsn: str | None
    enable_telemetry: bool

    @classmethod
    def from_env(cls, env: Env) -> Self:
        return cls(
            app_version=env.get_string("app-version", default="dirty"),
            nats=NatsConfig.from_env(env / "nats"),
            telegram_api_key=env.get_string("telegram-token", required=True),
            songlinker_api_key=env.get_string("songlink-api-token", required=True),
            sentry_dsn=env.get_string("sentry-dsn"),
            enable_telemetry=env.get_bool("enable-telemetry", default=False),
        )
