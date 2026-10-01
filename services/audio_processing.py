"""Audio processing for an exam-room-like listening preset."""

from dataclasses import dataclass

import librosa
import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt


MAX_AUDIO_SECONDS = 20 * 60
MIN_SAMPLE_RATE = 8_000
OUTPUT_PEAK = 0.92


class AudioProcessingError(Exception):
    """Raised when an audio file cannot be safely processed."""


@dataclass(frozen=True)
class ProcessedAudio:
    samples: np.ndarray
    sample_rate: int


def _create_room_impulse_response(sample_rate):
    """Create a deterministic synthetic room impulse response in memory."""
    duration_seconds = 0.35
    length = max(1, int(sample_rate * duration_seconds))
    time = np.arange(length, dtype=np.float32) / sample_rate
    decay = np.exp(-time * 12.0)

    rng = np.random.default_rng(2025)
    tail = rng.normal(0.0, 1.0, length).astype(np.float32)
    impulse_response = tail * decay * 0.025
    impulse_response[0] += 1.0

    for delay_seconds, amplitude in ((0.025, 0.32), (0.055, 0.20), (0.09, 0.12)):
        index = int(sample_rate * delay_seconds)
        if index < length:
            impulse_response[index] += amplitude

    energy = np.sqrt(np.sum(impulse_response**2))
    if energy > 0:
        impulse_response /= energy
    return impulse_response


def _apply_speaker_filter(samples, sample_rate):
    nyquist = sample_rate / 2
    if sample_rate < MIN_SAMPLE_RATE or nyquist <= 3_600:
        raise AudioProcessingError(
            f"{MIN_SAMPLE_RATE} Hz以上のサンプリングレートが必要です。"
        )

    high_pass = butter(4, 200, btype="highpass", fs=sample_rate, output="sos")
    low_pass = butter(4, 3_500, btype="lowpass", fs=sample_rate, output="sos")
    return sosfilt(low_pass, sosfilt(high_pass, samples))


def _add_environment_noise(samples, sample_rate):
    signal_rms = float(np.sqrt(np.mean(samples**2)))
    if signal_rms <= np.finfo(np.float32).eps:
        return samples

    rng = np.random.default_rng(311)
    noise = rng.normal(0.0, 1.0, len(samples)).astype(np.float32)
    noise_filter = butter(2, 1_500, btype="lowpass", fs=sample_rate, output="sos")
    noise = sosfilt(noise_filter, noise)
    noise_rms = float(np.sqrt(np.mean(noise**2)))
    if noise_rms > 0:
        noise *= signal_rms * 0.018 / noise_rms
    return samples + noise


def process_audio_file(input_path):
    try:
        samples, sample_rate = librosa.load(input_path, sr=None, mono=True)
    except Exception as error:
        raise AudioProcessingError(
            "音声を読み込めませんでした。正常なMP3またはWAVを選択してください。"
        ) from error

    if samples.size == 0 or sample_rate is None:
        raise AudioProcessingError("音声データが空です。")
    if not np.all(np.isfinite(samples)):
        raise AudioProcessingError("音声データに不正な値が含まれています。")

    duration_seconds = samples.size / sample_rate
    if duration_seconds > MAX_AUDIO_SECONDS:
        raise AudioProcessingError("音声の長さは20分以内にしてください。")

    filtered = _apply_speaker_filter(samples.astype(np.float32), sample_rate)
    impulse_response = _create_room_impulse_response(sample_rate)
    reverberated = fftconvolve(filtered, impulse_response, mode="full")
    processed = _add_environment_noise(reverberated, sample_rate)

    peak = float(np.max(np.abs(processed)))
    if peak > 0:
        processed = processed / peak * OUTPUT_PEAK

    return ProcessedAudio(
        samples=processed.astype(np.float32),
        sample_rate=int(sample_rate),
    )
