"""Local speech-to-text with faster-whisper (no audio leaves the laptop)."""
from pathlib import Path

from core.config import WHISPER_MODEL

_model = None


def _get_model():
    global _model
    if _model is None:
        # The first call downloads the model from Hugging Face. Corporate networks that inspect HTTPS
        # re-sign traffic with a root certificate that's in the Windows store but not in Python's
        # bundle; truststore makes Python verify against the Windows store (verification stays on).
        import truststore
        truststore.inject_into_ssl()
        from faster_whisper import WhisperModel  # slow import; only load when a video is analyzed
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def _read_wav(wav_path: Path):
    """16 kHz mono 16-bit WAV (as written by video.extract_audio) -> float32 array in [-1, 1].
    Passing an array skips faster-whisper's PyAV decoder, which breaks with newer PyAV versions."""
    import wave
    import numpy as np
    with wave.open(str(wav_path), "rb") as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("expected 16 kHz mono 16-bit WAV")
        pcm = w.readframes(w.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(wav_path: Path) -> dict:
    """Returns {language, segments: [{start, end, text}]}. Empty segments if no speech is detected."""
    # vad_filter skips non-speech stretches, which reduces made-up text over music or silence.
    segments, info = _get_model().transcribe(_read_wav(wav_path), vad_filter=True, beam_size=5)
    segs = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments if s.text.strip()]
    return {"language": info.language if segs else None, "segments": segs}
