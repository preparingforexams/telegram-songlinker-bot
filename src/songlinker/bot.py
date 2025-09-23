import asyncio
import logging
import signal
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, NamedTuple, Self, cast
from urllib import parse

from bs_nats_updater import create_updater
from opentelemetry import trace
from telegram import (
    Bot as TelegramBot,
)
from telegram import (
    InlineQueryResult,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions,
    MessageOriginHiddenUser,
    MessageOriginUser,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from songlinker.config import Config
from songlinker.link_api import IoException, LinkApi, Platform, SongData
from songlinker.telemetry import InstrumentedHttpxRequest

_LOG = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def telegram_span(*, update: Update, name: str) -> AsyncIterator[trace.Span]:
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(
            "telegram.update_keys",
            list(update.to_dict(recursive=False).keys()),
        )
        span.set_attribute("telegram.update_id", update.update_id)

        if message := update.effective_message:
            span.set_attribute("telegram.message_id", message.message_id)
            span.set_attribute("telegram.message_timestamp", message.date.isoformat())

        if chat := update.effective_chat:
            span.set_attribute("telegram.chat_id", chat.id)
            span.set_attribute("telegram.chat_type", chat.type)
            if chat_name := chat.effective_name:
                span.set_attribute("telegram.chat_name", chat_name)

        if user := update.effective_user:
            span.set_attribute("telegram.user_id", user.id)
            span.set_attribute("telegram.user_full_name", user.full_name)
            if user_username := user.username:
                span.set_attribute("telegram.user_username", user_username)

        if query := update.inline_query:
            span.set_attribute("telegram.query_id", query.id)

        yield span


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

    def to_inline_result(self) -> InlineQueryResult:
        artist = self.data.metadata.artist_name
        title = self.data.metadata.title
        result_title = self.data.links.page
        if artist and title:
            result_title = f"{artist} - {title}"

        thumbnail_data = {}
        link_preview_options = LinkPreviewOptions(is_disabled=True)

        if thumbnail := self.data.metadata.thumbnail:
            _LOG.info(
                "Using thumbnail URL: %s (type: %s)",
                thumbnail.url,
                type(thumbnail.url),
            )
            thumbnail_data = {
                "thumbnail_url": thumbnail.url,
                "thumbnail_width": thumbnail.width,
                "thumbnail_height": thumbnail.height,
            }

            link_preview_options = LinkPreviewOptions(
                url=thumbnail.url,
                show_above_text=True,
            )

        return InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=result_title,
            url=self.data.links.page,
            input_message_content=InputTextMessageContent(
                message_text=self.to_message_content(),
                parse_mode="HTML",
                link_preview_options=link_preview_options,
            ),
            **thumbnail_data,  # type: ignore
        )


class EntityPosition(NamedTuple):
    offset: int
    length: int


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
        if match.url is not None and ("song.link" not in match.require_url())
    ]


class Bot:
    def __init__(self, config: Config) -> None:
        bot = TelegramBot(
            token=config.telegram_api_key,
            request=InstrumentedHttpxRequest(connection_pool_size=2),
        )
        self._bot = bot
        self._link_api = LinkApi(config.songlinker_api_key)

        app = (
            Application.builder()
            .post_shutdown(self._close)
            .updater(create_updater(bot, config.nats))
            .build()
        )
        self._app = app

        app.add_handler(InlineQueryHandler(callback=self._on_inline_query))
        app.add_handler(
            MessageHandler(
                filters=filters.TEXT & ~filters.UpdateType.EDITED,
                callback=self._on_message_update,
                block=False,
            )
        )

    async def _close(self, _: Any = None) -> None:
        _LOG.info("Closing bot")
        await self._link_api.close()

    def handle_updates(self) -> None:
        _LOG.info("Starting bot")
        self._app.run_polling(
            stop_signals=[
                signal.SIGINT,
                signal.SIGTERM,
            ]
        )

    async def _on_message_update(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        async with telegram_span(update=update, name="on_message_update") as span:
            message = update.message
            if message is None:
                raise RuntimeError("No message")

            if via_bot := message.via_bot:
                if self._bot.username == via_bot.username:
                    _LOG.info("Skipping message that was sent via this bot")
                    span.set_attribute("songlinker.skipped", True)
                    return

            if forward_origin := message.forward_origin:
                match forward_origin:
                    case MessageOriginUser():
                        sender_user = forward_origin.sender_user
                        if self._bot.username == sender_user.username:
                            _LOG.info("Skipping message forwarded from this bot")
                            span.set_attribute("songlinker.skipped", True)
                            return
                    case MessageOriginHiddenUser():
                        user_name = forward_origin.sender_user_name
                        _LOG.info(
                            "Message was forwarded from hidden user %s", user_name
                        )
                    case other:
                        _LOG.error("Unknown forward origin type: %s", other)

            entities = message.entities
            if not entities:
                _LOG.debug("No entities in message")
                span.set_attribute("songlinker.skipped", True)
                return

            entity_by_position: dict[EntityPosition, EntityMatch] = {}

            for entity in entities:
                position = EntityPosition(
                    offset=entity.offset,
                    length=entity.length,
                )

                entity_match: EntityMatch
                match entity.type:
                    case "url":
                        url = message.parse_entity(entity)
                        entity_match = EntityMatch(position=position, url=url)
                    case "text_link":
                        entity_match = EntityMatch(position=position, url=entity.url)
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

            span.set_attribute("songlinker.url_entity_count", len(entities))

            if not entity_matches:
                _LOG.info("No URLs after filtering")
                span.set_attribute("songlinker.skipped", True)
                return

            tasks: list[asyncio.Task[SongResult | None]] = []
            async with asyncio.TaskGroup() as tg:
                for match in entity_matches:
                    task = tg.create_task(self._build_result(match))
                    tasks.append(task)

            results = [t.result() for t in tasks]

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

            span.set_attribute("songlinker.result_size", len(message_contents))

            if not message_contents:
                _LOG.info("No known songs found")
                return

            await message.reply_text(
                parse_mode=ParseMode.HTML,
                text="\n\n".join(message_contents),
                link_preview_options=LinkPreviewOptions(
                    is_disabled=True,
                ),
                disable_notification=True,
            )

    async def _on_inline_query(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        async with telegram_span(update=update, name="on_inline_query"):
            inline_query = update.inline_query
            if inline_query is None:
                raise RuntimeError("No inline query")

            query_text: str = inline_query.query.strip()
            if not query_text:
                _LOG.debug("Ignoring empty inline query")
                await inline_query.answer(results=[])
                return

            try:
                url = parse.urlparse(query_text)
            except ValueError:
                _LOG.debug("Received non-URL query")
                await inline_query.answer(results=[])
                return

            if url.scheme not in ["http", "https"]:
                _LOG.debug("Received non-HTTP URL")
                await inline_query.answer(results=[])
                return

            song_result = await self._build_result(
                EntityMatch(
                    position=EntityPosition(offset=0, length=len(query_text)),
                    url=query_text,
                ),
            )

            results = [song_result.to_inline_result()] if song_result else []
            await inline_query.answer(results=results)

    async def _build_result(self, entity: EntityMatch) -> SongResult | None:
        try:
            data = await self._link_api.lookup_links(entity.require_url())
        except IoException as e:
            _LOG.error(
                f"Could not look up data for URL {entity.require_url()}",
                exc_info=e,
            )
            return None

        if data is None:
            return None

        return SongResult(data, is_spoiler=entity.is_spoiler)
