import logging
from collections.abc import Callable
from typing import Any, cast

import httpx
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from songlinker.config import Config
from songlinker.link_api import IoException

_API_KEY = ""
_LOG = logging.getLogger(__name__)
_client = httpx.Client(timeout=30)
HTTPXClientInstrumentor().instrument_client(_client)


def init(config: Config) -> None:
    global _API_KEY

    if _API_KEY:
        raise RuntimeError("Tried to initialize telegram library multiple times")

    _API_KEY = config.telegram_api_key


def _build_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_API_KEY}/{method}"


def _get_actual_body(response: httpx.Response) -> dict[str, Any] | list[Any]:
    response.raise_for_status()
    body = response.json()
    if body.get("ok"):
        return cast(dict[str, Any] | list[Any], body["result"])
    raise ValueError(f"Body was not ok! {body}")


def _request_updates(
    client: httpx.Client, last_update_id: int | None
) -> list[dict[str, Any]]:
    body: dict[str, Any] | None = None
    if last_update_id:
        body = {
            "offset": last_update_id + 1,
            "timeout": 10,
        }
    return cast(
        list[dict[str, Any]],
        _get_actual_body(
            client.post(
                _build_url("getUpdates"),
                json=body,
                timeout=12,
            )
        ),
    )


def handle_updates(
    should_run: Callable[[], bool],
    handler: Callable[[dict[str, Any]], None],
) -> None:
    client = httpx.Client(timeout=30)
    last_update_id: int | None = None
    while should_run():
        updates = _request_updates(client, last_update_id)
        try:
            for update in updates:
                _LOG.info(f"Received update: {update}")
                handler(update)
                last_update_id = update["update_id"]
        except IoException as e:
            _LOG.error("Could not handle update due to IO exception", exc_info=e)
        except Exception as e:
            _LOG.error("Could not handle update", exc_info=e)


def send_message(
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
    disable_web_page_preview: bool = False,
    disable_notification: bool = False,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    body = {
        "chat_id": chat_id,
        "reply_to_message_id": reply_to_message_id,
        "disable_notification": disable_notification,
        "allow_sending_without_reply": True,
        "disable_web_page_preview": disable_web_page_preview,
        "text": text,
    }

    if parse_mode:
        body["parse_mode"] = parse_mode

    return cast(
        dict[str, Any],
        _get_actual_body(
            _client.post(
                _build_url("sendMessage"),
                json=body,
            )
        ),
    )


def answer_inline_query(inline_query_id: str | int, results: list[Any]) -> None:
    _get_actual_body(
        _client.post(
            _build_url("answerInlineQuery"),
            json={
                "inline_query_id": inline_query_id,
                "results": results,
            },
        )
    )
