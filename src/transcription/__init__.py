"""Transcription module for audio-to-text conversion using Whisper."""

from .transcriber import get_model, convert_to_wav, transcribe_file

__all__ = ["get_model", "convert_to_wav", "transcribe_file"]
