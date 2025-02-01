import logging
import uuid
from collections import OrderedDict, namedtuple
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self, cast
from urllib import parse

from opentelemetry import trace
from opentelemetry.trace import Span

from songlinker import telegram
from songlinker.config import Config
from songlinker.link_api import IoException, LinkApi, Platform, SongData

_LOG = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_api_key = ""


def handle_updates(config: Config) -> None:
    global _api_key
    if _api_key:
        raise RuntimeError("Already running")
    _api_key = config.songlinker_api_key

    telegram.init(config)
    telegram.handle_updates(
        lambda: True,
        _handle_update,
    )


def _handle_update(update: dict[str, Any]) -> None:
    with tracer.start_as_current_span("handle_update") as span:
        span.set_attribute("telegram.update_keys", list(update.keys()))
        span.set_attribute("telegram.update_id", update["update_id"])

        match update:
            case {"message": message} if message:
                _collect_message_span_attributes(span, message)
                _handle_message(message)
            case {"inline_query": inline_query} if inline_query:
                _collect_inline_query_span_attributes(span, inline_query)
                _handle_query(inline_query)


def _collect_message_span_attributes(span: Span, message: dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    span.set_attribute("telegram.chat_id", chat_id)
    user_id = message["from"]["id"]
    span.set_attribute("telegram.user_id", user_id)
    time = datetime.fromtimestamp(
        message["date"],
        tz=UTC,
    )
    span.set_attribute("telegram.message_timestamp", time.isoformat())
    message_id = message["message_id"]
    span.set_attribute("telegram.message_id", message_id)


def _collect_inline_query_span_attributes(span: Span, query: dict[str, Any]) -> None:
    query_id = query["id"]
    span.set_attribute("telegram.query_id", query_id)
    chat_type = query["chat_type"]
    span.set_attribute("telegram.chat_type", chat_type)
    user_id = query["from"]["id"]
    span.set_attribute("telegram.user_id", user_id)


class SongResult:
    def __init__(self, data: SongData, *, is_spoiler: bool):
        self.data = data
        self.is_spoiler = is_spoiler

    @staticmethod
    def _format_link(platform: Platform, link: str) -> str:
        return f'<a href="{link}">{platform.value.name}</a>'

    def to_message_content(self) -> str:
        prefix: str = ""
        if self.data.metadata.is_album:
            prefix = "<b>Album:</b> "

        title = self.data.metadata.title
        artist = self.data.metadata.artist_name
        name = title if artist is None else f"{artist} - {title}"
        links = ", ".join(
            self._format_link(platform, link)
            for platform, link in self.data.links.items()
        )

        header = f"{prefix}{name}"
        if self.is_spoiler:
            header = f"<tg-spoiler>{header}</tg-spoiler>"

        return f"{header}\n[{links}]"

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
                    song_result = _build_result(
                        api,
                        EntityMatch(
                            position=EntityPosition(offset=0, length=len(query_text)),
                            url=query_text,
                        ),
                    )
        except ValueError:
            pass
    results = [song_result.to_inline_result()] if song_result else []
    telegram.answer_inline_query(
        inline_query_id=query["id"],
        results=results,
    )


EntityPosition = namedtuple("EntityPosition", ["offset", "length"])


@dataclass(frozen=True)
class EntityMatch:
    position: EntityPosition
    url: str | None = None
    is_spoiler: bool = False

    def require_url(self) -> str:
        url = self.url
        if not url:
            raise ValueError("url is None")

        return url

    def merge(self, other: Self) -> Self:
        if other.position != self.position:
            raise ValueError("Can't merge entities with different positions")

        if other.url is not None and self.url is not None:
            raise ValueError("Can't overwrite url")

        if other.is_spoiler and self.is_spoiler:
            raise ValueError("Can't overwrite is_spoiler")

        return cast(
            Self,
            EntityMatch(
                position=self.position,
                url=other.url or self.url,
                is_spoiler=other.is_spoiler or self.is_spoiler,
            ),
        )

    def with_spoiler(self) -> Self:
        if self.is_spoiler:
            return self

        return cast(
            Self,
            EntityMatch(
                position=self.position,
                url=self.url,
                is_spoiler=True,
            ),
        )

    def contains(self, position: EntityPosition) -> bool:
        own = self.position
        if position.offset < own.offset:
            # Their start is before our start
            return False

        if (position.offset + position.length) > (own.offset + own.length):
            # Their end is after our end
            return False

        return True


def _get_text(message: dict[str, Any], position: EntityPosition) -> str:
    text: str = cast(str, message["text"])
    return text[position.offset : position.offset + position.length]


def _spoil_if_match(
    match: EntityMatch,
    spoiler_matches: list[EntityMatch],
) -> EntityMatch:
    if match.is_spoiler:
        return match

    if any(spoiler.contains(match.position) for spoiler in spoiler_matches):
        return match.with_spoiler()

    return match


def _collapse_entities(
    entity_by_position: dict[EntityPosition, EntityMatch],
) -> list[EntityMatch]:
    spoiler_matches = [
        match for match in entity_by_position.values() if match.url is None
    ]

    return [
        _spoil_if_match(match, spoiler_matches)
        for match in sorted(
            entity_by_position.values(),
            key=lambda match: match.position.offset,
        )
        if match.url is not None and _not_song_link(match.require_url())
    ]


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
                entity_match = EntityMatch(position=position, url=url)
            case "text_link":
                entity_match = EntityMatch(position=position, url=entity["url"])
            case "spoiler":
                entity_match = EntityMatch(position=position, is_spoiler=True)
            case _:
                continue

        existing_match = entity_by_position.get(position)
        if existing_match is None:
            entity_by_position[position] = entity_match
        else:
            entity_by_position[position] = existing_match.merge(entity_match)

    _LOG.debug("Got %d entity matches", len(entity_by_position))

    entity_matches = _collapse_entities(entity_by_position)

    if not entity_matches:
        _LOG.info("No URLs after filtering")
        return

    with LinkApi(api_key=_api_key) as api:
        results = [_build_result(api, match) for match in entity_matches]
        deduped_results: dict[SongData, SongResult] = OrderedDict()
        for result in results:
            if result is None:
                continue

            old = deduped_results.get(result.data)

            if old is None:
                deduped_results[result.data] = result
                continue

            if old.is_spoiler:
                continue

            if result.is_spoiler:
                deduped_results[result.data] = result

        message_contents = [
            result.to_message_content() for result in deduped_results.values()
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
