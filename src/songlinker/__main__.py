import logging

import click
import sentry_sdk
from bs_config import Env

from . import bot

_LOG = logging.getLogger("songlinker")


def _setup_logging() -> None:
    logging.basicConfig()
    _LOG.level = logging.DEBUG


def _setup_sentry(env: Env) -> None:
    dsn = env.get_string("SENTRY_DSN")
    if dsn is None:
        _LOG.warning("No Sentry DSN found")
        return

    sentry_sdk.init(
        dsn,
        release=env.get_string("APP_VERSION", default="dirty"),
    )


@click.group()
def app() -> None:
    pass


@app.command()
@click.pass_obj
def handle_updates(obj: Env) -> None:
    bot.handle_updates(obj)


def _main() -> None:
    env = Env.load(include_default_dotenv=True)
    _setup_logging()
    _setup_sentry(env)

    app.main(obj=env)


if __name__ == "__main__":
    _main()
