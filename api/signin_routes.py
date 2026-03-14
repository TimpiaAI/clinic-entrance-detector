"""REST API routes for digital signin workflow."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .signin_manager import SigninManager


router = APIRouter(prefix="/api/signin", tags=["signin"])


class StartSigninRequest(BaseModel):
    detected_name: str


class FuzzyMatchResponse(BaseModel):
    appointment_id: int
    full_name: str
    appointment_at: str
    score: float


class ConfirmAppointmentRequest(BaseModel):
    appointment_id: int
    phone: str


class CompleteSigninRequest(BaseModel):
    email: str = "noemail@clinic.local"
    address: str = "Clinic"


def create_signin_routes(signin_manager: SigninManager) -> APIRouter:
    """Create signin API routes."""

    @router.post("/start")
    async def start_signin(req: StartSigninRequest) -> dict:
        """
        Start signin session with detected person name.

        Returns fuzzy-matched appointments from today's schedule.
        """
        session, matches = signin_manager.start_signin_session(req.detected_name)

        return {
            "session_id": id(session),  # Use object id as session ID
            "detected_name": req.detected_name,
            "detected_at": session.detected_at,
            "fuzzy_matches": [
                {
                    "appointment_id": m.appointment.id,
                    "full_name": m.appointment.full_name,
                    "appointment_at": m.appointment.appointment_at,
                    "time": m.appointment.time_str,
                    "medic_id": m.appointment.medic_id,
                    "score": m.score,
                }
                for m in matches
            ],
            "appointments_count": len(signin_manager.all_appointments),
        }

    @router.post("/confirm-appointment/{session_id}")
    async def confirm_appointment(
        session_id: str,
        req: ConfirmAppointmentRequest,
    ) -> dict:
        """
        Confirm appointment selection and provide phone number.

        Phone number is used for verification before creating signin.
        """
        success, error = signin_manager.confirm_appointment(
            session_id,
            req.appointment_id,
            req.phone,
        )
        if not success:
            raise HTTPException(status_code=400, detail=error)

        session = signin_manager.get_session(session_id)
        if not session or not session.selected_appointment:
            raise HTTPException(status_code=400, detail="Session error")

        appt = session.selected_appointment
        return {
            "session_id": session_id,
            "confirmed_appointment": {
                "id": appt.id,
                "full_name": appt.full_name,
                "appointment_at": appt.appointment_at,
                "time": appt.time_str,
            },
            "phone_confirmed": req.phone,
            "ready_for_signin": True,
        }

    @router.post("/complete/{session_id}")
    async def complete_signin(
        session_id: str,
        req: CompleteSigninRequest | None = None,
    ) -> dict:
        """
        Complete signin - creates presentation and triggers tablet signature capture.

        Returns presentation_id for signature capture.
        """
        if req is None:
            req = CompleteSigninRequest()

        response, error = signin_manager.complete_signin(
            session_id,
            email=req.email,
            address=req.address,
        )
        if error:
            raise HTTPException(status_code=400, detail=error)

        session = signin_manager.get_session(session_id)
        return {
            "presentation_id": response.get("presentation_id"),
            "patient_id": response.get("patient_id"),
            "medic_id": response.get("medic_id"),
            "appointment_id": response.get("appointment_id"),
            "full_name": f"{response.get('first_name')} {response.get('last_name')}",
            "status": "waiting_for_signature",
        }

    @router.get("/refresh-appointments")
    async def refresh_appointments() -> dict:
        """Force refresh of today's appointments from all doctors."""
        success, error = signin_manager.refresh_appointments()
        if not success:
            raise HTTPException(status_code=500, detail=error)

        status = signin_manager.get_status()
        return {
            "success": True,
            "appointments_count": status["appointments_count"],
            "last_sync": status["last_sync"],
        }

    @router.get("/status")
    async def get_signin_status() -> dict:
        """Get signin manager status."""
        return signin_manager.get_status()

    @router.get("/clear-session/{session_id}")
    async def clear_session(session_id: str) -> dict:
        """Clear a completed signin session."""
        signin_manager.clear_session(session_id)
        return {"session_id": session_id, "cleared": True}

    return router
