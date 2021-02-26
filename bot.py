import json
import os
import uuid
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib import parse

import requests
from requests import RequestException

_bot_token = os.getenv('TELEGRAM_TOKEN')
_api_key = os.getenv('SONGLINK_API_TOKEN')
_api_base_url = "https://api.song.link/v1-alpha.1/links"


def handle_update(update, context):
    message = update.get('message')
    result = None
    if message:
        result = _handle_message(message)
    inline_query = update.get('inline_query')
    if inline_query:
        result = _handle_query(inline_query)
    if result:
        print(json.dumps(result, separators=(',', ':')))
        return result


@dataclass
class SongLink:
    url: str
    artist: Optional[str] = None
    title: Optional[str] = None

    def to_message_content(self) -> str:
        artist = self.artist
        title = self.title
        if not artist or not title:
            return self.url
        else:
            return f"{artist} - {title}: {self.url}"

    def to_inline_result(self) -> dict:
        artist = self.artist
        title = self.title
        result_title = self.url
        if artist and title:
            result_title = f"{artist} - {title}"
        return {
            'type': "article",
            'id': _random_id(),
            'title': result_title,
            'url': self.url,
            'input_message_content': {
                'message_text': self.url,
            }
        }


def _random_id() -> str:
    return str(uuid.uuid4())


def _handle_query(query: dict) -> Optional[dict]:
    query_text: str = query['query'].strip()
    song_link: Optional[SongLink] = None
    if query_text:
        try:
            url = parse.urlparse(query_text)
            if url.scheme == 'http' or url.scheme == 'https':
                song_link = _build_link(query_text)
        except ValueError:
            pass
    results = [song_link.to_inline_result()] if song_link else []
    return {
        'method': "answerInlineQuery",
        'inline_query_id': query['id'],
        'results': results
    }


def _handle_message(message: dict) -> Optional[dict]:
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

    links = filter(None, (_build_link(it).to_message_content() for it in urls))

    return {
        'method': 'sendMessage',
        'chat_id': chat['id'],
        'reply_to_message_id': message['message_id'],
        'disable_web_page_preview': True,
        'disable_notification': True,
        'text': _build_message(links)
    }


def _not_song_link(url: str) -> bool:
    return "song.link" not in url


def _build_link(url: str) -> Optional[SongLink]:
    params = {
        'url': url,
        'userCountry': "DE",
        'key': _api_key
    }

    try:
        result = requests.get(_api_base_url, params=params)
        if result.status_code == 400 and result.json()['code'] == "could_not_resolve_entity":
            # In this case the URL just isn't a song
            return None
        result.raise_for_status()
        info = result.json()
        bare_url = info['pageUrl']
        entities_by_id: dict = info['entitiesByUniqueId']
        for match in entities_by_id.values():
            if match['apiProvider'] == 'spotify':
                title = match.get('title')
                artist = match.get('artistName')
                return SongLink(bare_url, artist, title)

        return SongLink(bare_url)
    except RequestException as e:
        print(f"Could not get URL from API: {e}")
        return SongLink(f"https://song.link/{url}")


def _build_message(links: Iterable[str]) -> str:
    return "\n".join(links)


def _request_url(method: str):
    return f"https://api.telegram.org/bot{_bot_token}/{method}"
