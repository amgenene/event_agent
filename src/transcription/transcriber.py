"""Whisper-based transcription for audio files."""

import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
_executor = ThreadPoolExecutor(max_workers=1)
_model = None


def get_model():
    """Get or initialize the Whisper model (singleton)."""
    global _model
    if _model is None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper not installed")
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
        logger.info("Whisper model '%s' loaded", MODEL_NAME)
    return _model


def convert_to_wav(input_path: str, out_path: str) -> str:
    """Convert audio file to 16kHz mono WAV format for Whisper.

    Args:
        input_path: Path to input audio file
        out_path: Path to output WAV file

    Returns:
        Path to the converted WAV file
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        out_path,
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path


def transcribe_file(wav_path: str) -> str:
    """Transcribe a WAV file to text using Whisper.

    Args:
        wav_path: Path to WAV file (16kHz mono recommended)

    Returns:
        Transcribed text
    """
    model = get_model()
    segments, _ = model.transcribe(wav_path, beam_size=5)
    text = "".join([s.text for s in segments])
    return text
