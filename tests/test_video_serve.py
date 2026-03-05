"""Unit tests for video serving endpoint with HTTP 206 range support.

Tests range-request serving, whitelist enforcement, 404 handling,
and 416 range-not-satisfiable errors.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def video_dir(tmp_path):
    """Create a temp directory with a fake video file."""
    video_file = tmp_path / "video1.mp4"
    # Create 2048 bytes of known content for range testing
    video_file.write_bytes(bytes(range(256)) * 8)
    return tmp_path


@pytest.fixture
def client(video_dir):
    """Create a test client with VIDEO_DIR pointing to temp directory."""
    with patch.dict(os.environ, {"VIDEO_DIR": str(video_dir)}):
        # Need to re-import to pick up the patched env
        from dashboard.web import DashboardState, create_dashboard_app
        from detector.zone_config import ZoneConfigManager

        state = DashboardState()
        zm = ZoneConfigManager("calibration.json")
        app = create_dashboard_app(state=state, zone_manager=zm)
        yield TestClient(app)


class TestVideoServeFullFile:
    """Tests for GET /api/videos/{filename} without Range header."""

    def test_get_full_video(self, client: TestClient, video_dir):
        """GET /api/videos/video1.mp4 without Range returns 200 with full file."""
        resp = client.get("/api/videos/video1.mp4")
        assert resp.status_code == 200
        assert resp.headers["accept-ranges"] == "bytes"
        assert resp.headers["content-length"] == "2048"
        assert len(resp.content) == 2048

    def test_content_type_is_video_mp4(self, client: TestClient, video_dir):
        """Response has video/mp4 content type."""
        resp = client.get("/api/videos/video1.mp4")
        assert "video/mp4" in resp.headers["content-type"]


class TestVideoServeRangeRequest:
    """Tests for GET /api/videos/{filename} with Range header."""

    def test_range_returns_206(self, client: TestClient, video_dir):
        """GET with Range: bytes=0-1023 returns 206 with Content-Range."""
        resp = client.get("/api/videos/video1.mp4", headers={"Range": "bytes=0-1023"})
        assert resp.status_code == 206
        assert resp.headers["content-range"] == "bytes 0-1023/2048"
        assert resp.headers["accept-ranges"] == "bytes"
        assert resp.headers["content-length"] == "1024"
        assert len(resp.content) == 1024

    def test_range_partial_end(self, client: TestClient, video_dir):
        """GET with Range: bytes=1024- returns rest of file."""
        resp = client.get("/api/videos/video1.mp4", headers={"Range": "bytes=1024-"})
        assert resp.status_code == 206
        assert resp.headers["content-range"] == "bytes 1024-2047/2048"
        assert len(resp.content) == 1024

    def test_range_beyond_file_size_returns_416(self, client: TestClient, video_dir):
        """Range beyond file size returns 416 Range Not Satisfiable."""
        resp = client.get("/api/videos/video1.mp4", headers={"Range": "bytes=3000-4000"})
        assert resp.status_code == 416


class TestVideoServeErrors:
    """Tests for 404 and whitelist enforcement."""

    def test_nonexistent_file_returns_404(self, client: TestClient):
        """GET /api/videos/video2.mp4 for missing file returns 404."""
        resp = client.get("/api/videos/video2.mp4")
        assert resp.status_code == 404

    def test_disallowed_file_returns_404(self, client: TestClient):
        """GET /api/videos/malicious.mp4 (not in whitelist) returns 404."""
        resp = client.get("/api/videos/malicious.mp4")
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client: TestClient):
        """Path traversal attempts are blocked by whitelist."""
        resp = client.get("/api/videos/../.env")
        # FastAPI may normalize this or the whitelist blocks it
        assert resp.status_code in (404, 422)
