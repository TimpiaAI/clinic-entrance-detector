"""REST API for signin workflow triggered by detector events."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .functie_client import parse_cnp, get_medic_id_from_cnp, MALE_DOCTOR_ID, FEMALE_DOCTOR_ID
from .signin_integrator import SigninIntegrator


class DetectNameRequest(BaseModel):
    """Request to process detected name."""

    person_id: int
    detected_name: str


class ConfirmAppointmentRequest(BaseModel):
    """Request to confirm appointment selection."""

    person_id: int
    session_id: str
    appointment_id: int
    phone: str
    cnp: str = ""


class CompleteSigninRequest(BaseModel):
    """Request to complete signin (create presentation)."""

    person_id: int
    session_id: str
    email: str = "noemail@clinic.local"
    address: str = "Clinic"


def create_signin_api_routes(integrator: SigninIntegrator) -> APIRouter:
    """Create signin API routes integrated with detector."""

    router = APIRouter(prefix="/api/signin", tags=["signin-detector"])

    @router.post("/detect-name")
    async def detect_name(req: DetectNameRequest) -> dict:
        """
        Process detected person name (from transcriber).

        Called when audio transcription returns a person's name.
        Returns fuzzy matched appointments for staff to confirm.
        """
        signin_event, error = integrator.on_name_detected(
            req.person_id,
            req.detected_name,
        )

        if error:
            raise HTTPException(status_code=400, detail=error)

        if not signin_event or not signin_event.session_id:
            raise HTTPException(status_code=500, detail="Failed to create session")

        # Get fuzzy matches from signin manager
        session = integrator.signin.get_session(signin_event.session_id)
        if not session:
            raise HTTPException(status_code=500, detail="Session not found")

        return {
            "person_id": req.person_id,
            "session_id": signin_event.session_id,
            "detected_name": req.detected_name,
            "snapshot": signin_event.entry.snapshot_b64,
            "fuzzy_matches": [
                {
                    "appointment_id": m.appointment.id,
                    "full_name": m.appointment.full_name,
                    "appointment_at": m.appointment.appointment_at,
                    "time": m.appointment.time_str,
                    "medic_id": m.appointment.medic_id,
                    "score": m.score,
                }
                for m in session.fuzzy_matches
            ],
            "match_count": len(session.fuzzy_matches),
        }

    @router.post("/confirm-appointment")
    async def confirm_appointment(req: ConfirmAppointmentRequest) -> dict:
        """
        Confirm appointment selection and phone number.

        Staff enters phone number to verify patient before creating signin.
        """
        success, error = integrator.on_appointment_confirmed(
            req.person_id,
            req.session_id,
            req.appointment_id,
            req.phone,
            req.cnp or None,
        )

        if not success:
            raise HTTPException(status_code=400, detail=error)

        signin_event = integrator.get_pending_entry(req.person_id)
        if not signin_event or not signin_event.session_id:
            raise HTTPException(status_code=500, detail="Session error")

        session = integrator.signin.get_session(signin_event.session_id)
        if not session or not session.selected_appointment:
            raise HTTPException(status_code=500, detail="Appointment not found")

        appt = session.selected_appointment
        return {
            "person_id": req.person_id,
            "session_id": req.session_id,
            "confirmed": True,
            "appointment": {
                "id": appt.id,
                "full_name": appt.full_name,
                "appointment_at": appt.appointment_at,
                "time": appt.time_str,
                "medic_id": appt.medic_id,
            },
            "phone": req.phone,
            "next_step": "create_signin",
        }

    @router.post("/complete")
    async def complete_signin(req: CompleteSigninRequest) -> dict:
        """
        Complete signin - creates presentation and triggers tablet signature.

        Returns presentation_id for tablet signature capture.
        """
        response, error = integrator.on_signin_complete(
            req.person_id,
            req.session_id,
        )

        if error:
            raise HTTPException(status_code=400, detail=error)

        if not response:
            raise HTTPException(status_code=500, detail="Failed to create presentation")

        return {
            "person_id": req.person_id,
            "presentation_id": response.get("presentation_id"),
            "patient_id": response.get("patient_id"),
            "medic_id": response.get("medic_id"),
            "appointment_id": response.get("appointment_id"),
            "full_name": f"{response.get('first_name')} {response.get('last_name')}",
            "status": "waiting_for_signature",
            "next_step": "show_tablet",
        }

    @router.get("/entry/{person_id}")
    async def get_pending_entry(person_id: int) -> dict:
        """Get pending signin entry for a person."""
        signin_event = integrator.get_pending_entry(person_id)
        if not signin_event:
            raise HTTPException(status_code=404, detail="Entry not found")

        return {
            "person_id": person_id,
            "detected_name": signin_event.detected_name,
            "session_id": signin_event.session_id,
            "status": signin_event.status,
            "fuzzy_matches_count": signin_event.fuzzy_matches_count,
            "timestamp": signin_event.entry.timestamp,
            "confidence": signin_event.entry.confidence,
        }

    @router.get("/recent")
    async def get_recent_signin_events(limit: int = Query(10, ge=1, le=50)) -> dict:
        """Get recent signin events."""
        events = integrator.get_recent_events(limit)
        return {
            "recent_events": [
                {
                    "person_id": e.entry.person_id,
                    "detected_name": e.detected_name,
                    "status": e.status,
                    "timestamp": e.entry.timestamp,
                    "confidence": e.entry.confidence,
                }
                for e in events
            ],
            "count": len(events),
        }

    @router.get("/refresh-appointments")
    async def refresh_appointments() -> dict:
        """Force refresh today's appointments."""
        success, error = integrator.signin.refresh_appointments()
        if not success:
            raise HTTPException(status_code=500, detail=error)

        status = integrator.signin.get_status()
        return {
            "success": True,
            "appointments_count": status["appointments_count"],
            "last_sync": status["last_sync"],
        }

    @router.get("/status")
    async def get_status() -> dict:
        """Get signin integrator status."""
        return integrator.get_status()

    @router.post("/clear/{person_id}")
    async def clear_entry(person_id: int) -> dict:
        """Clear completed signin entry."""
        integrator.clear_entry(person_id)
        return {"person_id": person_id, "cleared": True}

    @router.post("/validate-cnp")
    async def validate_cnp(req: dict) -> dict:
        """Validate a CNP and return gender/doctor routing info."""
        cnp = req.get("cnp", "")
        parsed = parse_cnp(cnp)
        if not parsed:
            return {"valid": False, "error": "CNP invalid"}

        medic_id = get_medic_id_from_cnp(cnp)
        # Find doctor name
        doctor_name = ""
        for doc in integrator.signin.doctors:
            if doc.id == medic_id:
                doctor_name = doc.full_name
                break

        return {
            "valid": True,
            "gender": "M" if parsed["gender"] == 1 else "F",
            "birth_date": parsed["birth_date"],
            "medic_id": medic_id,
            "doctor_name": doctor_name,
        }

    @router.get("/appointments")
    async def get_today_appointments() -> dict:
        """Get today's appointments for all doctors."""
        manager = integrator.signin
        appointments = []
        for appt in manager.all_appointments:
            appointments.append({
                "id": appt.id,
                "full_name": appt.full_name,
                "first_name": appt.first_name,
                "last_name": appt.last_name,
                "appointment_at": appt.appointment_at,
                "time": appt.time_str,
                "medic_id": appt.medic_id,
                "patient_id": appt.patient_id,
            })

        doctors = []
        for doc in manager.doctors:
            doctors.append({
                "id": doc.id,
                "full_name": doc.full_name,
                "first_name": doc.first_name,
                "last_name": doc.last_name,
            })

        return {
            "appointments": appointments,
            "doctors": doctors,
            "count": len(appointments),
            "last_sync": manager.last_sync,
        }

    return router
