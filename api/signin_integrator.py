"""Integration layer between detector entry events and signin workflow."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any
from datetime import datetime, timezone

from detector.entry_analyzer import EntryEvent
from .signin_manager import SigninManager


@dataclass
class DetectionEntry:
    """Captured person entry event."""

    event: str  # "person_entered"
    timestamp: str  # ISO format
    person_id: int
    confidence: float
    bbox: tuple[int, int, int, int]
    snapshot_b64: str  # Base64 encoded image
    frame_number: int
    total_entries_today: int


@dataclass
class SigninEvent:
    """Event for signin workflow triggered by detection."""

    entry: DetectionEntry
    detected_name: str | None = None  # Name from transcription
    session_id: str | None = None  # Signin session ID
    fuzzy_matches_count: int = 0
    status: str = "waiting_for_name"  # waiting_for_name → transcribing → ready_for_confirm


class SigninIntegrator:
    """Bridges detector entry events and signin workflow."""

    def __init__(self, signin_manager: SigninManager, logger: Any = None):
        self.signin = signin_manager
        self.logger = logger

        self._lock = threading.RLock()
        self.pending_entries: dict[int, SigninEvent] = {}  # person_id -> SigninEvent
        self.recent_events: list[SigninEvent] = []  # Last 50 events

    def on_person_entered(
        self,
        event: EntryEvent,
        snapshot_b64: str,
        frame_number: int,
        total_entries_today: int,
    ) -> SigninEvent:
        """
        Called when detector detects person entry.

        Returns SigninEvent that can be pushed to dashboard for UI.
        """
        detection = DetectionEntry(
            event="person_entered",
            timestamp=event.timestamp,
            person_id=event.person_id,
            confidence=event.confidence,
            bbox=event.bbox,
            snapshot_b64=snapshot_b64,
            frame_number=frame_number,
            total_entries_today=total_entries_today,
        )

        signin_event = SigninEvent(
            entry=detection,
            status="waiting_for_name",
        )

        with self._lock:
            self.pending_entries[event.person_id] = signin_event
            self.recent_events.insert(0, signin_event)
            if len(self.recent_events) > 50:
                self.recent_events.pop()

        if self.logger:
            self.logger.info(
                "Person detected - waiting for name transcription",
                extra={
                    "extra": {
                        "person_id": event.person_id,
                        "confidence": event.confidence,
                    }
                },
            )

        return signin_event

    def on_name_detected(
        self,
        person_id: int,
        detected_name: str,
    ) -> tuple[SigninEvent | None, str]:
        """
        Called when transcriber detects person's name (from microphone).

        Args:
            person_id: Detected person ID from tracker
            detected_name: Name transcribed from audio

        Returns:
            (SigninEvent with fuzzy matches, error_message)
        """
        with self._lock:
            signin_event = self.pending_entries.get(person_id)
            if not signin_event:
                return None, f"No pending entry for person {person_id}"

            signin_event.detected_name = detected_name
            signin_event.status = "transcribing"

        # Start signin session with fuzzy matching
        session, matches = self.signin.start_signin_session(detected_name)
        session_id = str(id(session))

        with self._lock:
            signin_event.session_id = session_id
            signin_event.fuzzy_matches_count = len(matches)
            signin_event.status = "ready_for_confirm"

        if self.logger:
            self.logger.info(
                "Name detected - fuzzy matches found",
                extra={
                    "extra": {
                        "person_id": person_id,
                        "detected_name": detected_name,
                        "matches_count": len(matches),
                        "session_id": session_id,
                    }
                },
            )

        return signin_event, ""

    def on_appointment_confirmed(
        self,
        person_id: int,
        session_id: str,
        appointment_id: int,
        phone: str,
        cnp: str | None = None,
    ) -> tuple[bool, str]:
        """
        Called when staff confirms appointment selection and phone.

        Args:
            person_id: Tracked person ID
            session_id: Signin session ID
            appointment_id: Selected appointment ID
            phone: Phone number for verification
            cnp: Romanian CNP for doctor routing

        Returns:
            (success, error_message)
        """
        success, error = self.signin.confirm_appointment(
            session_id,
            appointment_id,
            phone,
            cnp=cnp,
        )

        if not success:
            return False, error

        with self._lock:
            signin_event = self.pending_entries.get(person_id)
            if signin_event:
                signin_event.status = "appointment_confirmed"

        if self.logger:
            self.logger.info(
                "Appointment confirmed",
                extra={
                    "extra": {
                        "person_id": person_id,
                        "appointment_id": appointment_id,
                        "phone": phone[:2] + "*" * len(phone[2:-2]) + phone[-2:],  # Mask
                    }
                },
            )

        return True, ""

    def on_signin_complete(
        self,
        person_id: int,
        session_id: str,
    ) -> tuple[dict[str, Any] | None, str]:
        """
        Called when staff initiates final signin (creates presentation).

        Args:
            person_id: Tracked person ID
            session_id: Signin session ID

        Returns:
            (presentation_response, error_message)
        """
        response, error = self.signin.complete_signin(session_id)

        if not error:
            with self._lock:
                signin_event = self.pending_entries.get(person_id)
                if signin_event:
                    signin_event.status = "presentation_created"

            if self.logger:
                self.logger.info(
                    "Signin completed - presentation created",
                    extra={
                        "extra": {
                            "person_id": person_id,
                            "presentation_id": response.get("presentation_id"),
                        }
                    },
                )
        else:
            if self.logger:
                self.logger.error(
                    "Signin failed",
                    extra={"extra": {"person_id": person_id, "error": error}},
                )

        return response, error

    def clear_entry(self, person_id: int) -> None:
        """Clear completed signin session."""
        with self._lock:
            signin_event = self.pending_entries.pop(person_id, None)
            if signin_event and signin_event.session_id:
                self.signin.clear_session(signin_event.session_id)

    def get_pending_entry(self, person_id: int) -> SigninEvent | None:
        """Get pending signin event for a person."""
        with self._lock:
            return self.pending_entries.get(person_id)

    def get_recent_events(self, limit: int = 20) -> list[SigninEvent]:
        """Get recent signin events."""
        with self._lock:
            return self.recent_events[:limit]

    def get_status(self) -> dict[str, Any]:
        """Get integrator status."""
        with self._lock:
            return {
                "pending_entries": len(self.pending_entries),
                "recent_events": len(self.recent_events),
                "signin_manager_status": self.signin.get_status(),
            }
