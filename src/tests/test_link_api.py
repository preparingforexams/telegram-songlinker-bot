import os
from unittest.mock import MagicMock

import pytest

from songlinker.link_api import LinkApi
from tests.conftest import require_integration


@pytest.fixture()
def api_token(require_integration) -> str:
    result = os.getenv("SONGLINK_API_TOKEN")
    assert result
    return result


@pytest.fixture()
def link_api(api_token) -> LinkApi:
    with LinkApi(api_key=api_token) as api:
        yield api


def test_context_manager__works(mocker):
    close: MagicMock = mocker.spy(LinkApi, "close")

    with LinkApi(api_key="fake") as api:
        assert isinstance(api, LinkApi)
        close.assert_not_called()

    close.assert_called_once()
