import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from songlinker.link_api import IoException, LinkApi, Platform


@pytest.fixture
def api_token(require_integration) -> str:
    result = os.getenv("SONGLINK_API_TOKEN")
    assert result, "SONGLINK_API_TOKEN not set"
    return result


@pytest_asyncio.fixture
async def link_api(api_token) -> AsyncIterator[LinkApi]:
    api = LinkApi(api_key=api_token)
    try:
        yield api
    finally:
        await api.close()


@pytest_asyncio.fixture
async def invalid_api() -> AsyncIterator[LinkApi]:
    api = LinkApi(api_key="invalid")
    try:
        yield api
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_request_io_error(mocker, invalid_api):
    _client = mocker.patch.object(invalid_api, "_client", autospec=True)
    _client.get.side_effect = httpx.RequestError("Test")
    with pytest.raises(IoException):
        await invalid_api.lookup_links(
            "https://open.spotify.com/track/0d28khcov6AiegSCpG5TuT"
        )


@pytest.mark.asyncio
async def test_server_error(mocker, invalid_api):
    _client = mocker.patch.object(invalid_api, "_client", autospec=True)
    get_mock = mocker.AsyncMock(
        return_value=mocker.MagicMock(
            spec=httpx.Response,
            is_success=False,
            status_code=502,
        ),
    )
    _client.get = get_mock
    with pytest.raises(IoException):
        await invalid_api.lookup_links(
            "https://open.spotify.com/track/0d28khcov6AiegSCpG5TuT"
        )


@pytest.mark.default_cassette("TestLinkApi.yaml")
@pytest.mark.integration
@pytest.mark.vcr
class TestLinkApi:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url,title,artist",
        [
            (
                "https://open.spotify.com/track/0SZemtszoaQHL3aUuMS6WF",
                "Bum Bum Eis",
                "FiNCH, Esther Graf",
            ),
            (
                "https://open.spotify.com/track/0d28khcov6AiegSCpG5TuT",
                "Feel Good Inc.",
                "Gorillaz",
            ),
            (
                "https://www.youtube.com/watch?v=dTAAsCNK7RA",
                "Here It Goes Again",
                "OK Go",
            ),
        ],
    )
    async def test_lookup_links_has_all_links(self, link_api, url, title, artist):
        data = await link_api.lookup_links(url)
        assert data is not None

        links = data.links
        for platform in Platform:
            assert links[platform]

        metadata = data.metadata
        assert metadata.title == title
        assert metadata.artist_name == artist

    @pytest.mark.asyncio
    async def test_lookup_youtube_only(self, link_api):
        data = await link_api.lookup_links(
            "https://www.youtube.com/watch?v=0_S3ytsXlIA"
        )
        assert data is None

    @pytest.mark.asyncio
    async def test_lookup_non_song(self, link_api):
        data = await link_api.lookup_links("https://google.com")
        assert data is None
