import logging
import os
import uuid
from typing import Iterable
from urllib import parse

from songlinker import telegram
from songlinker.link_api import IoException, LinkApi, Platform, SongData

_LOG = logging.getLogger(__name__)


_api_key: str = os.getenv("SONGLINK_API_TOKEN")  # type: ignore


def handle_updates():
    if not _api_key:
        raise ValueError("SONGLINK_API_TOKEN is not set")
    telegram.check()
    telegram.handle_updates(
        lambda: True,
        _handle_update,
    )


def _handle_update(update: dict) -> None:
    match update:
        case {"message": message} if message:
            _handle_message(message)
        case {"inline_query": inline_query} if inline_query:
            _handle_query(inline_query)


class SongResult:
    def __init__(self, data: SongData):
        self.data = data

    @staticmethod
    def _format_link(platform: Platform, link: str) -> str:
        return f'<a href="{link}">{platform.value.name}</a>'

    def to_message_content(self) -> str:
        title = self.data.metadata.title
        artist = self.data.metadata.artist_name
        name = title if artist is None else f"{artist} - {title}"
        links = ", ".join(
            self._format_link(platform, link)
            for platform, link in self.data.links.items()
        )

        return f"{name}\n[{links}]"

    def to_inline_result(self) -> dict:
        artist = self.data.metadata.artist_name
        title = self.data.metadata.title
        result_title = self.data.links.page
        if artist and title:
            result_title = f"{artist} - {title}"
        return {
            "type": "article",
            "id": _random_id(),
            "title": result_title,
            "url": self.data.links.page,
            "input_message_content": {
                "message_text": self.to_message_content(),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        }


def _random_id() -> str:
    return str(uuid.uuid4())


def _handle_query(query: dict) -> None:
    query_text: str = query["query"].strip()
    song_result: SongResult | None = None
    if query_text:
        try:
            url = parse.urlparse(query_text)
            if url.scheme == "http" or url.scheme == "https":
                with LinkApi(api_key=_api_key) as api:
                    song_result = _build_result(api, query_text)
        except ValueError:
            pass
    results = [song_result.to_inline_result()] if song_result else []
    telegram.answer_inline_query(
        inline_query_id=query["id"],
        results=results,
    )


def _handle_message(message: dict):
    chat = message["chat"]
    entities = message.get("entities")
    if not entities:
        _LOG.debug("No entities in message")
        return

    urls = set()

    for entity in entities:
        entity_type = entity["type"]
        if entity_type == "url":
            offset = int(entity["offset"])
            length = int(entity["length"])
            url = message["text"][offset : offset + length]
            urls.add(url)
        elif entity_type == "text_link":
            urls.add(entity["url"])

    _LOG.debug("Got %d URLs", len(urls))

    urls = {url for url in urls if _not_song_link(url)}

    if not urls:
        _LOG.info("No URLs after filtering")
        return

    with LinkApi(api_key=_api_key) as api:
        results = (_build_result(api, url) for url in urls)
        message_contents = [
            result.to_message_content() for result in results if result is not None
        ]

    if not message_contents:
        _LOG.info("No known songs found")
        return

    telegram.send_message(
        chat_id=chat["id"],
        reply_to_message_id=message["message_id"],
        disable_web_page_preview=True,
        disable_notification=True,
        text=_build_message(message_contents),
        parse_mode="HTML",
    )


def _not_song_link(url: str) -> bool:
    return "song.link" not in url


def _build_result(api: LinkApi, url: str) -> SongResult | None:
    try:
        data = api.lookup_links(url)
    except IoException as e:
        _LOG.error(f"Could not look up data for URL {url}", exc_info=e)
        return None

    if data is None:
        return None

    return SongResult(data)


def _build_message(formatted_links: Iterable[str]) -> str:
    return "\n\n".join(formatted_links)
