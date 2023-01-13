import logging
import os
from typing import Optional, List, Callable

import requests

_API_KEY = os.getenv("TELEGRAM_API_KEY")
_LOG = logging.getLogger(__name__)
_session = requests.Session()


def check():
    if not _API_KEY:
        raise ValueError("Missing TELEGRAM_API_KEY")


def _build_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_API_KEY}/{method}"


def _get_actual_body(response: requests.Response):
    response.raise_for_status()
    body = response.json()
    if body.get("ok"):
        return body["result"]
    raise ValueError(f"Body was not ok! {body}")


def _request_updates(last_update_id: Optional[int]) -> List[dict]:
    body: Optional[dict] = None
    if last_update_id:
        body = {
            "offset": last_update_id + 1,
            "timeout": 10,
        }
    return _get_actual_body(
        _session.post(
            _build_url("getUpdates"),
            json=body,
            timeout=12,
        )
    )


def handle_updates(should_run: Callable[[], bool], handler: Callable[[dict], None]):
    last_update_id: Optional[int] = None
    while should_run():
        updates = _request_updates(last_update_id)
        try:
            for update in updates:
                _LOG.info(f"Received update: {update}")
                handler(update)
                last_update_id = update["update_id"]
        except Exception as e:
            _LOG.error("Could not handle update", exc_info=e)


def send_message(
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = False,
    disable_notification: bool = False,
) -> dict:
    return _get_actual_body(
        _session.post(
            _build_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "reply_to_message_id": reply_to_message_id,
                "disable_notification": disable_notification,
                "allow_sending_without_reply": True,
                "disable_web_page_preview": disable_web_page_preview,
                "text": text,
            },
            timeout=10,
        )
    )


def answer_inline_query(inline_query_id: str | int, results: list):
    return _get_actual_body(
        _session.post(
            _build_url("answerInlineQuery"),
            json={
                "inline_query_id": inline_query_id,
                "results": results,
            },
            timeout=10,
        )
    )
