import logging
import os

from slack_bolt import App

_LOG = logging.getLogger(__name__)


class SlackApp:
    def __init__(self):
        self.port = int(os.getenv("SLACK_PORT"))
        signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        token = os.getenv("SLACK_TOKEN")

        app = App(
            signing_secret=signing_secret,
            token=token,
        )
        self.app = app

        app.event("link_shared")(self.on_link_shared)

    def run(self):
        self.app.start(port=self.port, path="/")

    def on_link_shared(self, client, event, ack, say):
        _LOG.info("Received event: %s", event)
        ack()
