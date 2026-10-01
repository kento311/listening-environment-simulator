import io
import unittest
from unittest.mock import patch

import numpy as np

from app import app
from services.audio_processing import AudioProcessingError, ProcessedAudio


class AppTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.original_max_content_length = app.config["MAX_CONTENT_LENGTH"]
        self.client = app.test_client()

    def tearDown(self):
        app.config["MAX_CONTENT_LENGTH"] = self.original_max_content_length

    def test_home_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Listening Environment Simulator", response.data)

    def test_requires_an_audio_file(self):
        response = self.client.post("/api/process", data={})

        self.assertEqual(response.status_code, 400)

    def test_rejects_unsupported_extension(self):
        response = self.client.post(
            "/api/process",
            data={"file": (io.BytesIO(b"not audio"), "notes.txt")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("対応形式", response.get_json()["error"])

    @patch("app.process_audio_file")
    def test_returns_processed_wav(self, process):
        process.return_value = ProcessedAudio(
            samples=np.zeros(800, dtype=np.float32),
            sample_rate=8_000,
        )

        response = self.client.post(
            "/api/process",
            data={"file": (io.BytesIO(b"input"), "practice.wav")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/wav")
        self.assertTrue(response.data.startswith(b"RIFF"))
        self.assertIn(
            "practice_exam-room.wav",
            response.headers["Content-Disposition"],
        )

    @patch("app.process_audio_file")
    def test_returns_safe_audio_validation_errors(self, process):
        process.side_effect = AudioProcessingError("音声データが空です。")

        response = self.client.post(
            "/api/process",
            data={"file": (io.BytesIO(b"input"), "empty.wav")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "音声データが空です。")

    @patch("app.process_audio_file")
    def test_hides_internal_processing_errors(self, process):
        process.side_effect = RuntimeError("private filesystem details")

        with self.assertLogs(app.logger, level="ERROR"):
            response = self.client.post(
                "/api/process",
                data={"file": (io.BytesIO(b"input"), "practice.wav")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"private filesystem details", response.data)

    def test_rejects_oversized_requests(self):
        app.config["MAX_CONTENT_LENGTH"] = 128

        response = self.client.post(
            "/api/process",
            data={"file": (io.BytesIO(b"x" * 1_024), "large.wav")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("25 MB", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
