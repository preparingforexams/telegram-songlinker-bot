import logging
import os
import uuid
from collections import namedtuple
from dataclasses import dataclass
from typing import Any, Iterable, Self, cast
from urllib import parse

from songlinker import telegram
from songlinker.link_api import IoException, LinkApi, Platform, SongData

_LOG = logging.getLogger(__name__)


_api_key: str = os.getenv("SONGLINK_API_TOKEN")  # type: ignore


def handle_updates() -> None:
    if not _api_key:
        raise ValueError("SONGLINK_API_TOKEN is not set")
    telegram.check()
    telegram.handle_updates(
        lambda: True,
        _handle_update,
    )


def _handle_update(update: dict[str, Any]) -> None:
    match update:
        case {"message": message} if message:
            _handle_message(message)
        case {"inline_query": inline_query} if inline_query:
            _handle_query(inline_query)


class SongResult:
    def __init__(self, data: SongData, *, is_spoiler: bool):
        self.data = data
        self.is_spoiler = is_spoiler

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

        result = f"{name}\n[{links}]"
        if self.is_spoiler:
            return f"<tg-spoiler>{result}</tg-spoiler>"
        else:
            return result

    def to_inline_result(self) -> dict[str, Any]:
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


def _handle_query(query: dict[str, Any]) -> None:
    query_text: str = query["query"].strip()
    song_result: SongResult | None = None
    if query_text:
        try:
            url = parse.urlparse(query_text)
            if url.scheme == "http" or url.scheme == "https":
                with LinkApi(api_key=_api_key) as api:
                    song_result = _build_result(api, EntityMatch(url=query_text))
        except ValueError:
            pass
    results = [song_result.to_inline_result()] if song_result else []
    telegram.answer_inline_query(
        inline_query_id=query["id"],
        results=results,
    )


@dataclass(frozen=True)
class EntityMatch:
    url: str | None = None
    is_spoiler: bool = False

    def require_url(self) -> str:
        url = self.url
        if not url:
            raise ValueError("url is None")

        return url

    def merge(self, other: Self) -> Self:
        if other.url is not None and self.url is not None:
            raise ValueError("Can't overwrite url")

        if other.is_spoiler and self.is_spoiler:
            raise ValueError("Can't overwrite is_spoiler")

        return cast(
            Self,
            EntityMatch(
                url=other.url or self.url,
                is_spoiler=other.is_spoiler or self.is_spoiler,
            ),
        )


EntityPosition = namedtuple("EntityPosition", ["offset", "length"])


def _get_text(message: dict[str, Any], position: EntityPosition) -> str:
    text: str = cast(str, message["text"])
    return text[position.offset : position.offset + position.length]


def _handle_message(message: dict[str, Any]) -> None:
    chat = message["chat"]
    entities = message.get("entities")
    if not entities:
        _LOG.debug("No entities in message")
        return

    entity_by_position: dict[EntityPosition, EntityMatch] = {}

    for entity in entities:
        position = EntityPosition(
            offset=entity["offset"],
            length=entity["length"],
        )

        entity_match: EntityMatch
        match entity["type"]:
            case "url":
                url = _get_text(message, position)
                entity_match = EntityMatch(url=url)
            case "text_link":
                entity_match = EntityMatch(url=entity["url"])
            case "spoiler":
                entity_match = EntityMatch(is_spoiler=True)
            case _:
                continue

        existing_match = entity_by_position.get(position)
        if existing_match is None:
            entity_by_position[position] = entity_match
        else:
            entity_by_position[position] = existing_match.merge(entity_match)

    _LOG.debug("Got %d entity matches", len(entity_by_position))

    entity_matches = [
        match
        for _, match in sorted(
            entity_by_position.items(),
            key=lambda t: t[0].offset,
        )
        if match.url is not None and _not_song_link(match.require_url())
    ]

    if not entity_matches:
        _LOG.info("No URLs after filtering")
        return

    with LinkApi(api_key=_api_key) as api:
        results = (_build_result(api, match) for match in entity_matches)
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


def _build_result(api: LinkApi, entity: EntityMatch) -> SongResult | None:
    try:
        data = api.lookup_links(entity.require_url())
    except IoException as e:
        _LOG.error(
            f"Could not look up data for URL {entity.require_url()}",
            exc_info=e,
        )
        return None

    if data is None:
        return None

    return SongResult(data, is_spoiler=entity.is_spoiler)


def _build_message(formatted_links: Iterable[str]) -> str:
    return "\n\n".join(formatted_links)
