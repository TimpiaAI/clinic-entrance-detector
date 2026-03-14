# Digital Signin System - Complete Overview

## What Was Created

### 1. **FunctieAPIClient** (`api/functie_client.py`)
Connects to Functie API (ConsultaDoctor platform) to:
- Fetch doctor list (2 doctors: Nastas Alexandru, Nastas Ana)
- Fetch today's appointments for each doctor
- Create digital signin (presentation)

**Key Methods:**
```python
client.get_doctors() → List[Doctor]
client.get_today_appointments(medic_id) → List[Appointment]
client.create_presentation(...) → presentation_id
```

---

### 2. **SigninManager** (`api/signin_manager.py`)
Orchestrates the signin workflow with **fuzzy name matching**:

**Key Features:**
- ✅ Fuzzy match detected names to appointment list (handles typos)
- ✅ Multi-step signin: start → confirm appointment → phone verification → complete
- ✅ Thread-safe session management
- ✅ Appointment refresh (daily sync)

**Key Methods:**
```python
manager.initialize() → Load doctors on startup
manager.refresh_appointments() → Sync today's appointments
manager.start_signin_session(detected_name) → FuzzyMatch list
manager.confirm_appointment(session_id, appointment_id, phone) → Verify
manager.complete_signin(session_id) → Create presentation
```

---

### 3. **Signin API Routes** (`api/signin_routes.py`)
REST endpoints for frontend/staff UI:

```
POST   /api/signin/start                          → Start workflow
POST   /api/signin/confirm-appointment/{sid}      → Confirm + phone
POST   /api/signin/complete/{sid}                 → Create signin
GET    /api/signin/refresh-appointments           → Sync daily
GET    /api/signin/status                         → Manager status
GET    /api/signin/clear-session/{sid}            → Cleanup
```

---

## How It Works - Step by Step

### **Scenario:** Person named "Pica Ovidiu" arrives at clinic

#### **Step 1: Detect & Transcribe (You provide)**
- Camera detects person
- Microphone transcribes: "Pica Ovidiu" (or "Pic Ovidiu" - typo okay!)

#### **Step 2: Start Signin Session**
```bash
POST /api/signin/start
{
  "detected_name": "Pic Ovidiu"
}
```

**Response:** Top 5 fuzzy matched appointments
```json
{
  "session_id": "abc123",
  "fuzzy_matches": [
    {
      "appointment_id": 42,
      "full_name": "Pica Ovidiu",      ← Matched!
      "appointment_at": "2026-03-14 10:30",
      "medic_id": 2,                   ← Dr. Nastas Alexandru
      "score": 98.5                    ← Confidence
    }
  ]
}
```

#### **Step 3: Staff Confirms & Enters Phone**
- Staff sees fuzzy matched appointment
- Asks patient for phone to verify
- Staff enters phone: "0721234567"

```bash
POST /api/signin/confirm-appointment/abc123
{
  "appointment_id": 42,
  "phone": "0721234567"
}
```

#### **Step 4: Create Digital Signin**
```bash
POST /api/signin/complete/abc123
{}
```

**Response:** Patient goes to tablet for signature
```json
{
  "presentation_id": 999,
  "full_name": "Pica Ovidiu",
  "medic_id": 2,
  "status": "waiting_for_signature"
}
```

---

## Fuzzy Matching Examples

| Detected | Appointment | Match | Score |
|----------|-------------|-------|-------|
| "Pica Ovidiu" | "Pica Ovidiu" | ✅ | 100 |
| "Pic Ovidiu" | "Pica Ovidiu" | ✅ | 98 |
| "Pika Ovidiu" | "Pica Ovidiu" | ✅ | 95 |
| "Ovidiu Pica" | "Pica Ovidiu" | ✅ | 100 (word swap) |
| "Pick Ovidian" | "Pica Ovidiu" | ⚠️ | 75 (different) |
| "John Smith" | "Pica Ovidiu" | ❌ | <60 (filtered) |

**Threshold:** 60 (configurable)
**Top results:** 5 appointments per search

---

