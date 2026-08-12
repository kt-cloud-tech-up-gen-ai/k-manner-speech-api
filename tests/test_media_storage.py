import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class MediaStorageTests(unittest.TestCase):
    @patch("app.services.media_storage.urlopen")
    @patch("app.services.media_storage.get_supabase_service_role_key", return_value="service-key")
    @patch("app.services.media_storage.get_supabase_url", return_value="https://project.supabase.co")
    def test_bucket_bootstrap_keeps_audio_private(self, _url, _key, mock_urlopen):
        from app.services.media_storage import SupabaseMediaStorage

        mock_urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
        SupabaseMediaStorage().ensure_buckets()

        bodies = [call.args[0].data.decode("utf-8") for call in mock_urlopen.call_args_list]
        self.assertTrue(any('"id": "persona-images"' in body and '"public": true' in body for body in bodies))
        self.assertTrue(any('"id": "chat-audio"' in body and '"public": false' in body for body in bodies))

    @patch("app.services.media_storage.urlopen")
    @patch("app.services.media_storage.get_supabase_service_role_key", return_value="service-key")
    @patch("app.services.media_storage.get_supabase_url", return_value="https://project.supabase.co")
    def test_audio_upload_uses_owner_room_message_path(self, _url, _key, mock_urlopen):
        from app.services.media_storage import SupabaseMediaStorage

        mock_urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
        with TemporaryDirectory() as directory:
            wav = Path(directory) / "answer.wav"
            wav.write_bytes(b"RIFF-test")
            path = SupabaseMediaStorage().upload_chat_audio(
                wav, owner_id="user-1", room_id="room-1", message_id="message-1"
            )

        self.assertEqual(path, "user-1/room-1/message-1.wav")
        request = mock_urlopen.call_args.args[0]
        self.assertIn("/storage/v1/object/chat-audio/user-1/room-1/message-1.wav", request.full_url)
        self.assertEqual(request.headers["Content-type"], "audio/wav")

    def test_message_response_contains_audio_url_only_when_stored(self):
        from app.models.chat import ChatMessage
        from app.routers.rooms import _to_message_response

        created_at = datetime.now(timezone.utc)
        message = ChatMessage(id="m1", room_id="r1", role="assistant", content="안녕", created_at=created_at)
        message.audio_storage_path = "owner/r1/m1.wav"
        response = _to_message_response(message)
        self.assertEqual(response.audio_url, "/rooms/r1/messages/m1/audio")

        legacy = ChatMessage(id="m2", room_id="r1", role="assistant", content="예전 답변", created_at=created_at)
        self.assertIsNone(_to_message_response(legacy).audio_url)


if __name__ == "__main__":
    unittest.main()
