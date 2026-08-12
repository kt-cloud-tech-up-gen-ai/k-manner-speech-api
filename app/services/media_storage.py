"""Supabase Storage boundary for public persona images and private chat audio."""

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

# Importing config loads the repository .env before auth settings are read.
from app.core import config as _config  # noqa: F401
from app.core.auth import get_supabase_service_role_key, get_supabase_url

PERSONA_BUCKET = "persona-images"
CHAT_AUDIO_BUCKET = "chat-audio"


class SupabaseMediaStorage:
    def __init__(self) -> None:
        self.base_url = get_supabase_url().rstrip("/")
        self.key = get_supabase_service_role_key()
        if not self.key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY가 필요합니다.")

    def _request(self, path: str, *, method: str = "GET", data: bytes | None = None,
                 content_type: str = "application/json", allow_conflict: bool = False) -> bytes:
        request = Request(f"{self.base_url}/storage/v1{path}", data=data, method=method)
        request.add_header("apikey", self.key)
        request.add_header("Authorization", f"Bearer {self.key}")
        request.add_header("Content-Type", content_type)
        if method in {"POST", "PUT"}:
            request.add_header("x-upsert", "true")
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as error:
            if allow_conflict and error.code in {400, 409}:
                return b""
            raise RuntimeError(f"Supabase Storage 요청 실패: HTTP {error.code}") from error

    def ensure_buckets(self) -> None:
        for bucket, public, mime_types in (
            (PERSONA_BUCKET, True, ["image/jpeg", "image/png", "image/webp"]),
            (CHAT_AUDIO_BUCKET, False, ["audio/wav"]),
        ):
            payload = json.dumps({
                "id": bucket, "name": bucket, "public": public,
                "allowed_mime_types": mime_types,
            }).encode()
            self._request("/bucket", method="POST", data=payload, allow_conflict=True)

    def upload(self, bucket: str, object_path: str, source: Path, content_type: str) -> str:
        encoded = "/".join(quote(part, safe="") for part in object_path.split("/"))
        self._request(
            f"/object/{bucket}/{encoded}", method="POST", data=source.read_bytes(),
            content_type=content_type,
        )
        return object_path

    def upload_chat_audio(self, source: Path, *, owner_id: str, room_id: str, message_id: str) -> str:
        return self.upload(
            CHAT_AUDIO_BUCKET, f"{owner_id}/{room_id}/{message_id}.wav", source, "audio/wav"
        )

    def upload_persona_image(self, source: Path, persona_id: str) -> str:
        suffix = source.suffix.lower()
        content_type = {".png": "image/png", ".webp": "image/webp"}.get(suffix, "image/jpeg")
        return self.upload(PERSONA_BUCKET, f"{persona_id}/portrait{suffix}", source, content_type)

    def public_url(self, bucket: str, object_path: str) -> str:
        encoded = "/".join(quote(part, safe="") for part in object_path.split("/"))
        return f"{self.base_url}/storage/v1/object/public/{bucket}/{encoded}"

    def download_chat_audio(self, object_path: str) -> bytes:
        encoded = "/".join(quote(part, safe="") for part in object_path.split("/"))
        return self._request(f"/object/{CHAT_AUDIO_BUCKET}/{encoded}")
