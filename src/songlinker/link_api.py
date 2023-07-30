from typing import Self

import httpx
from pydantic import BaseModel


class LinkResponse(BaseModel):
    pass


class LinkApi:
    BASE_URL = "https://api.song.link/v1-alpha.1/links"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.Client()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._client.close()
