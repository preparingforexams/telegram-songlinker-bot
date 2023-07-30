from typing import Annotated, Self

import httpx
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, HttpUrl
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


class PlatformMetadata(CamelCaseModel):
    type: str
    title: str
    artist_name: str
    api_provider: str
    platforms: Annotated[list[str], Field(min_length=1)]


class PlatformLink(CamelCaseModel):
    entity_unique_id: UniqueEntityId
    url: HttpUrl
    native_app_uri_desktop: AnyUrl | None = None
    native_app_uri_mobile: AnyUrl | None = None


class LinkResponse(CamelCaseModel):
    page_url: HttpUrl
    entities_by_unique_id: Annotated[
        dict[UniqueEntityId, PlatformMetadata], Field(min_length=1)
    ]
    links_by_platform: Annotated[dict[str, PlatformLink], Field(min_length=1)]


class ErrorResponse(CamelCaseModel):
    code: NonEmptyString


class SongLinks(BaseModel):
    page: HttpUrl
    apple_music: HttpUrl | None
    deezer: HttpUrl | None
    spotify: HttpUrl | None
    soundcloud: HttpUrl | None
    tidal: HttpUrl | None
    youtube: HttpUrl | None


class SongMetadata(BaseModel):
    title: NonEmptyString
    artist_name: NonEmptyString | None


class SongData(BaseModel):
    links: SongLinks
    metadata: SongMetadata


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
            title=entity.title,
            artist_name=entity.artist_name,
        )

    def _extract_url(
        self,
        links_by_platform: dict[str, PlatformLink],
        platform: str,
    ) -> HttpUrl | None:
        platform_link = links_by_platform.get(platform)
        if platform_link is None:
            return None
        return platform_link.url

    def _parse_response(self, content: bytes) -> SongData | None:
        response = LinkResponse.model_validate_json(content)

        if len(response.entities_by_unique_id) == 1:
            return None

        metadata = self._extract_metadata(
            links_by_platform=response.links_by_platform,
            entities_by_unique_id=response.entities_by_unique_id,
        )
        links = SongLinks(
            page=response.page_url,
            apple_music=self._extract_url(response.links_by_platform, "appleMusic"),
            deezer=self._extract_url(response.links_by_platform, "deezer"),
            spotify=self._extract_url(response.links_by_platform, "spotify"),
            soundcloud=self._extract_url(response.links_by_platform, "soundcloud"),
            tidal=self._extract_url(response.links_by_platform, "tidal"),
            youtube=self._extract_url(response.links_by_platform, "youtube"),
        )
        return SongData.model_validate(
            SongData(
                metadata=metadata,
                links=links,
            )
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
