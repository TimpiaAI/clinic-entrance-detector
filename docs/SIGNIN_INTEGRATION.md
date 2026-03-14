# Digital Signin Integration Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ STARTUP                                                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Load doctors (2 total: Nastas Alexandru, Nastas Ana)        │
│ 2. Initialize SigninManager                                    │
│ 3. Ready to accept person detections                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ DAILY REFRESH (on demand or scheduled)                         │
├─────────────────────────────────────────────────────────────────┤
│ Call: GET /api/signin/refresh-appointments                     │
│ Fetches today's appointments for each doctor                   │
│ Response: {appointments_count: N, last_sync: ISO}              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PERSON DETECTED - START SIGNIN FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. TRANSCRIBE NAME (from microphone/video analysis)            │
│    Example: "Pica Ovidiu" or "Pic Ovidiu" (fuzzy match needed) │
│                                                                 │
│ 2. POST /api/signin/start                                       │
│    Request:  {"detected_name": "Pica Ovidiu"}                  │
│    Response: {                                                  │
│      "session_id": "12345",                                     │
│      "detected_name": "Pica Ovidiu",                            │
│      "fuzzy_matches": [                                         │
│        {                                                        │
│          "appointment_id": 42,                                  │
│          "full_name": "Pica Ovidiu",    ← Best match           │
│          "appointment_at": "2026-03-14 10:30",                 │
│          "time": "10:30",                                       │
│          "medic_id": 2,                 ← Nastas Alexandru      │
│          "score": 98.5                  ← Fuzzy match score     │
│        },                                                       │
│        {                                                        │
│          "appointment_id": 43,                                  │
│          "full_name": "Pick Ovidian",   ← Lesser match          │
│          "appointment_at": "2026-03-14 11:00",                 │
│          "time": "11:00",                                       │
│          "medic_id": 3,                 ← Nastas Ana            │
│          "score": 75.2                                          │
│        },                                                       │
│      ]                                                          │
│    }                                                            │
│                                                                 │
│ 3. SHOW MATCHES TO STAFF                                        │
│    Display fuzzy matched appointments with confidence scores    │
│                                                                 │
│ 4. ASK FOR PHONE CONFIRMATION                                   │
│    Staff enters phone number to verify matched patient          │
│                                                                 │
│ 5. POST /api/signin/confirm-appointment/{session_id}           │
│    Request:  {                                                  │
│      "appointment_id": 42,                                      │
│      "phone": "0721234567"                                      │
│    }                                                            │
│    Response: {                                                  │
│      "confirmed_appointment": {                                │
│        "full_name": "Pica Ovidiu",                             │
│        "appointment_at": "2026-03-14 10:30"                    │
│      },                                                         │
│      "phone_confirmed": "0721234567",                          │
│      "ready_for_signin": True                                  │
│    }                                                            │
│                                                                 │
│ 6. CREATE PRESENTATION (digital signin)                        │
│    POST /api/signin/complete/{session_id}                      │
│    Response: {                                                  │
│      "presentation_id": 999,    ← Show to patient              │
│      "patient_id": 123,                                         │
│      "medic_id": 2,                                             │
│      "full_name": "Pica Ovidiu",                               │
│      "status": "waiting_for_signature"                         │
│    }                                                            │
│                                                                 │
│ 7. TABLET SIGNATURE CAPTURE                                     │
│    Tablet websocket connects for digital signature              │
│    (Functie API handles this part)                             │
│                                                                 │
│ 8. CLEAR SESSION                                                │
│    GET /api/signin/clear-session/{session_id}                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Fuzzy Matching Details

**Algorithm:** Token Set Ratio (from `rapidfuzz`)
- Handles word order differences
- Handles typos and character mismatches
- Returns score 0-100

**Examples:**
```
"Pica Ovidiu" vs "Pica Ovidiu"  → 100 (exact match)
"Pica Ovidiu" vs "Pic Ovidiu"   → 98+ (1 char typo)
"Pica Ovidiu" vs "Ovidiu Pica"  → 100 (word order swap)
"Pica Ovidiu" vs "Pika Ovidiu"  → 95+ (letter similarity)
"Pica Ovidiu" vs "Pick Ovidian" → 75+ (similar but different)
```

**Threshold:** 60 (configurable)
- Matches scoring 60+ are shown to staff
- Top 5 matches returned

## Environment Variables

Add to `.env`:
```
FUNCTIE_API_URL=https://cbm.consultadoctor.ro
FUNCTIE_API_KEY=sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH
```

## Integration Checklist

- [ ] Install `rapidfuzz>=3.0.0` (add to requirements.txt)
- [ ] Create FunctieAPIClient instance
- [ ] Create SigninManager instance on startup
- [ ] Initialize doctors (call `signin_manager.initialize()`)
- [ ] Refresh appointments daily (call `signin_manager.refresh_appointments()`)
- [ ] Expose SigninManager to FastAPI dashboard
- [ ] Include signin routes in FastAPI app
- [ ] Update frontend to call signin API endpoints
- [ ] Test with sample appointments

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/signin/start` | Start signin session with detected name |
| POST | `/api/signin/confirm-appointment/{session_id}` | Confirm appointment + phone |
| POST | `/api/signin/complete/{session_id}` | Create presentation (trigger signin) |
| GET | `/api/signin/refresh-appointments` | Sync today's appointments |
| GET | `/api/signin/status` | Get manager status |
| GET | `/api/signin/clear-session/{session_id}` | Clean up session |

## Error Handling

All endpoints follow this pattern:
- **Success:** HTTP 200 with response data
- **Error:** HTTP 400 with `{"detail": "error message"}`

Functie API errors (CNP validation, etc.) return:
```json
{"error": "CNP-ul este incorect!"}
```

## Next Steps

1. **Update `main.py`** to initialize SigninManager
2. **Update `dashboard/web.py`** to include signin routes
3. **Update frontend** to call signin API endpoints
4. **Add daily appointment refresh** (cron or on-demand)
5. **Test fuzzy matching** with real appointment names
