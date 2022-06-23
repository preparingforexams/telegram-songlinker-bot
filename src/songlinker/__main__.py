import logging
import os

import click
import sentry_sdk

from . import bot
from .slack.app import SlackApp

_LOG = logging.getLogger("songlinker")


def _setup_logging():
    logging.basicConfig()
    _LOG.level = logging.DEBUG


def _setup_sentry():
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
def app():
    pass


@app.command()
def handle_updates():
    bot.handle_updates()


@app.command()
def run_slack_app():
    slack = SlackApp()
    slack.run()


if __name__ == "__main__":
    _setup_logging()
    _setup_sentry()

    app.main()
