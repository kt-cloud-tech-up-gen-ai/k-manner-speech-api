import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.db import (
    DatabaseConfigurationError,
    get_database_url,
    get_engine,
    get_session_factory,
)
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


class DatabaseConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_session_factory.cache_clear()
        get_engine.cache_clear()

    def test_missing_database_url_returns_503_without_connecting(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            get_session_factory.cache_clear()
            get_engine.cache_clear()
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/rooms")

        self.assertEqual(response.status_code, 503, "AC-DB-URL-MISSING-HTTP-503")
        self.assertEqual(response.json()["error"]["code"], "SERVICE_UNAVAILABLE")
        self.assertNotIn("postgresql", response.text.lower())

    def test_missing_database_url_fails_closed_outside_http(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            with self.assertRaises(
                DatabaseConfigurationError,
                msg="AC-DB-URL-MISSING-ALEMBIC-FAILS",
            ) as caught:
                get_database_url()

        self.assertIn("DATABASE_URL", str(caught.exception), "AC-DB-URL-MISSING-ALEMBIC-FAILS")
        self.assertNotIn("postgresql", str(caught.exception).lower())

    def test_tracked_configuration_contains_no_database_credentials(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        offenders = []
        inspected_prefixes = ("app/", "migrations/", ".env.example", "alembic.ini")
        for relative in tracked:
            normalized = relative.replace("\\", "/")
            if not normalized.startswith(inspected_prefixes):
                continue
            path = ROOT / relative
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line in text.splitlines():
                if (
                    "postgresql+psycopg://" in line
                    and "@" in line
                    and "<" not in line
                    and ">" not in line
                ):
                    offenders.append(relative)
                    break

        self.assertEqual(offenders, [], "AC-TRACKED-CONFIG-NO-DB-CREDENTIALS")
