# Digital Signin - Getting Started

## 🎯 Your System is Ready!

Everything is integrated. Here's what to do next.

---

## 1️⃣ Install & Start

### Install dependencies
```bash
pip install -r requirements.txt
```

### Start detector
```bash
python main.py --show-window
```

You should see:
```
INFO: Digital signin system initialized
INFO: Loaded 2 doctors
INFO: Synced X appointments
INFO: Dashboard started at http://localhost:8080
```

---

## 2️⃣ Test Entry Detection

### Open dashboard
http://localhost:8080

### Simulate entry
Click: **API** → **Simulate Entry**

Check logs - you should see:
```
INFO: Person detected - waiting for name transcription
```

---

## 3️⃣ Test Fuzzy Matching

### Call signin API with a name
```bash
curl -X POST http://localhost:8080/api/signin/detect-name \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 999,
    "detected_name": "Ion Popescu"
  }' | python -m json.tool
```

You'll get back:
```json
{
  "session_id": "abc123",
  "fuzzy_matches": [
    {
      "appointment_id": 42,
      "full_name": "Ion Popescu",
      "appointment_at": "2026-03-14 10:30",
      "time": "10:30",
      "medic_id": 2,
      "score": 100.0
    }
  ]
}
```

---

## 4️⃣ Test Confirmation

### Confirm appointment with phone
```bash
curl -X POST http://localhost:8080/api/signin/confirm-appointment \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 999,
    "session_id": "abc123",
    "appointment_id": 42,
    "phone": "0721234567"
  }' | python -m json.tool
```

Response:
```json
{
  "confirmed": true,
  "appointment": {
    "id": 42,
    "full_name": "Ion Popescu",
    "appointment_at": "2026-03-14 10:30"
  },
  "phone": "0721234567"
}
```

---

## 5️⃣ Test Complete Signin

### Create digital signin
```bash
curl -X POST http://localhost:8080/api/signin/complete \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": 999,
    "session_id": "abc123"
  }' | python -m json.tool
```

Response:
```json
{
  "presentation_id": 999,
  "patient_id": 123,
  "medic_id": 2,
  "full_name": "Ion Popescu",
  "status": "waiting_for_signature"
}
```

✅ **Now patient goes to tablet with presentation_id**

---

## 🎨 Frontend Implementation

### What your UI needs to do:

#### Step 1: Show when person detected
```javascript
ws.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  if (data.event === 'signin_started') {
    // Show camera snapshot
    showImage(data.snapshot);
    // Show "Listening for name..." message
    showWaitingScreen();
  }
});
```

#### Step 2: When transcriber gets name
```javascript
const name = "Pic Ovidiu"; // From Deepgram

const response = await fetch('/api/signin/detect-name', {
  method: 'POST',
  body: JSON.stringify({
    person_id: detectedPersonId,
    detected_name: name
  })
});

const data = await response.json();
const { fuzzy_matches, session_id } = data;

// Show matches UI
fuzzy_matches.forEach(match => {
  console.log(`${match.full_name} @ ${match.time} (${match.score}%)`);
});
```

#### Step 3: Staff selects match + phone
```javascript
const selectedMatch = fuzzy_matches[0];  // Best match
const phone = "0721234567";  // Staff enters this

const confirmed = await fetch('/api/signin/confirm-appointment', {
  method: 'POST',
  body: JSON.stringify({
    person_id: detectedPersonId,
    session_id: sessionId,
    appointment_id: selectedMatch.appointment_id,
    phone: phone
  })
});

// Show "Creating signin..."
```

#### Step 4: Create signin
```javascript
const result = await fetch('/api/signin/complete', {
  method: 'POST',
  body: JSON.stringify({
    person_id: detectedPersonId,
    session_id: sessionId
  })
});

const { presentation_id } = await result.json();

// Show presentation_id on screen
console.log(`Show patient: ${presentation_id}`);

// Patient goes to tablet for signature
```

---

## 🔊 Deepgram Integration

