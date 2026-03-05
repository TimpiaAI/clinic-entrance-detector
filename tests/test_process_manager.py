"""Unit tests for api.process_manager module.

Tests use mocked subprocess.Popen and psutil.Process to avoid
actually spawning the detector. State is reset between tests
via module-level global reset.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset the module-level _detector_proc singleton between tests."""
    import api.process_manager as pm

    pm._detector_proc = None
    yield
    pm._detector_proc = None


class TestStartDetector:
    """Tests for start_detector()."""

    @patch("api.process_manager.subprocess.Popen")
    def test_start_when_not_running_returns_started(self, mock_popen):
        from api.process_manager import start_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        result = start_detector()

        assert result["status"] == "started"
        assert result["pid"] == 12345
        mock_popen.assert_called_once()

    @patch("api.process_manager.subprocess.Popen")
    def test_start_when_already_running_returns_already_running(self, mock_popen):
        from api.process_manager import start_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Still running
        mock_popen.return_value = mock_proc

        # First start
        start_detector()

        # Second start (already running)
        result = start_detector()

        assert result["status"] == "already_running"
        assert result["pid"] == 12345


class TestStopDetector:
    """Tests for stop_detector()."""

    def test_stop_when_not_running_returns_not_running(self):
        from api.process_manager import stop_detector

        result = stop_detector()

        assert result["status"] == "not_running"

    @patch("api.process_manager.psutil.Process")
    @patch("api.process_manager.psutil.wait_procs")
    @patch("api.process_manager.subprocess.Popen")
    def test_stop_when_running_returns_stopped(
        self, mock_popen, mock_wait_procs, mock_psutil_process
    ):
        from api.process_manager import start_detector, stop_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Running
        mock_popen.return_value = mock_proc

        # Set up psutil mocks
        mock_parent = MagicMock()
        mock_child = MagicMock()
        mock_parent.children.return_value = [mock_child]
        mock_psutil_process.return_value = mock_parent
        mock_wait_procs.return_value = ([mock_parent, mock_child], [])

        start_detector()
        result = stop_detector()

        assert result["status"] == "stopped"
        assert result["pid"] == 12345

    @patch("api.process_manager.psutil.Process")
    @patch("api.process_manager.psutil.wait_procs")
    @patch("api.process_manager.subprocess.Popen")
    def test_stop_uses_psutil_tree_kill(
        self, mock_popen, mock_wait_procs, mock_psutil_process
    ):
        """Verify children are enumerated and terminated before parent."""
        from api.process_manager import start_detector, stop_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        mock_parent = MagicMock()
        mock_child1 = MagicMock()
        mock_child2 = MagicMock()
        mock_parent.children.return_value = [mock_child1, mock_child2]
        mock_psutil_process.return_value = mock_parent
        mock_wait_procs.return_value = (
            [mock_parent, mock_child1, mock_child2],
            [],
        )

        start_detector()
        stop_detector()

        # Children must be terminated
        mock_child1.terminate.assert_called_once()
        mock_child2.terminate.assert_called_once()
        # Parent must be terminated
        mock_parent.terminate.assert_called_once()
        # children(recursive=True) must be called
        mock_parent.children.assert_called_once_with(recursive=True)
        # wait_procs must be called with parent + children
        mock_wait_procs.assert_called_once()

    @patch("api.process_manager.psutil.Process")
    @patch("api.process_manager.psutil.wait_procs")
    @patch("api.process_manager.subprocess.Popen")
    def test_stop_force_kills_survivors(
        self, mock_popen, mock_wait_procs, mock_psutil_process
    ):
        """Processes that survive terminate() get force-killed."""
        from api.process_manager import start_detector, stop_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        mock_parent = MagicMock()
        mock_survivor = MagicMock()
        mock_parent.children.return_value = []
        mock_psutil_process.return_value = mock_parent
        # Survivor did not exit after terminate
        mock_wait_procs.return_value = ([], [mock_survivor])

        start_detector()
        stop_detector()

        mock_survivor.kill.assert_called_once()


class TestDetectorStatus:
    """Tests for detector_status()."""

    def test_status_when_no_process_returns_not_running(self):
        from api.process_manager import detector_status

        result = detector_status()

        assert result["running"] is False
        assert result["pid"] is None
        assert result["exit_code"] is None

    @patch("api.process_manager.subprocess.Popen")
    def test_status_after_start_returns_running(self, mock_popen):
        from api.process_manager import detector_status, start_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Still running
        mock_popen.return_value = mock_proc

        start_detector()
        result = detector_status()

        assert result["running"] is True
        assert result["pid"] == 12345
        assert result["exit_code"] is None

    @patch("api.process_manager.subprocess.Popen")
    def test_status_after_process_exits_returns_exit_code(self, mock_popen):
        from api.process_manager import detector_status, start_detector

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = 1  # Exited with code 1
        mock_popen.return_value = mock_proc

        start_detector()
        result = detector_status()

        assert result["running"] is False
        assert result["pid"] == 12345
        assert result["exit_code"] == 1
