"""Create media buckets and upload the canonical Doyun portrait."""

import argparse
from pathlib import Path

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.catalog import Persona
from app.services.media_storage import PERSONA_BUCKET, SupabaseMediaStorage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Supabase 미디어 버킷을 만들고 도윤 이미지를 업로드합니다."
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="업로드할 도윤 이미지 파일 경로",
    )
    return parser


def main(source: Path) -> None:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"도윤 이미지가 없습니다: {source}")
    storage = SupabaseMediaStorage()
    storage.ensure_buckets()
    object_path = storage.upload_persona_image(source, "doyun")
    public_url = storage.public_url(PERSONA_BUCKET, object_path)
    with get_session_factory()() as db:
        persona = db.scalar(select(Persona).where(Persona.id == "doyun"))
        if persona is None:
            raise RuntimeError("doyun persona가 DB에 없습니다.")
        persona.avatar_url = public_url
        db.commit()
    print("Supabase media storage bootstrap complete.")


if __name__ == "__main__":
    main(build_parser().parse_args().source)
