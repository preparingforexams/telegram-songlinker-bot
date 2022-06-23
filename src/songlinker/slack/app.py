import os

from slack_bolt import App


class SlackApp:
    def __init__(self):
        self.port = int(os.getenv("SLACK_PORT"))
        signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        token = os.getenv("SLACK_TOKEN")
        self.app = App(
            signing_secret=signing_secret,
            token=token,
        )

    def run(self):
        # TODO: implement
        self.app.start(port=self.port, path="/")
