"""Transcription endpoint: accept audio, transcribe via Deepgram or local Whisper, extract CNP/email."""

from __future__ import annotations

import logging
import os
import re
import tempfile
import time

import httpx
from fastapi import APIRouter, File, Form, UploadFile

log = logging.getLogger("clinic_detector")

router = APIRouter(tags=["transcribe"])

# ---------------------------------------------------------------------------
# Deepgram transcription
# ---------------------------------------------------------------------------

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-3")
DEEPGRAM_LANGUAGE = os.getenv("DEEPGRAM_LANGUAGE", "ro")


async def _transcribe_deepgram(audio_bytes: bytes, content_type: str) -> str:
    """Send audio to Deepgram pre-recorded API and return transcript text."""
    url = "https://api.deepgram.com/v1/listen"
    params = {
        "model": DEEPGRAM_MODEL,
        "language": DEEPGRAM_LANGUAGE,
        "smart_format": "true",
        "punctuate": "true",
    }
    # Deepgram needs a clean content type (no codecs parameter)
    clean_type = content_type.split(";")[0].strip() if content_type else "audio/webm"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": clean_type,
    }
    log.info("Deepgram request: model=%s lang=%s audio_size=%d content_type=%s",
             DEEPGRAM_MODEL, DEEPGRAM_LANGUAGE, len(audio_bytes), content_type)
    t0 = time.monotonic()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, params=params, headers=headers, content=audio_bytes)
        resp.raise_for_status()
        data = resp.json()

    elapsed_ms = (time.monotonic() - t0) * 1000
    log.info("Deepgram raw response: %s", data)

    # Extract transcript from Deepgram response
    channels = data.get("results", {}).get("channels", [])
    transcript = ""
    confidence = 0.0
    if channels:
        alternatives = channels[0].get("alternatives", [])
        if alternatives:
            transcript = alternatives[0].get("transcript", "")
            confidence = alternatives[0].get("confidence", 0.0)

    log.info("Deepgram result: text=%r confidence=%.3f elapsed=%.0fms",
             transcript, confidence, elapsed_ms)
    return transcript


# ---------------------------------------------------------------------------
# Local Whisper fallback
# ---------------------------------------------------------------------------

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            os.getenv("WHISPER_MODEL", "medium"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        )
    return _whisper_model


def _transcribe_whisper(tmp_path: str, initial_prompt: str | None) -> str:
    model = _get_whisper_model()
    kwargs: dict = {"language": "ro", "vad_filter": True}
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
    segments, _ = model.transcribe(tmp_path, **kwargs)
    return " ".join(s.text for s in segments).strip()


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_cnp(text: str) -> str | None:
    """Extract Romanian CNP (13 digits) from transcribed speech."""
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 13:
        return digits[:13]
    if len(digits) >= 10:
        return digits
    return None


def extract_email(text: str) -> str | None:
    """Extract email from Romanian speech transcription.

    Handles common misrecognitions of spoken email addresses:
    - "arond/arong/aroon/arun/arung/at/et/ad/a run/a rung" -> "@"
    - "punct/dot" before com/ro/net/org/gmail/yahoo -> "."
    """
    attempt = text.lower()

    attempt = re.sub(
        r"\s*(punct|dot|\.)\s*(com|ro|net|org|gmail|yahoo)",
        r".\2",
        attempt,
    )

    attempt = re.sub(
        r"\s*(a rung|a run|arond|arong|aroon|aron\u0434|arun|arung|@)\s*",
        "@",
        attempt,
    )
    attempt = re.sub(
        r"\b(at|et|ad)\b",
        "@",
        attempt,
    )

    if "@" not in attempt or "." not in attempt.split("@")[-1]:
        return None

    last_at = attempt.rfind("@")
    raw_local = attempt[:last_at]
    raw_domain = attempt[last_at + 1:]

    local_tokens = raw_local.strip().split()
    local = local_tokens[-1] if local_tokens else ""
    local = local.replace(" ", "").rstrip(".")

    domain = raw_domain.replace(" ", "").lstrip(".")

    if not local or not domain:
        return None

    result = local + "@" + domain
    result = re.sub(r"[^a-z0-9@._\-]", "", result)
    return result if result else None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

STT_PROVIDER = os.getenv("STT_PROVIDER", "deepgram").lower()


@router.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    initial_prompt: str | None = Form(None),
):
    """Accept an audio file (WebM/WAV), transcribe, extract CNP and email."""
    content = await audio.read()
    content_type = audio.content_type or "audio/webm"

    log.info("Transcribe request: provider=%s audio_size=%d content_type=%s",
             STT_PROVIDER, len(content), content_type)

    if STT_PROVIDER == "deepgram" and DEEPGRAM_API_KEY:
        text = await _transcribe_deepgram(content, content_type)
    else:
        # Fallback to local Whisper
        suffix = ".webm"
        if "wav" in content_type:
            suffix = ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            text = _transcribe_whisper(tmp_path, initial_prompt)
        finally:
            os.unlink(tmp_path)

    cnp = extract_cnp(text)
    email = extract_email(text)

    log.info("Transcribe result: text=%r cnp=%s email=%s", text, cnp, email)
    return {"text": text, "cnp": cnp, "email": email}
