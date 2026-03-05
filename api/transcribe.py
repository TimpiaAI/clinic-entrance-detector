"""Transcription endpoint: accept audio, transcribe with Faster Whisper, extract CNP/email."""

from __future__ import annotations

import os
import re
import tempfile

from fastapi import APIRouter, File, Form, UploadFile

router = APIRouter(tags=["transcribe"])

# Lazy-loaded Whisper model singleton -- NOT loaded at import time (see Pitfall 2).
_model = None


def get_model():
    """Lazy-load the Whisper model on first request and reuse for all subsequent calls."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            os.getenv("WHISPER_MODEL", "medium"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        )
    return _model


def extract_cnp(text: str) -> str | None:
    """Extract Romanian CNP (13 digits) from transcribed speech.

    - 13+ digits: return first 13 (full CNP)
    - 10-12 digits: return all (partial CNP for user confirmation)
    - <10 digits: return None
    """
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 13:
        return digits[:13]
    if len(digits) >= 10:
        return digits
    return None


def extract_email(text: str) -> str | None:
    """Extract email from Romanian speech transcription.

    Handles common Whisper misrecognitions of spoken email addresses:
    - "arond/arong/aroon/arun/arung/at/et/ad/a run/a rung" -> "@"
    - "punct/dot" before com/ro/net/org/gmail/yahoo -> "."

    Ported from controller.py (lines 213-233) -- production-tested patterns.
    """
    attempt = text.lower()

    # Normalize "punct"/"dot" before common TLD/domain words -> "."
    attempt = re.sub(
        r"\s*(punct|dot|\.)\s*(com|ro|net|org|gmail|yahoo)",
        r".\2",
        attempt,
    )

    # Normalize Romanian speech variants of "@"
    # Long patterns first (a rung, a run, arond, etc.) then short patterns with word boundaries
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

    # Find the last "@" occurrence and extract local + domain parts around it
    # Use the rightmost "@" to handle cases where text precedes the email
    last_at = attempt.rfind("@")
    raw_local = attempt[:last_at]
    raw_domain = attempt[last_at + 1:]

    # Local part: take only the last whitespace-delimited token (ignore preceding text)
    local_tokens = raw_local.strip().split()
    local = local_tokens[-1] if local_tokens else ""
    local = local.replace(" ", "").rstrip(".")

    # Domain part: take the first whitespace-delimited token(s) up to the TLD
    domain = raw_domain.replace(" ", "").lstrip(".")

    if not local or not domain:
        return None

    result = local + "@" + domain
    result = re.sub(r"[^a-z0-9@._\-]", "", result)
    return result if result else None


@router.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    initial_prompt: str | None = Form(None),
):
    """Accept an audio file (WebM/WAV), transcribe with Whisper, extract CNP and email."""
    model = get_model()

    # Determine temp file suffix from content type
    suffix = ".webm"
    if audio.content_type and "wav" in audio.content_type:
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        kwargs: dict = {"language": "ro", "vad_filter": True}
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        segments, _ = model.transcribe(tmp_path, **kwargs)
        text = " ".join(s.text for s in segments).strip()
    finally:
        os.unlink(tmp_path)

    cnp = extract_cnp(text)
    email = extract_email(text)

    return {"text": text, "cnp": cnp, "email": email}
