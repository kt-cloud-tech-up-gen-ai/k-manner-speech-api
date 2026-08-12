"""Fail-closed target validation for explicitly enabled live Supabase checks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

TARGET_PROJECT_REF = "dlgjsarbbblmsscxrqrt"
TARGET_POOLER_HOST = "aws-0-ap-southeast-2.pooler.supabase.com"
PREVIOUS_PROJECT_REF = "nfdkddajydfwcwddeoyn"


@dataclass(frozen=True)
class LiveSupabaseTarget:
    project_ref: str
    pooler_host: str


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"AC-LIVE-CONFIG-TARGET: {name} is required")
    return value


def validate_live_supabase_environment() -> LiveSupabaseTarget:
    """Validate target identity without returning or logging credentials."""
    database_url = _required("DATABASE_URL")
    supabase_url = _required("SUPABASE_URL")
    publishable_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv(
        "SUPABASE_PUBLISHABLE_KEY"
    )
    if not publishable_key:
        raise RuntimeError("AC-LIVE-CONFIG-TARGET: publishable key is required")
    _required("SUPABASE_SERVICE_ROLE_KEY")
    guest_secret = _required("GUEST_SESSION_SECRET")
    if len(guest_secret) < 32:
        raise RuntimeError("AC-LIVE-CONFIG-TARGET: GUEST_SESSION_SECRET is too short")

    combined = f"{database_url}\n{supabase_url}"
    if PREVIOUS_PROJECT_REF in combined or TARGET_PROJECT_REF not in combined:
        raise RuntimeError("AC-LIVE-CONFIG-TARGET: unexpected Supabase project")

    database = urlparse(database_url)
    project = urlparse(supabase_url)
    expected_user = f"postgres.{TARGET_PROJECT_REF}"
    if (
        database.hostname != TARGET_POOLER_HOST
        or database.port != 5432
        or database.username != expected_user
        or database.path != "/postgres"
        or project.scheme != "https"
        or project.hostname != f"{TARGET_PROJECT_REF}.supabase.co"
    ):
        raise RuntimeError("AC-LIVE-CONFIG-TARGET: unexpected Supabase endpoint")

    return LiveSupabaseTarget(
        project_ref=TARGET_PROJECT_REF,
        pooler_host=TARGET_POOLER_HOST,
    )
