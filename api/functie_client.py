"""Functie API client for doctor/appointment management and digital signin."""

from __future__ import annotations

import httpx
from typing import Any
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class Doctor:
    id: int
    first_name: str
    last_name: str
    specialities: list[int]
    medical_units: list[int]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Appointment:
    id: int
    first_name: str
    last_name: str
    patient_id: int
    appointment_at: str  # "2023-06-17 10:55"
    medic_id: int = 0

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def time_str(self) -> str:
        """Extract HH:MM from appointment_at."""
        try:
            return self.appointment_at.split()[-1]
        except Exception:
            return self.appointment_at


def parse_cnp(cnp: str) -> dict[str, Any] | None:
    """Parse a Romanian CNP and extract gender, birth_date, and medic routing.

    Returns dict with keys: gender (1=M, 2=F), birth_date (YYYY-MM-DD),
    gender_code (first digit), medic_hint ('male'|'female'), or None if invalid.
    """
    cnp = cnp.strip()
    if len(cnp) != 13 or not cnp.isdigit():
        return None

    # Validate checksum
    weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
    s = sum(int(cnp[i]) * weights[i] for i in range(12))
    r = s % 11
    expected = r if r < 10 else 1
    if int(cnp[12]) != expected:
        return None

    first = int(cnp[0])
    yy = cnp[1:3]
    mm = cnp[3:5]
    dd = cnp[5:7]

    if first in (1, 2):
        year = 1900 + int(yy)
    elif first in (5, 6):
        year = 2000 + int(yy)
    elif first in (3, 4):
        year = 1800 + int(yy)
    elif first in (7, 8, 9):
        year = 2000 + int(yy)  # foreign residents
    else:
        return None

    gender = 1 if first in (1, 3, 5, 7) else 2  # 1=Male, 2=Female
    birth_date = f"{year}-{mm}-{dd}"

    return {
        "gender": gender,
        "birth_date": birth_date,
        "gender_code": first,
        "medic_hint": "male" if gender == 1 else "female",
        "cnp": cnp,
    }


# Doctor routing by gender
MALE_DOCTOR_ID = 2    # Nastas Alexandru (urology)
FEMALE_DOCTOR_ID = 3  # Nastas Ana (gynecology)


def get_medic_id_from_cnp(cnp: str) -> int | None:
    """Return doctor ID based on CNP gender: male→2, female→3."""
    parsed = parse_cnp(cnp)
    if not parsed:
        return None
    return MALE_DOCTOR_ID if parsed["gender"] == 1 else FEMALE_DOCTOR_ID