## Files Created

```
api/
├── functie_client.py      ← Functie API wrapper
├── signin_manager.py      ← Fuzzy match + workflow
└── signin_routes.py       ← REST endpoints

docs/
└── SIGNIN_INTEGRATION.md  ← Detailed integration guide

requirements.txt (updated)
└── Added: rapidfuzz>=3.0.0
```

---

## How to Integrate

### **1. Update `main.py`**
```python
from api.functie_client import FunctieAPIClient
from api.signin_manager import SigninManager

# In main startup:
functie_client = FunctieAPIClient(
    api_key="sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH",
    logger=logger
)
signin_manager = SigninManager(functie_client, logger=logger)

# Initialize on startup
success, error = signin_manager.initialize()
if not success:
    logger.error(f"Failed to initialize signin: {error}")
```

### **2. Update `dashboard/web.py`**
```python
from api.signin_routes import create_signin_routes

def create_dashboard_app(state, zone_manager, ..., signin_manager=None):
    app = FastAPI(...)

    # Add signin routes
    if signin_manager:
        signin_router = create_signin_routes(signin_manager)
        app.include_router(signin_router)

    return app
```

### **3. Call refresh daily**
```python
# On demand or scheduled (e.g., 8:00 AM)
success, error = signin_manager.refresh_appointments()
```

### **4. Frontend integration**
When person detected:
```javascript
// 1. Start signin
const { session_id, fuzzy_matches } = await fetch('/api/signin/start', {
  method: 'POST',
  body: JSON.stringify({ detected_name: "Pica Ovidiu" })
}).then(r => r.json());

// 2. Show matches to staff, get appointment_id and phone

// 3. Confirm appointment
await fetch(`/api/signin/confirm-appointment/${session_id}`, {
  method: 'POST',
  body: JSON.stringify({
    appointment_id: 42,
    phone: "0721234567"
  })
});

// 4. Complete signin
const { presentation_id } = await fetch(`/api/signin/complete/${session_id}`, {
  method: 'POST'
}).then(r => r.json());

// 5. Show presentation_id, redirect to tablet signature capture
```

---

## Key Design Decisions

✅ **Fuzzy matching handles transcription errors** - No need for perfect speech recognition

✅ **Phone confirmation adds verification step** - Ensures correct patient before signin

✅ **Session-based workflow** - Stateful but cleanup after completion

✅ **Thread-safe** - Safe to use from detector loop + API simultaneously

✅ **Extensible** - Easy to add additional verification steps (ID scan, etc.)

---

## Environment Variables

Add to `.env`:
```
FUNCTIE_API_URL=https://cbm.consultadoctor.ro
FUNCTIE_API_KEY=sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH
```

---

## Error Scenarios

| Scenario | Handling |
|----------|----------|
| No appointments today | Empty list, still allow manual entry |
| Fuzzy match score < 60 | Not shown, staff can still search manually |
| Phone mismatch | Use anyway (staff verification) |
| Functie API down | Error message, manual fallback |
| Invalid CNP | Functie API handles, creates without PID |

---

## Testing

### Install dependencies first:
```bash
pip install -r requirements.txt
```

### Quick test:
```python
from api.functie_client import FunctieAPIClient
from api.signin_manager import SigninManager

client = FunctieAPIClient("sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH")
manager = SigninManager(client)

# Load doctors
success, error = manager.initialize()
print(f"Doctors: {len(manager.doctors)}")

# Sync today's appointments
success, error = manager.refresh_appointments()
print(f"Appointments: {len(manager.all_appointments)}")

# Test fuzzy match
session, matches = manager.start_signin_session("Pica Ovidiu")
for m in matches:
    print(f"{m.appointment.full_name}: {m.score}%")
```

---

## Next Phase Features

- [ ] Add fingerprint verification
- [ ] Add ID card scanning
- [ ] Add appointment rescheduling
- [ ] Add no-show tracking
- [ ] Add staff audit log
- [ ] Add multi-language support
- [ ] Add SMS confirmation (6-digit code)
- [ ] Add QR code check-in
