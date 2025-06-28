import pytest
import uvloop


@pytest.fixture()
def require_integration(request: pytest.FixtureRequest) -> None:
    marker = request.node.get_closest_marker("integration")
    if marker is None:
        raise pytest.UsageError("Fixture is only available in integration tests")


@pytest.fixture(scope="session")
def event_loop_policy():
    return uvloop.EventLoopPolicy()
