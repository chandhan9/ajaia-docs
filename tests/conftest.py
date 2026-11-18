import pytest

from app import create_app


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def app(db_path):
    return create_app({"TESTING": True, "DATABASE_PATH": db_path, "SECRET_KEY": "test"})


@pytest.fixture
def login(app):
    """Return a factory that yields a test client signed in as the given demo user."""
    def _login(email):
        client = app.test_client()
        res = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
        assert res.status_code == 200, res.get_json()
        return client
    return _login


@pytest.fixture
def alice(login):
    return login("alice@ajaia.test")


@pytest.fixture
def bob(login):
    return login("bob@ajaia.test")


@pytest.fixture
def carol(login):
    return login("carol@ajaia.test")
