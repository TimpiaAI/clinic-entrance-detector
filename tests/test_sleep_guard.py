"""Unit tests for api/sleep_guard.py wake-lock endpoints.

Tests all wake-lock activation, deactivation, and status scenarios
with mocked wakepy to avoid actual OS-level sleep prevention.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import api.sleep_guard as sleep_guard_module


def _make_app():
    """Create a minimal FastAPI app with the sleep_guard router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(sleep_guard_module.router)
    return app


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level globals before each test."""
    sleep_guard_module._keep_ctx = None
    sleep_guard_module._mode = None
    yield
    # Cleanup after test
    sleep_guard_module._keep_ctx = None
    sleep_guard_module._mode = None


@pytest.fixture
def client():
    return TestClient(_make_app())


class TestActivateWakeLock:
    """Tests for POST /api/system/wake-lock."""

    def test_activate_when_not_active(self, client: TestClient):
        """POST /wake-lock when not active activates wake lock and returns active."""
        mock_mode = MagicMock()
        mock_mode.active = True

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_mode)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch.object(sleep_guard_module.keep, "presenting", return_value=mock_ctx):
            resp = client.post("/api/system/wake-lock")

        assert resp.status_code == 200
        assert resp.json() == {"status": "active"}

    def test_activate_when_already_active(self, client: TestClient):
        """POST /wake-lock when already active returns already_active."""
        mock_mode = MagicMock()
        mock_mode.active = True
        sleep_guard_module._mode = mock_mode
        sleep_guard_module._keep_ctx = MagicMock()

        resp = client.post("/api/system/wake-lock")
        assert resp.status_code == 200
        assert resp.json() == {"status": "already_active"}

    def test_activate_when_mode_not_active(self, client: TestClient):
        """POST /wake-lock when Mode.active is False returns failed and cleans up."""
        mock_mode = MagicMock()
        mock_mode.active = False

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_mode)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch.object(sleep_guard_module.keep, "presenting", return_value=mock_ctx):
            resp = client.post("/api/system/wake-lock")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert "detail" in data
        # Verify cleanup happened
        assert sleep_guard_module._keep_ctx is None
        assert sleep_guard_module._mode is None
        # Verify __exit__ was called to release resources
        mock_ctx.__exit__.assert_called_once_with(None, None, None)


class TestReleaseWakeLock:
    """Tests for POST /api/system/wake-lock/release."""

    def test_release_when_active(self, client: TestClient):
        """POST /wake-lock/release when active deactivates and returns inactive."""
        mock_ctx = MagicMock()
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_mode = MagicMock()
        mock_mode.active = True

        sleep_guard_module._keep_ctx = mock_ctx
        sleep_guard_module._mode = mock_mode

        resp = client.post("/api/system/wake-lock/release")
        assert resp.status_code == 200
        assert resp.json() == {"status": "inactive"}
        # Verify cleanup
        assert sleep_guard_module._keep_ctx is None
        assert sleep_guard_module._mode is None
        mock_ctx.__exit__.assert_called_once_with(None, None, None)

    def test_release_when_not_active(self, client: TestClient):
        """POST /wake-lock/release when not active returns already_inactive."""
        resp = client.post("/api/system/wake-lock/release")
        assert resp.status_code == 200
        assert resp.json() == {"status": "already_inactive"}


class TestWakeLockStatus:
    """Tests for wake_lock_status() function."""

    def test_status_when_no_lock(self):
        """wake_lock_status() returns active=False when no lock held."""
        result = sleep_guard_module.wake_lock_status()
        assert result == {"active": False}

    def test_status_when_lock_active(self):
        """wake_lock_status() returns active=True when lock is held."""
        mock_mode = MagicMock()
        mock_mode.active = True
        sleep_guard_module._mode = mock_mode
        sleep_guard_module._keep_ctx = MagicMock()

        result = sleep_guard_module.wake_lock_status()
        assert result == {"active": True}

    def test_status_when_mode_inactive(self):
        """wake_lock_status() returns active=False when mode exists but not active."""
        mock_mode = MagicMock()
        mock_mode.active = False
        sleep_guard_module._mode = mock_mode

        result = sleep_guard_module.wake_lock_status()
        assert result == {"active": False}
