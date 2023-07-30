import os
from unittest.mock import MagicMock

import pytest

from songlinker.link_api import LinkApi


@pytest.fixture()
def api_token(require_integration) -> str:
    result = os.getenv("SONGLINK_API_TOKEN")
    assert result, "SONGLINK_API_TOKEN not set"
    return result


@pytest.fixture()
def link_api(api_token) -> LinkApi:  # type: ignore
    with LinkApi(api_key=api_token) as api:
        yield api


def test_context_manager__works(mocker):
    close: MagicMock = mocker.spy(LinkApi, "close")

    with LinkApi(api_key="fake") as api:
        assert isinstance(api, LinkApi)
        close.assert_not_called()

    close.assert_called_once()


@pytest.mark.default_cassette("TestLinkApi.yaml")
@pytest.mark.integration
@pytest.mark.vcr
class TestLinkApi:
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
    def test_lookup_links_has_all_links(self, link_api, url, title, artist):
        data = link_api.lookup_links(url)
        assert data is not None

        links = data.links
        assert links.apple_music
        assert links.deezer
        assert links.spotify
        assert links.soundcloud
        assert links.tidal
        assert links.youtube

        metadata = data.metadata
        assert metadata.title == title
        assert metadata.artist_name == artist

    def test_lookup_youtube_only(self, link_api):
        data = link_api.lookup_links("https://www.youtube.com/watch?v=0_S3ytsXlIA")
        assert data is not None

        assert data.links.youtube
        assert data.metadata.title == "An Apple"
        assert data.metadata.artist_name == "tykylevits"
