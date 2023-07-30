from unittest.mock import MagicMock

from songlinker.link_api import LinkApi


def test_context_manager__works(mocker):
    close: MagicMock = mocker.spy(LinkApi, "close")

    with LinkApi(api_key="fake") as api:
        assert isinstance(api, LinkApi)
        close.assert_not_called()

    close.assert_called_once()
