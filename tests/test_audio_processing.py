import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from services.audio_processing import (
    MAX_AUDIO_SECONDS,
    AudioProcessingError,
    process_audio_file,
)


class AudioProcessingTests(unittest.TestCase):
    def test_processes_audio_deterministically(self):
        sample_rate = 16_000
        time = np.arange(sample_rate // 4, dtype=np.float32) / sample_rate
        source = (0.25 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "synthetic.wav"
            sf.write(input_path, source, sample_rate)
            first = process_audio_file(input_path)
            second = process_audio_file(input_path)

        self.assertEqual(first.sample_rate, sample_rate)
        self.assertGreater(first.samples.size, source.size)
        self.assertTrue(np.all(np.isfinite(first.samples)))
        self.assertLessEqual(float(np.max(np.abs(first.samples))), 0.921)
        np.testing.assert_array_equal(first.samples, second.samples)

    @patch("services.audio_processing.librosa.load")
    def test_rejects_unreadable_audio(self, load):
        load.side_effect = RuntimeError("decoder details")

        with self.assertRaisesRegex(
            AudioProcessingError, "音声を読み込めませんでした"
        ) as context:
            process_audio_file("broken.wav")

        self.assertNotIn("decoder details", str(context.exception))

    @patch("services.audio_processing.librosa.load")
    def test_rejects_audio_longer_than_twenty_minutes(self, load):
        load.return_value = (
            np.zeros(MAX_AUDIO_SECONDS + 1, dtype=np.float32),
            1,
        )

        with self.assertRaisesRegex(AudioProcessingError, "20分以内"):
            process_audio_file("too-long.wav")

    @patch("services.audio_processing.librosa.load")
    def test_rejects_unsupported_sample_rate(self, load):
        load.return_value = (np.ones(1_000, dtype=np.float32), 7_000)

        with self.assertRaisesRegex(AudioProcessingError, "8000 Hz以上"):
            process_audio_file("low-rate.wav")


if __name__ == "__main__":
    unittest.main()