### Get name from Deepgram transcript
```javascript
const deepgramWs = new WebSocket('wss://api.deepgram.com/v1/listen?...');

deepgramWs.addEventListener('message', async (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'transcript' && data.is_final) {
    const text = data.transcript.text;
    console.log(`Detected: ${text}`);

    // Call signin API
    const response = await fetch('/api/signin/detect-name', {
      method: 'POST',
      body: JSON.stringify({
        person_id: currentPersonId,
        detected_name: text
      })
    });

    // Continue workflow...
  }
});
```

---

## 📋 Complete Workflow Example

```javascript
// 1. Person enters → Detector triggers
// Dashboard receives: {event: "signin_started", person_id: 123, snapshot: "..."}

// 2. Frontend shows camera snapshot + "Listening..."

// 3. Deepgram transcribes: "Pic Ovidiu"
async function onNameDetected(name) {
  // Detect name
  const detect = await fetch('/api/signin/detect-name', {
    method: 'POST',
    body: JSON.stringify({person_id: 123, detected_name: name})
  }).then(r => r.json());

  const {session_id, fuzzy_matches} = detect;

  // Show matches UI
  showMatches(fuzzy_matches);

  // Wait for staff to select + enter phone
  const {appointmentId, phone} = await waitForStaffInput();

  // Confirm
  await fetch('/api/signin/confirm-appointment', {
    method: 'POST',
    body: JSON.stringify({
      person_id: 123,
      session_id,
      appointment_id: appointmentId,
      phone
    })
  }).then(r => r.json());

  // Complete
  const complete = await fetch('/api/signin/complete', {
    method: 'POST',
    body: JSON.stringify({person_id: 123, session_id})
  }).then(r => r.json());

  const {presentation_id} = complete;

  // Show to patient
  showPresentationId(presentation_id);
  // Patient goes to tablet
}
```

---

## 🔧 Troubleshooting

### "Signin manager init failed"
**Problem:** API key not set
**Solution:**
```bash
echo "FUNCTIE_API_KEY=sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH" >> .env
```

### No appointments showing
**Problem:** Appointments not synced
**Solution:**
```bash
curl http://localhost:8080/api/signin/refresh-appointments
```

### Fuzzy matches score too low
**Problem:** Matching is too strict
**Solution:** Edit `api/signin_manager.py`, line ~200:
```python
threshold=40  # Lower from 60 to 40
```

### "ModuleNotFoundError: rapidfuzz"
**Problem:** Dependency not installed
**Solution:**
```bash
pip install rapidfuzz>=3.0.0
```

---

## ✨ Key Points

- **Fuzzy matching is automatic** - No need for perfect transcription
- **Phone verification adds security** - Confirms right patient
- **Workflow is 4 simple steps** - Detect → Match → Confirm → Create
- **Everything works together** - Detector → API → Functie API → Tablet

---

## 📞 API Reference

### Detect Name
```
POST /api/signin/detect-name
Body: {person_id: int, detected_name: str}
Response: {session_id: str, fuzzy_matches: []}
```

### Confirm Appointment
```
POST /api/signin/confirm-appointment
Body: {person_id: int, session_id: str, appointment_id: int, phone: str}
Response: {confirmed: bool, appointment: {}, phone: str}
```

### Complete Signin
```
POST /api/signin/complete
Body: {person_id: int, session_id: str}
Response: {presentation_id: int, patient_id: int, status: str}
```

### Get Status
```
GET /api/signin/status
Response: {pending_entries: int, recent_events: int, ...}
```

### Refresh Appointments
```
GET /api/signin/refresh-appointments
Response: {appointments_count: int, last_sync: str}
```

---

## 🎉 You're Ready!

Your complete digital signin system is live:
- ✅ Person detection → fuzzy name matching
- ✅ Phone verification → security
- ✅ Appointment confirmation → accuracy
- ✅ Digital presentation → tablet signature

Start with **Step 1** above and work through each test! 🚀
