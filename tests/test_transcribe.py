"""Unit tests for api/transcribe.py -- CNP/email extraction and endpoint."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# --------------- extract_cnp tests ---------------


class TestExtractCnp:
    """Test CNP extraction from transcribed speech text."""

    def test_13_digit_string_returns_first_13(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("unu doi trei patru cinci sase sapte opt noua zero unu doi trei")
        # Text has no digits -- should return None (Romanian words for numbers)
        # But the plan says input "1234567890123" returns itself
        assert result is None

    def test_13_digits_embedded_returns_first_13(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("1234567890123")
        assert result == "1234567890123"

    def test_digits_spoken_with_spaces(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("numarul meu este 2 9 5 0 6 1 5 1 2 3 4 5 6")
        assert result == "2950615123456"

    def test_no_digits_returns_none(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("nu am cnp")
        assert result is None

    def test_fewer_than_10_digits_returns_none(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("partial 12345678")
        assert result is None

    def test_10_to_12_digits_returns_partial(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("doar zece 1234567890")
        assert result == "1234567890"

    def test_more_than_13_digits_returns_first_13(self):
        from api.transcribe import extract_cnp

        result = extract_cnp("12345678901234567")
        assert result == "1234567890123"


# --------------- extract_email tests ---------------


class TestExtractEmail:
    """Test email extraction from Romanian speech transcription."""

    def test_arond_gmail_punct_com(self):
        from api.transcribe import extract_email

        result = extract_email("ion arond gmail punct com")
        assert result == "ion@gmail.com"

    def test_arong_yahoo_punct_ro(self):
        from api.transcribe import extract_email

        result = extract_email("maria.pop arong yahoo punct ro")
        assert result == "maria.pop@yahoo.ro"

    def test_at_gmail_dot_com(self):
        from api.transcribe import extract_email

        result = extract_email("test at gmail dot com")
        assert result == "test@gmail.com"

    def test_no_email_returns_none(self):
        from api.transcribe import extract_email

        result = extract_email("nu am email")
        assert result is None

    def test_arung_hotmail(self):
        from api.transcribe import extract_email

        result = extract_email("adresa mea este ana123 a rung hotmail punct com")
        assert result == "ana123@hotmail.com"

    def test_arun_variant(self):
        from api.transcribe import extract_email

        result = extract_email("user arun example punct com")
        assert result == "user@example.com"

    def test_et_variant(self):
        from api.transcribe import extract_email

        result = extract_email("admin et company punct ro")
        assert result == "admin@company.ro"


# --------------- POST /api/transcribe endpoint test ---------------


class TestTranscribeEndpoint:
    """Test the POST /api/transcribe endpoint with a mocked Whisper model."""

    def test_transcribe_returns_expected_shape(self):
        from api.transcribe import router

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        # Mock the Whisper model before making requests
        mock_segment = MagicMock()
        mock_segment.text = "numarul meu este 2 9 5 0 6 1 5 1 2 3 4 5 6 email ion arond gmail punct com"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], None)

        with patch("api.transcribe._model", mock_model), \
             patch("api.transcribe.get_model", return_value=mock_model):
            client = TestClient(app)
            # Create a fake audio file
            fake_audio = io.BytesIO(b"\x00" * 100)
            response = client.post(
                "/api/transcribe",
                files={"audio": ("test.webm", fake_audio, "audio/webm")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "cnp" in data
        assert "email" in data
        assert data["cnp"] == "2950615123456"
        assert data["email"] == "ion@gmail.com"

    def test_transcribe_no_cnp_no_email(self):
        from api.transcribe import router

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        mock_segment = MagicMock()
        mock_segment.text = "buna ziua"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], None)

        with patch("api.transcribe._model", mock_model), \
             patch("api.transcribe.get_model", return_value=mock_model):
            client = TestClient(app)
            fake_audio = io.BytesIO(b"\x00" * 100)
            response = client.post(
                "/api/transcribe",
                files={"audio": ("test.webm", fake_audio, "audio/webm")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "buna ziua"
        assert data["cnp"] is None
        assert data["email"] is None
