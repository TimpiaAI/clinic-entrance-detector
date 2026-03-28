"""Signin workflow with fuzzy name matching and phone confirmation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
from rapidfuzz import fuzz
import threading

from .functie_client import Doctor, Appointment, FunctieAPIClient, parse_cnp, get_medic_id_from_cnp


@dataclass
class FuzzyMatch:
    """Fuzzy match result for an appointment."""

    appointment: Appointment
    score: float  # 0-100


@dataclass
class SigninSession:
    """Active signin session - user detected, matching in progress."""

    person_name: str  # Detected/transcribed name
    detected_at: str  # ISO timestamp
    fuzzy_matches: list[FuzzyMatch] = field(default_factory=list)
    selected_appointment: Appointment | None = None
    phone_confirmed: str | None = None
    cnp: str | None = None
    presentation_id: int | None = None


class SigninManager:
    """Manages doctor data, daily appointments, and signin workflows."""

    def __init__(self, functie_client: FunctieAPIClient, logger: Any = None):
        self.functie = functie_client
        self.logger = logger

        self._lock = threading.RLock()
        self.doctors: list[Doctor] = []
        self.all_appointments: list[Appointment] = []
        self.last_sync: str | None = None

        self.active_sessions: dict[str, SigninSession] = {}

    def initialize(self) -> tuple[bool, str]:
        """Fetch doctors on startup. Returns (success, error_msg)."""
        with self._lock:
            doctors, error = self.functie.get_doctors()
            if error:
                msg = f"Failed to load doctors: {error}"
                if self.logger:
                    self.logger.error(msg)
                return False, msg

            self.doctors = doctors
            if self.logger:
                self.logger.info(f"Initialized with {len(doctors)} doctors")
            return True, ""

    def refresh_appointments(self) -> tuple[bool, str]:
        """Fetch today's appointments for all doctors. Returns (success, error_msg)."""
        with self._lock:
            all_appts = []
            for doctor in self.doctors:
                appts, error = self.functie.get_today_appointments(doctor.id)
                if error:
                    if self.logger:
                        self.logger.warning(f"Failed to get appointments for {doctor.full_name}: {error}")
                    continue
                all_appts.extend(appts)

            self.all_appointments = all_appts
            self.last_sync = datetime.now(timezone.utc).isoformat()
            if self.logger:
                self.logger.info(f"Synced {len(all_appts)} appointments across {len(self.doctors)} doctors")
            return True, ""

    def find_fuzzy_matches(
        self,
        detected_name: str,
        threshold: int = 60,
        top_n: int = 5,
    ) -> list[FuzzyMatch]:
        """
        Find appointment matches using fuzzy name matching.

        Args:
            detected_name: Detected/transcribed person name (e.g., "Pica Ovidiu")
            threshold: Minimum match score (0-100)
            top_n: Return top N matches

        Returns:
            Sorted list of FuzzyMatch results
        """
        with self._lock:
            if not self.all_appointments:
                return []

            matches = []
            for appt in self.all_appointments:
                # Match against full name
                score = fuzz.token_set_ratio(detected_name.lower(), appt.full_name.lower())
                if score >= threshold:
                    matches.append(FuzzyMatch(appointment=appt, score=score))

            # Sort by score descending
            matches.sort(key=lambda m: m.score, reverse=True)
            return matches[:top_n]

    def start_signin_session(
        self,
        detected_name: str,
        session_id: str | None = None,
    ) -> tuple[SigninSession, list[FuzzyMatch]]:
        """
        Start a signin session for a detected person.

        Args:
            detected_name: Transcribed/detected person name
            session_id: Optional custom session ID (defaults to timestamp)

        Returns:
            (SigninSession, fuzzy_matches)
        """
        if session_id is None:
            session_id = datetime.now(timezone.utc).isoformat()

        fuzzy_matches = self.find_fuzzy_matches(detected_name)

        session = SigninSession(
            person_name=detected_name,
            detected_at=datetime.now(timezone.utc).isoformat(),
            fuzzy_matches=fuzzy_matches,
        )

        with self._lock:
            self.active_sessions[session_id] = session

        if self.logger:
            self.logger.info(
                f"Started signin session {session_id}: '{detected_name}' "
                f"({len(fuzzy_matches)} fuzzy matches)"
            )

        return session, fuzzy_matches

    def confirm_appointment(
        self,
        session_id: str,
        appointment_id: int,
        phone: str,
        cnp: str | None = None,
    ) -> tuple[bool, str]:
        """
        Confirm an appointment selection, phone number, and CNP for a session.

        Args:
            session_id: Active session ID
            appointment_id: Selected appointment ID
            phone: Phone number confirmation
            cnp: Romanian CNP (determines doctor routing)

        Returns:
            (success, message)
        """
        with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False, "Session not found"

            # Find appointment in fuzzy matches
            appt = None
            for match in session.fuzzy_matches:
                if match.appointment.id == appointment_id:
                    appt = match.appointment
                    break

            if not appt:
                return False, "Appointment not found in matches"

            # If CNP provided, validate and auto-route doctor
            if cnp:
                parsed = parse_cnp(cnp)
                if not parsed:
                    return False, "CNP invalid"
                session.cnp = cnp
                # Override medic_id based on CNP gender
                appt.medic_id = get_medic_id_from_cnp(cnp) or appt.medic_id

            session.selected_appointment = appt
            session.phone_confirmed = phone
            if self.logger:
                self.logger.info(f"Confirmed appointment {appointment_id} with phone {phone}, cnp={'***' if cnp else 'none'}")
            return True, ""

    def complete_signin(
        self,
        session_id: str,
        email: str = "noemail@clinic.local",
        address: str = "Clinic",
    ) -> tuple[dict[str, Any] | None, str]:
        """
        Complete signin by creating presentation.

        Args:
            session_id: Active session ID
            email: Patient email (optional, has default)
            address: Patient address (optional, has default)

        Returns:
            (presentation_response, error_msg)
        """
        with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return None, "Session not found"

            if not session.selected_appointment:
                return None, "No appointment selected"

            if not session.phone_confirmed:
                return None, "Phone not confirmed"

            appt = session.selected_appointment

            # Create presentation
            response, error = self.functie.create_presentation(
                medic_id=appt.medic_id,
                first_name=appt.first_name,
                last_name=appt.last_name,
                phone=session.phone_confirmed,
                email=email,
                address=address,
                appointment_id=appt.id,
                patient_id=appt.patient_id,
                cnp=session.cnp,
            )

            if error:
                return None, error

            session.presentation_id = response.get("presentation_id")
            if self.logger:
                self.logger.info(f"Signin complete: presentation_id={session.presentation_id}")

            return response, ""

    def get_session(self, session_id: str) -> SigninSession | None:
        """Get signin session by ID."""
        with self._lock:
            return self.active_sessions.get(session_id)

    def clear_session(self, session_id: str) -> None:
        """Remove completed signin session."""
        with self._lock:
            self.active_sessions.pop(session_id, None)

    def get_status(self) -> dict[str, Any]:
        """Get manager status."""
        with self._lock:
            return {
                "doctors_count": len(self.doctors),
                "appointments_count": len(self.all_appointments),
                "last_sync": self.last_sync,
                "active_sessions": len(self.active_sessions),
            }
