"""Create media buckets and upload the canonical Doyun portrait."""

from pathlib import Path

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.catalog import Persona
from app.services.media_storage import PERSONA_BUCKET, SupabaseMediaStorage

SOURCE = Path("/Users/mac/Basic_project_front/k-manner-speech-front/web/src/assets/characters/doyun.jpg")


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"도윤 이미지가 없습니다: {SOURCE}")
    storage = SupabaseMediaStorage()
    storage.ensure_buckets()
    object_path = storage.upload_persona_image(SOURCE, "doyun")
    public_url = storage.public_url(PERSONA_BUCKET, object_path)
    with get_session_factory()() as db:
        persona = db.scalar(select(Persona).where(Persona.id == "doyun"))
        if persona is None:
            raise RuntimeError("doyun persona가 DB에 없습니다.")
        persona.avatar_url = public_url
        db.commit()
    print("Supabase media storage bootstrap complete.")


if __name__ == "__main__":
    main()
