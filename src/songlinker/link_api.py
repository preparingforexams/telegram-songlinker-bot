from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, HttpUrl
from pydantic.alias_generators import to_camel


class CamelCaseModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)


class PlatformLink(CamelCaseModel):
    url: HttpUrl
    entity_unique_id: str


class LinkResponse(CamelCaseModel):
    page_url: HttpUrl
    links_by_platform: dict[str, PlatformLink]


class SongLinks(BaseModel):
    page: HttpUrl
    apple_music: HttpUrl | None
    deezer: HttpUrl | None
    spotify: HttpUrl | None
    soundcloud: HttpUrl | None
    tidal: HttpUrl | None
    youtube: HttpUrl | None


class IoException(Exception):
    pass


class LinkApi:
    BASE_URL = "https://api.song.link/v1-alpha.1/links"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.Client(timeout=20)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._client.close()

    def _extract_url(
        self,
        links_by_platform: dict[str, PlatformLink],
        platform: str,
    ) -> HttpUrl | None:
        platform_link = links_by_platform.get(platform)
        if platform_link is None:
            return None
        return platform_link.url

    def _parse_response(self, content: bytes) -> SongLinks:
        response = LinkResponse.model_validate_json(content)
        result = SongLinks(
            page=response.page_url,
            apple_music=self._extract_url(response.links_by_platform, "appleMusic"),
            deezer=self._extract_url(response.links_by_platform, "deezer"),
            spotify=self._extract_url(response.links_by_platform, "spotify"),
            soundcloud=self._extract_url(response.links_by_platform, "soundcloud"),
            tidal=self._extract_url(response.links_by_platform, "tidal"),
            youtube=self._extract_url(response.links_by_platform, "youtube"),
        )
        return SongLinks.model_validate(result)

    def lookup_links(self, url: str) -> SongLinks | None:
        try:
            response = self._client.get(
                url=self.BASE_URL,
                params={
                    "url": url,
                    "userCountry": "DE",
                    "key": self._api_key,
                },
            )
        except httpx.RequestError as e:
            raise IoException from e

        status_code = response.status_code
        if response.is_success:
            return self._parse_response(response.content)
        elif 400 <= status_code < 500:
            raise IoException(f"Client error during request: {status_code}")
        elif 500 <= status_code < 600:
            raise IoException(f"Received server error {status_code}")
        else:
            raise IoException(f"Unexpected response status: {status_code}")
