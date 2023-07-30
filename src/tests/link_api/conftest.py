import pytest


@pytest.fixture(autouse=True)
def vcr_config(request: pytest.FixtureRequest):
    return {"filter_query_parameters": ["key"]}
