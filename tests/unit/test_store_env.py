"""store.app_url: the API must run as taxsetu_app, never as the platform's owner role; and Postgres refuses the default signing secret."""
import pytest

from taxsetu_api import store
from taxsetu_api.main import create_app

OWNER = "postgresql://neondb_owner:ownerpw@ep-x-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("DATABASE_URL_APP", "DATABASE_URL", "TAXSETU_APP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)


def test_unconfigured_is_memory():
    assert store.app_url() is None and store.from_env() == (None, None)


def test_owner_url_without_app_password_is_ignored(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", OWNER)
    assert store.app_url() is None


def test_owner_url_is_repointed_at_app_role(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", OWNER)
    monkeypatch.setenv("TAXSETU_APP_PASSWORD", "p@ss/w:rd")
    assert store.app_url() == "postgresql://taxsetu_app:p%40ss%2Fw%3Ard@ep-x-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"


def test_explicit_app_url_wins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", OWNER)
    monkeypatch.setenv("TAXSETU_APP_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL_APP", "postgresql://taxsetu_app:y@h/db")
    assert store.app_url() == "postgresql://taxsetu_app:y@h/db"


def test_postgres_refuses_default_signing_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL_APP", "postgresql://taxsetu_app:y@localhost:1/db")
    monkeypatch.delenv("HITL_SIGNING_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="default HITL_SIGNING_SECRET"):
        create_app()
    assert create_app(secret=b"x" * 32) is not None      # an explicit secret is fine (psycopg connects lazily)
