from collections import namedtuple
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Self

import httpx
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pydantic.alias_generators import to_camel


class CamelCaseModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)


UniqueEntityId = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"[A-Z_]+::.+",
    ),
]

NonEmptyString = Annotated[str, Field(min_length=1)]

PlatformSpec = namedtuple("PlatformSpec", ["id", "name"])


class Platform(Enum):
    spotify = PlatformSpec("spotify", "Spotify")
    apple_music = PlatformSpec("appleMusic", "Apple Music")
    deezer = PlatformSpec("deezer", "Deezer")
    soundcloud = PlatformSpec("soundcloud", "SoundCloud")
    tidal = PlatformSpec("tidal", "Tidal")
    youtube = PlatformSpec("youtube", "YouTube")


class PlatformMetadata(CamelCaseModel):
    type: str
    title: str
    artist_name: str
    api_provider: str
    platforms: Annotated[list[str], Field(min_length=1)]


class PlatformLink(CamelCaseModel):
    entity_unique_id: UniqueEntityId
    url: HttpUrl
    native_app_uri_desktop: str | None = None
    native_app_uri_mobile: str | None = None


class LinkResponse(CamelCaseModel):
    page_url: HttpUrl
    entities_by_unique_id: Annotated[
        dict[UniqueEntityId, PlatformMetadata], Field(min_length=1)
    ]
    links_by_platform: Annotated[dict[str, PlatformLink], Field(min_length=1)]


class ErrorResponse(CamelCaseModel):
    code: NonEmptyString


class SongLinks:
    def __init__(self, page: str, link_by_platform: dict[Platform, str]):
        self.page = page
        self._link_by_platform = link_by_platform

    def __getitem__(self, item: Platform) -> str | None:
        return self._link_by_platform.get(item)

    def items(self) -> Iterable[tuple[Platform, str]]:
        return sorted(
            self._link_by_platform.items(),
            key=lambda t: t[0].value.name,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SongLinks):
            return False

        return self.page == other.page

    def __hash__(self) -> int:
        return hash(self.page)


@dataclass(frozen=True)
class SongMetadata:
    type: str
    title: str
    artist_name: str | None

    @property
    def is_album(self) -> bool:
        return self.type == "album"

    @property
    def is_song(self) -> bool:
        return self.type == "song"


@dataclass(eq=False, frozen=True)
class SongData:
    links: SongLinks
    metadata: SongMetadata

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SongData):
            return False

        return self.links == other.links

    def __hash__(self) -> int:
        return hash(self.links)


class IoException(Exception):
    pass


class LinkApi:
    BASE_URL = "https://api.song.link/v1-alpha.1/links"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.Client(timeout=20)
        HTTPXClientInstrumentor().instrument_client(self._client)

    def __enter__(self) -> Self:
        return self

    def __exit__(  # type: ignore[no-untyped-def]
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _extract_metadata(
        self,
        links_by_platform: dict[str, PlatformLink],
        entities_by_unique_id: dict[str, PlatformMetadata],
    ) -> SongMetadata:
        entity: PlatformMetadata
        for platform in ("spotify", "tidal", "appleMusic", "soundcloud", "youtube"):
            # first try our preferred providers
            link = links_by_platform.get(platform)
            if link is None:
                continue

            entity_id = link.entity_unique_id
            entity = entities_by_unique_id[entity_id]
            break
        else:
            # If no preferred provider was found, use the first one
            _, entity = entities_by_unique_id.popitem()

        return SongMetadata(
            type=entity.type,
            title=entity.title,
            artist_name=entity.artist_name,
        )

    def _extract_url(
        self,
        links_by_platform: dict[str, PlatformLink],
        platform: Platform,
    ) -> HttpUrl | None:
        platform_link = links_by_platform.get(platform.value.id)
        if platform_link is None:
            return None
        return platform_link.url

    def _parse_response(self, content: bytes) -> SongData | None:
        response = LinkResponse.model_validate_json(content)

        metadata = self._extract_metadata(
            links_by_platform=response.links_by_platform,
            entities_by_unique_id=response.entities_by_unique_id,
        )

        link_by_platform: dict[Platform, str] = {}
        for platform in Platform:
            link = self._extract_url(response.links_by_platform, platform)
            if link is not None:
                link_by_platform[platform] = str(link)

        if len(link_by_platform) <= 1:
            return None

        links = SongLinks(
            page=str(response.page_url),
            link_by_platform=link_by_platform,
        )

        return SongData(
            metadata=metadata,
            links=links,
        )

    def lookup_links(self, url: str) -> SongData | None:
        try:
            response = self._client.get(
                url=self.BASE_URL,
                params={
                    "url": url,
                    "userCountry": "DE",
                    "songIfSingle": "true",
                    "key": self._api_key,
                },
            )
        except httpx.RequestError as e:
            raise IoException from e

        status_code = response.status_code
        if response.is_success:
            return self._parse_response(response.content)
        elif 400 <= status_code < 500:
            try:
                error = ErrorResponse.model_validate_json(response.content)
                if error.code == "could_not_resolve_entity":
                    return None
                else:
                    raise IoException(
                        f"Client error during request:"
                        f" {status_code}, code: {error.code}"
                    )
            except ValueError:
                raise IoException(f"Client error during request: {status_code}")
        elif 500 <= status_code < 600:
            raise IoException(f"Received server error {status_code}")
        else:
            raise IoException(f"Unexpected response status: {status_code}")
