import os
from typing import Iterable

_bot_token = os.getenv('TELEGRAM_TOKEN')


def handle_update(update, context):
    message = update.get('message')
    if not message:
        return
    chat = message['chat']
    entities = message.get('entities')
    if not entities:
        return

    links = []

    for entity in entities:
        entity_type = entity['type']
        if entity_type == "url":
            offset = int(entity['offset'])
            length = int(entity['length'])
            url = message['text'][offset:offset + length]
            links.append(_build_link(url))
        elif entity_type == "text_link":
            links.append(_build_link(entity['url']))

    links = set(filter(_not_song_link, links))

    if not links:
        return

    return {
        'method': 'sendMessage',
        'chat_id': chat['id'],
        'reply_to_message_id': message['message_id'],
        'disable_web_page_preview': True,
        'disable_notification': True,
        'text': _build_message(links)
    }


def _not_song_link(url: str) -> bool:
    return "song.link" in url


def _build_link(url: str) -> str:
    return f"https://song.link/{url}"


def _build_message(links: Iterable[str]) -> str:
    return "\n".join(links)


def _request_url(method: str):
    return f"https://api.telegram.org/bot{_bot_token}/{method}"
