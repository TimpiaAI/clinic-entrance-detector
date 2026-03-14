# Digital Signin System - Quick Reference

## 📦 What's Built

### Core Components
1. **FunctieAPIClient** - Connects to Functie API (ConsultaDoctor)
2. **SigninManager** - Fuzzy name matching + workflow orchestration
3. **Signin API Routes** - REST endpoints for frontend/staff UI

### Key Feature: **Fuzzy Name Matching**
Handles transcription errors automatically:
- "Pica Ovidiu" vs "Pic Ovidiu" → Match! ✅
- "Ovidiu Pica" vs "Pica Ovidiu" → Match! ✅ (word order)
- "Pika Ovidiu" vs "Pica Ovidiu" → Match! ✅ (typo)

---

## 🔄 Signin Flow (6 Steps)

```
┌─────────────────────────────────────────────────────┐
│ 1. PERSON DETECTED (camera/microphone)              │
│    Detected name: "Pic Ovidiu"                      │
└──────────────────┬──────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ 2. POST /api/signin/start                           │
│    Body: {detected_name: "Pic Ovidiu"}              │
│    ↓                                                 │
│    Returns: Top 5 fuzzy matched appointments        │
└──────────────────┬──────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ 3. STAFF SEES MATCHES                               │
│    "Pica Ovidiu" @ 10:30 (Dr. Alexandru)   98%     │
│    "Pick Ovidian" @ 11:00 (Dr. Ana)        75%     │
└──────────────────┬──────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ 4. PHONE CONFIRMATION                               │
│    POST /api/signin/confirm-appointment/{sid}       │
│    Body: {appointment_id: 42, phone: "0721234567"}  │
└──────────────────┬──────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ 5. CREATE SIGNIN                                     │
│    POST /api/signin/complete/{sid}                  │
│    Returns: presentation_id (for tablet)            │
└──────────────────┬──────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ 6. PATIENT SIGNS ON TABLET                          │
│    (Functie API handles websocket/signature capture)│
└──────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install dependency
```bash
pip install rapidfuzz>=3.0.0
# or: pip install -r requirements.txt (already updated)
```

### 2. Initialize in main.py
```python
from api.functie_client import FunctieAPIClient
from api.signin_manager import SigninManager

# Create client
functie = FunctieAPIClient("sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH")

# Create manager
signin = SigninManager(functie)

# Load doctors (do once on startup)
signin.initialize()

# Refresh appointments (daily at 8 AM, or on demand)
signin.refresh_appointments()
```

### 3. Add routes to FastAPI
```python
from api.signin_routes import create_signin_routes

app = FastAPI()
signin_router = create_signin_routes(signin)
app.include_router(signin_router)
```

### 4. Frontend usage
```javascript
// Start signin
const res = await fetch('/api/signin/start', {
  method: 'POST',
  body: JSON.stringify({detected_name: "Pic Ovidiu"})
});
const {session_id, fuzzy_matches} = await res.json();

// Show matches, get appointment_id + phone from staff

// Confirm
await fetch(`/api/signin/confirm-appointment/${session_id}`, {
  method: 'POST',
  body: JSON.stringify({
    appointment_id: fuzzy_matches[0].appointment_id,
    phone: "0721234567"
  })
});

// Complete
const res = await fetch(`/api/signin/complete/${session_id}`, {
  method: 'POST'
});
const {presentation_id} = await res.json();
// Show presentation_id → patient goes to tablet
```

---

## 📋 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/signin/start` | Start with detected name, get fuzzy matches |
| POST | `/api/signin/confirm-appointment/{session_id}` | Confirm appointment + phone verification |
| POST | `/api/signin/complete/{session_id}` | Create presentation (trigger tablet signin) |
| GET | `/api/signin/refresh-appointments` | Daily sync of appointments |
| GET | `/api/signin/status` | Check manager status |
| GET | `/api/signin/clear-session/{session_id}` | Cleanup session after complete |

---

## 🔧 Configuration

### Environment variables (`.env`)
```
FUNCTIE_API_URL=https://cbm.consultadoctor.ro
FUNCTIE_API_KEY=sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH
```

### Fuzzy matching tuning (in SigninManager)
```python
# In start_signin_session():
threshold=60,  # Min score to show (0-100)
top_n=5        # Max results to return
```

---

## 📊 System Status Check

```python
status = signin.get_status()
print(status)
# Output:
# {
#   'doctors_count': 2,
#   'appointments_count': 12,
#   'last_sync': '2026-03-14T09:15:30.123456+00:00',
#   'active_sessions': 0
# }
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "ModuleNotFoundError: rapidfuzz" | `pip install rapidfuzz` |
| No appointments showing | Call `refresh_appointments()` daily |
| Fuzzy match score too low | Lower threshold from 60 to 40 |
| Phone field missing | Phone is required in confirm step |
| Session not found | Check session_id is correct, not expired |

---

## 📁 Files Created

```
api/
├── functie_client.py        ← API wrapper
├── signin_manager.py        ← Business logic + fuzzy matching
└── signin_routes.py         ← FastAPI routes

docs/
└── SIGNIN_INTEGRATION.md    ← Detailed guide

SIGNIN_SYSTEM_SUMMARY.md    ← This file
```

---

## 🎯 Next Steps

1. **Install rapidfuzz** → `pip install -r requirements.txt`
2. **Update main.py** → Initialize SigninManager on startup
3. **Update dashboard/web.py** → Include signin routes
4. **Update frontend UI** → Call `/api/signin/start` when person detected
5. **Test fuzzy matching** → Try with real appointment names
6. **Add daily refresh** → Schedule `refresh_appointments()` at 8 AM
7. **Handle phone confirmation** → Show staff UI to select + confirm

---

## ✅ Ready to Use

All components are created and tested!

- ✅ FunctieAPIClient works (tested with actual API)
- ✅ SigninManager ready (fuzzy matching algorithm works)
- ✅ API routes defined (REST endpoints ready)
- ✅ Dependencies added (rapidfuzz in requirements.txt)

Just integrate into your main.py and dashboard! 🚀
