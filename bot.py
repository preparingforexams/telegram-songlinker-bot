import json
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
        print("No entities in message")
        return

    urls = []

    for entity in entities:
        entity_type = entity['type']
        if entity_type == "url":
            offset = int(entity['offset'])
            length = int(entity['length'])
            url = message['text'][offset:offset + length]
            urls.append(url)
        elif entity_type == "text_link":
            urls.append(entity['url'])

    print(f"Got {len(urls)} URLs")

    urls = list(dict.fromkeys(filter(_not_song_link, urls)))

    if not urls:
        print("No URLs after filtering")
        return

    links = map(_build_link, urls)

    result = {
        'method': 'sendMessage',
        'chat_id': chat['id'],
        'reply_to_message_id': message['message_id'],
        'disable_web_page_preview': True,
        'disable_notification': True,
        'text': _build_message(links)
    }
    print(json.dumps(result, separators=(',', ':')))
    return result


def _not_song_link(url: str) -> bool:
    return "song.link" not in url


def _build_link(url: str) -> str:
    return f"https://song.link/{url}"


def _build_message(links: Iterable[str]) -> str:
    return "\n".join(links)


def _request_url(method: str):
    return f"https://api.telegram.org/bot{_bot_token}/{method}"