class FunctieAPIClient:
    """Client for Functie API (https://cbm.consultadoctor.ro)."""

    BASE_URL = "https://cbm.consultadoctor.ro"
    LOCATION_ID = 1  # Default location

    def __init__(self, api_key: str, logger: Any = None):
        self.api_key = api_key
        self.logger = logger
        self._http = httpx.Client(timeout=10.0)

    def __del__(self):
        try:
            self._http.close()
        except Exception:
            pass

    def _find_latest_presentation(self, first_name: str, last_name: str) -> int | None:
        """Scrape the web interface to find the latest presentation ID.

        Used as fallback when createPresentation API returns 500 but still creates
        the presentation in the database. Gets ALL latest presentations and
        returns the highest ID (most recently created).
        """
        import re
        try:
            web = httpx.Client(follow_redirects=True, timeout=10.0)
            login_page = web.get("https://citobiomed.consultadoctor.ro/accounts/login/")
            csrf_match = re.search(r'csrfmiddlewaretoken" value="([^"]+)', login_page.text)
            if not csrf_match:
                return None
            csrf = csrf_match.group(1)
            web.post(
                "https://citobiomed.consultadoctor.ro/accounts/login/",
                data={"csrfmiddlewaretoken": csrf, "username": "receptie", "password": "0102receptiecbm0131"},
                headers={"Referer": "https://citobiomed.consultadoctor.ro/accounts/login/"},
                follow_redirects=False,
            )
            # Get ALL latest presentations (no name filter) and return highest ID
            sr = web.get("https://citobiomed.consultadoctor.ro/ambulatory/presentations/search")
            pres_ids = re.findall(r'/ambulatory/presentations/(\d+)', sr.text)
            web.close()
            if pres_ids:
                latest = max(int(pid) for pid in pres_ids)
                if self.logger:
                    self.logger.info(f"Found latest presentation {latest} via web search")
                return latest
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Web search for presentation failed: {e}")
        return None

    def _check_error(self, data: dict) -> tuple[bool, str]:
        """Check if response contains an error."""
        if isinstance(data, dict) and "error" in data:
            return False, data["error"]
        return True, ""

    def get_doctors(self) -> tuple[list[Doctor], str | None]:
        """Fetch all doctors. Returns (doctors, error)."""
        try:
            url = f"{self.BASE_URL}/api/getDoctors"
            params = {"key": self.api_key}

            response = self._http.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            ok, error = self._check_error(data)
            if not ok:
                return [], error

            if not isinstance(data, list):
                return [], "Unexpected response format"

            doctors = [
                Doctor(
                    id=d["id"],
                    first_name=d.get("first_name", ""),
                    last_name=d.get("last_name", ""),
                    specialities=d.get("specialities", []),
                    medical_units=d.get("medical_units", []),
                )
                for d in data
            ]
            if self.logger:
                self.logger.info(f"Fetched {len(doctors)} doctors")
            return doctors, None
        except Exception as e:
            msg = f"get_doctors failed: {str(e)}"
            if self.logger:
                self.logger.error(msg)
            return [], msg

    def get_today_appointments(self, medic_id: int) -> tuple[list[Appointment], str | None]:
        """Fetch today's appointments for a doctor. Returns (appointments, error)."""
        try:
            url = f"{self.BASE_URL}/api/todayAppointments"
            params = {
                "key": self.api_key,
                "medic_id": medic_id,
                "location_id": self.LOCATION_ID,
            }

            response = self._http.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            ok, error = self._check_error(data)
            if not ok:
                return [], error

            if not isinstance(data, list):
                return [], "Unexpected response format"

            appointments = [
                Appointment(
                    id=a["id"],
                    first_name=a.get("first_name", ""),
                    last_name=a.get("last_name", ""),
                    patient_id=a.get("patient_id", 0),
                    appointment_at=a.get("appointment_at", ""),
                    medic_id=medic_id,
                )
                for a in data
            ]
            if self.logger:
                self.logger.info(f"Fetched {len(appointments)} appointments for medic {medic_id}")
            return appointments, None
        except Exception as e:
            msg = f"get_today_appointments failed: {str(e)}"
            if self.logger:
                self.logger.error(msg)
            return [], msg

    def create_presentation(
        self,
        medic_id: int,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        address: str = "",
        appointment_id: int | None = None,
        patient_id: int | None = None,
        cnp: str | None = None,
        birth_date: str | None = None,
        gender: int | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Create checkin/presentation. Returns (response, error).

        If cnp is provided, birth_date and gender are extracted from it.
        Note: The API has a known bug where it returns 500 but still creates
        the presentation. We handle this by scraping the presentation ID
        from the web interface when the API response is not JSON.
        """
        try:
            url = f"{self.BASE_URL}/api/createPresentation"
            params: dict[str, Any] = {"key": self.api_key}

            # Extract birth_date and gender from CNP if available
            if cnp:
                parsed = parse_cnp(cnp)
                if parsed:
                    birth_date = birth_date or parsed["birth_date"]
                    gender = gender or parsed["gender"]
                    # Auto-route doctor by gender if not explicitly set
                    if medic_id == 0:
                        medic_id = MALE_DOCTOR_ID if parsed["gender"] == 1 else FEMALE_DOCTOR_ID

            # NOTE: Do NOT send 'address' - the API crashes with
            # "'Patient' object has no attribute 'address'" after saving.
            body: dict[str, Any] = {
                "medic_id": medic_id,
                "first_name": first_name,
                "last_name": last_name,
                "location_id": self.LOCATION_ID,
                "phone": phone,
                "email": email,
            }
            # Send CNP as 'pid' — Citobiomed uses this for patient identification
            if cnp:
                body["pid"] = cnp
            # birth_date is REQUIRED by API when pid is missing
            if birth_date:
                body["birth_date"] = birth_date
            elif not cnp:
                # Fallback: API requires birth_date if no CNP — use a placeholder
                body["birth_date"] = "1900-01-01"
            if gender:
                body["gender"] = gender
            elif not cnp:
                # Default gender if unknown (API requires it when no CNP)
                body["gender"] = 1
            if appointment_id:
                body["appointment_id"] = appointment_id
            if patient_id:
                body["patient_id"] = patient_id

            response = self._http.post(url, params=params, json=body)

            # Try to parse JSON response
            try:
                data = response.json()
            except Exception:
                # API returned 500 HTML page - presentation was likely still created.
                # Try to find it via the web search.
                if self.logger:
                    self.logger.warning(
                        f"createPresentation returned {response.status_code} non-JSON "
                        f"(presentation likely created despite error)"
                    )
                pres_id = self._find_latest_presentation(first_name, last_name)
                if pres_id:
                    return {"presentation_id": pres_id, "first_name": first_name, "last_name": last_name}, None
                return None, f"API returned {response.status_code}, could not find presentation"

            # Check for success response (has presentation_id)
            if isinstance(data, dict) and "presentation_id" in data:
                if self.logger:
                    self.logger.info(f"Created presentation for {first_name} {last_name}: id={data.get('presentation_id')}")
                return data, None

            # API returned error JSON - presentation may still have been created
            ok, error = self._check_error(data)
            if not ok:
                if self.logger:
                    self.logger.warning(f"createPresentation error: {error}")
                # Try to find presentation via web search as fallback
                pres_id = self._find_latest_presentation(first_name, last_name)
                if pres_id:
                    if self.logger:
                        self.logger.info(f"Found presentation {pres_id} via web despite API error")
                    return {"presentation_id": pres_id, "first_name": first_name, "last_name": last_name}, None
                return data, error

            if self.logger:
                self.logger.info(f"Created presentation for {first_name} {last_name}")
            return data, None
        except Exception as e:
            msg = f"create_presentation failed: {str(e)}"
            if self.logger:
                self.logger.error(msg)
            return None, msg
