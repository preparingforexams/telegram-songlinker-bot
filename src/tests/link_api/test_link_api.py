import os
from unittest.mock import MagicMock

import pytest
import vcr

from songlinker.link_api import LinkApi
from tests.conftest import require_integration


@pytest.fixture()
def api_token(require_integration) -> str:
    result = os.getenv("SONGLINK_API_TOKEN")
    assert result
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


@pytest.mark.integration
@pytest.mark.parametrize(
    "url",
    [
        "https://open.spotify.com/track/0SZemtszoaQHL3aUuMS6WF?si=110f087282bd457f",
        "https://open.spotify.com/track/0d28khcov6AiegSCpG5TuT?si=49a8f03c107746d4",
        "https://www.youtube.com/watch?v=fJ9rUzIMcZQ&pp=ygUGcXVlZW4g",
    ],
)
@vcr.use_cassette(record_mode="new_episodes")
def test_lookup_links_has_all_links(link_api, url):
    response = link_api.lookup_links(url)
    assert response is not None

    assert response.apple_music
    assert response.deezer
    assert response.spotify
    assert response.soundcloud
    assert response.tidal
    assert response.youtube
