import logging
import os

import click
import sentry_sdk

from . import bot

_LOG = logging.getLogger("songlinker")


def _setup_logging() -> None:
    logging.basicConfig()
    _LOG.level = logging.DEBUG


def _setup_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        _LOG.warning("No Sentry DSN found")
        return

    sentry_sdk.init(
        dsn,
        release=os.getenv("BUILD_SHA") or "dirty",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
    )


@click.group()
def app() -> None:
    pass


@app.command()
def handle_updates() -> None:
    bot.handle_updates()


if __name__ == "__main__":
    _setup_logging()
    _setup_sentry()

    app.main()
