import logging

import click
import sentry_sdk
from bs_config import Env

from songlinker.config import Config

from . import bot

_LOG = logging.getLogger("songlinker")


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
def app() -> None:
    pass


@app.command()
@click.pass_obj
def handle_updates(obj: Config) -> None:
    bot.handle_updates(obj)


def _main() -> None:
    env = Env.load(include_default_dotenv=True)
    config = Config.from_env(env)
    _setup_logging()
    _setup_sentry(config)

    app.main(obj=config)


if __name__ == "__main__":
    _main()
