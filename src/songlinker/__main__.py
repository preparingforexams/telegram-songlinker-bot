import asyncio
import logging

import click
import sentry_sdk
import uvloop
from bs_config import Env

from songlinker.bot import Bot
from songlinker.config import Config
from songlinker.telemetry import setup_telemetry

_LOG = logging.getLogger(__package__)


def _setup_logging() -> None:
    logging.basicConfig()
    _LOG.level = logging.DEBUG


def _setup_sentry(config: Config) -> None:
    dsn = config.sentry_dsn
    if dsn is None:
        _LOG.warning("No Sentry DSN found")
        return

    sentry_sdk.init(
        dsn,
        release=config.app_version,
    )


@click.group()
@click.pass_context
def app(ctx: click.Context) -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    env = Env.load(include_default_dotenv=True)
    config = Config.from_env(env)
    _setup_logging()
    _setup_sentry(config)
    setup_telemetry(config)

    ctx.obj = config


@app.command()
@click.pass_obj
def handle_updates(obj: Config) -> None:
    bot = Bot(obj)
    bot.handle_updates()


if __name__ == "__main__":
    app()
