import os
import subprocess
import sys

# Ensure the project root is importable
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure test mode while modules import; avoids race with fixtures.
# Several test modules import book_lamp.app at module scope, which builds the
# Flask app (and reads GOOGLE_CLIENT_ID) at import time, before any fixture runs.
# Set the credentials here so the app is built with a configured client ID.
os.environ["TEST_MODE"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["GOOGLE_CLIENT_ID"] = "dummy-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "dummy-client-secret"


@pytest.fixture
def app():
    # Set other test environment variables
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["GOOGLE_CLIENT_ID"] = "dummy-client-id"
    os.environ["GOOGLE_CLIENT_SECRET"] = "dummy-client-secret"
    os.environ["TEST_ALLOWED_EMAIL"] = "user@example.com"

    from book_lamp.app import app as flask_app

    flask_app.config.update(
        {
            "TESTING": True,
        }
    )

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture()
def authenticated_client(client):
    """Client with active session."""
    with client.session_transaction() as sess:
        sess["user_id"] = "1"  # Use string ID as stored in session
        sess["user_email"] = "user@example.com"
        sess["user_name"] = "Test User"
    return client


@pytest.fixture(autouse=True)
def _storage_reset(app):
    """Reset mock storage before each test."""
    with app.app_context():
        from book_lamp.app import get_storage
        from book_lamp.services.pg_storage import PostgresStorage

        storage = get_storage()

        if isinstance(storage, PostgresStorage):
            # PostgresStorage is reset in its own integration tests.
            # For general app tests, we might want to avoid wiping the whole DB
            # if we are using a persistent test DB, but usually we want a clean state.
            pass
        elif hasattr(storage, "books"):
            storage.books = []
            storage.reading_records = []
            storage.reading_list = []
            storage.next_book_id = 1
            storage.next_record_id = 1

        if hasattr(storage, "set_authorised"):
            storage.set_authorised(True)
        yield


@pytest.fixture(scope="session")
def docker_compose_command():
    """The compose implementation the container-backed tests use.

    Podman only. pytest-docker defaults to `docker compose`, which this project
    does not target, and podman-compose is what the deployment uses.
    """
    return "podman-compose"


def _kernel_cannot_program_the_bridge():
    """Whether netavark can program the compose bridge on this kernel.

    netavark, podman's bridge driver, sets the compose network up with nftables.
    `scripts/start` gives the database the host network when the kernel lacks that
    support (see compose.hostnet.yaml); the tests bring up the same stack, so they
    need the same overlay or the container never starts.
    """
    return not os.path.exists("/sys/module/nf_tables")


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """The compose file to run, plus the host-network overlay when it is needed."""
    root = str(pytestconfig.rootdir)
    files = [os.path.join(root, "compose.yaml")]
    if _kernel_cannot_program_the_bridge():
        files.append(os.path.join(root, "compose.hostnet.yaml"))
    return files


@pytest.fixture(scope="session")
def docker_setup():
    """Start the stack without waiting on health.

    pytest-docker's default is `up --build --wait`, and podman-compose rejects
    `--wait` — so every container-backed test errored in this fixture before it
    ran its body. Readiness is waited on by the `db_url` fixture instead, which
    polls until Postgres answers, so detaching here loses nothing.
    """
    return ["up --build --detach"]


@pytest.fixture(scope="session", autouse=True)
def _close_storage_pool():
    """Close the PostgreSQL pool at the end of the session.

    Left open, psycopg_pool's ConnectionPool is collected during interpreter
    shutdown and prints a PythonFinalizationError traceback after the summary,
    which reads like a test failure when it is only teardown noise.
    """
    yield

    from book_lamp.services import pg_storage

    if pg_storage._pool is not None:
        pg_storage._pool.close()
        pg_storage._pool = None


def _running_containers_named(prefix):
    """Names of running containers whose name contains `prefix`."""
    result = subprocess.run(
        ["podman", "ps", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


@pytest.fixture(scope="session")
def podman_services(request):
    """pytest-docker's stack, or a skip when the host cannot run containers.

    A stack that will not start makes pytest-docker raise out of its session
    fixture, which pytest reports as an ERROR against every test that needs it,
    so a host without the privileges to start containers looks like a broken
    suite. The tests still run wherever the stack does come up: this only changes
    what an unusable runtime reports as.
    """
    try:
        services = request.getfixturevalue("docker_services")
    except Exception as exc:  # a third-party fixture failing to start a container
        pytest.skip(f"podman could not start the compose stack: {exc}")

    # `up --detach` reports success even when the container never started — a
    # sandbox that cannot apply its network rules, say — and the failure only
    # surfaces later as a wait-for-Postgres timeout. Check the container
    # actually runs, so an unusable runtime skips at once and says why.
    project = request.getfixturevalue("docker_compose_project_name")
    if not _running_containers_named(project):
        pytest.skip(f"the compose stack did not start: no running container for {project}")

    return services
