# 🚀 Quick Start - Frontend Running in 3 Steps

## Step 1: Install
```bash
cd frontend
npm install
```
⏱️ Takes ~2-3 minutes (one-time only)

## Step 2: Start
```bash
npm run dev
```
✨ Opens at http://localhost:5173

## Step 3: Open Browser
```
http://localhost:5173
```

---

## 📋 Prerequisites

Make sure BOTH are running:

**Terminal 1 (Backend)**
```bash
python main.py --show-window
```
Runs at http://localhost:8080

**Terminal 2 (Frontend)**
```bash
cd frontend
npm run dev
```
Runs at http://localhost:5173

---

## ✅ What You'll See

### First Load
- 🏥 Dashboard with live camera feed
- 📊 System stats (FPS, entries today, people detected)
- 🎥 MJPEG video stream from camera
- 📊 System information panels

### Trigger Entry
- Press **F4** on detector dashboard (http://localhost:8080)
- OR click **Simulate Entry** button
- Frontend automatically switches to signin workflow

### Signin Workflow (5 Steps)

1. **Listen for Name** 🎤
   - Shows camera snapshot
   - Click "🎤 Start Listening"
   - Say patient name
   - OR click "Type Name Manually"

2. **Select Match** 📋
   - Shows top 5 fuzzy-matched appointments
   - Green = excellent (95%+), Orange = good (85%+)
   - Click to select best match

3. **Confirm Phone** 📱
   - Enter patient phone: "0721234567"
   - Shows appointment details
   - Click ✓ Confirm

4. **Creating Signin** ⏳
   - Loading spinner
   - Progress visualization
   - "Setting up digital signin..."

5. **Show ID** 🎉
   - Large presentation ID displayed
   - Click 📋 Copy button
   - Show patient the ID
   - Patient enters on tablet for signature

---

## 🎯 Test Workflow

```
1. Open http://localhost:5173 in browser

2. You should see:
   ├─ Live camera feed
   ├─ System stats
   └─ "System Status: Ready"

3. Go to http://localhost:8080

4. Click "Simulate Entry" or press F4

5. Switch back to http://localhost:5173

6. Should see "Listening for patient name..."

7. Click "Start Listening" or "Type Name Manually"

8. Enter test name: "Ion Popescu"

9. Should see fuzzy matches (if appointments exist)

10. Select a match

11. Enter phone: "0721234567"

12. Wait for signin to create...

13. See presentation ID displayed

14. Success! ✅
```

---

## 🔧 Common Issues

### "Cannot connect to backend"
**Solution:** Make sure `python main.py --show-window` is running
```bash
# Check if running
curl http://localhost:8080/api/state
```

### "npm: command not found"
**Solution:** Install Node.js from https://nodejs.org
```bash
# Verify installation
node --version
npm --version
```

### "Port 5173 already in use"
**Solution:** Kill process or use different port
```bash
# Windows: kill port 5173
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Or change port in vite.config.ts
```

### "Web Speech API not working"
**Solution:** Use "Type Name Manually" button instead
- Web Speech only works on localhost/HTTPS
- Some browsers don't support it (check browser console)

### "No matches found" when entering name
**Solution:** Add appointments via Functie admin
- System uses appointments for fuzzy matching
- Need at least one appointment for today
- Call `/api/signin/refresh-appointments` to sync

---

## 📱 What Works

✅ Voice recognition (Web Speech API) - Romanian language
✅ Fuzzy name matching (from backend)
✅ Phone verification
✅ Digital presentation ID creation
✅ Live camera feed display
✅ Real-time system stats
✅ Responsive design (desktop/tablet/mobile)
✅ WebSocket real-time updates
✅ Error handling & fallbacks
✅ Loading states & animations

---

## 📚 File Structure

```
frontend/
├── src/
│   ├── App.jsx                 ← Main app
│   ├── main.jsx                ← React entry
│   ├── components/
│   │   ├── DashboardView.jsx   ← Camera + stats
│   │   ├── SigninWorkflow.jsx  ← 5-step workflow
│   │   └── steps/
│   │       ├── ListeningForName.jsx
│   │       ├── SelectingMatch.jsx
│   │       ├── ConfirmingPhone.jsx
│   │       ├── CreatingSignin.jsx
│   │       └── PresentationReady.jsx
│   └── styles/
│       ├── *.css               ← All styling
│
├── package.json                ← Dependencies
├── vite.config.ts              ← Dev server config
├── tsconfig.json               ← TypeScript config
└── index.html                  ← HTML entry

Output: http://localhost:5173
```

---

## 🎬 Live Testing Checklist

- [ ] Backend running on port 8080
- [ ] Frontend running on port 5173
- [ ] Browser opened to http://localhost:5173
- [ ] Camera feed visible in dashboard
- [ ] FPS counter shows > 0
- [ ] System status shows "Ready"
- [ ] Simulated entry triggered
- [ ] Frontend shows listening screen
- [ ] Voice input or manual typing works
- [ ] Fuzzy matches displayed
- [ ] Match selected
- [ ] Phone number entered
- [ ] Loading spinner shown
- [ ] Presentation ID displayed
- [ ] Copy button works
- [ ] Can return to dashboard

---

## 🎨 UI Overview

### Dashboard (Initial Screen)
```
╔════════════════════════════════════════╗
║  🏥 Clinic Entrance Detector          ║
║     Digital Signin System              ║
╠════════════════════════════════════════╣
║                                        ║
║     📹 LIVE VIDEO FEED                 ║
║     [     Camera Stream     ]           ║
║                                        ║
║  👥 Currently: 2  📊 Today: 13         ║
║  ⚡ FPS: 14.5    ✅ Ready              ║
║                                        ║
╚════════════════════════════════════════╝
```

### Listening for Name
```
╔════════════════════════════════════════╗
║          Listening for patient name    ║
║                                        ║
║     [  Camera Snapshot  ]              ║
║                                        ║
║  [ 🎤 Start Listening ]                ║
║  [ Type Name Manually ]                ║
║                                        ║
║  Detected Name: Pic Ovidiu             ║
╚════════════════════════════════════════╝
```

### Select Match
```
╔════════════════════════════════════════╗
║   Select Matching Appointment          ║
║   Detected: Pic Ovidiu                 ║
║                                        ║
║ #1 | Pica Ovidiu @ 10:30              ║
║     | ■■■■■■■■■■ 98% Excellent       ║
║                                        ║
║ #2 | Pica Ovidian @ 14:00             ║
║     | ■■■■■■■■□□ 92% Good            ║
║                                        ║
║ #3 | Pick Ovidian @ 15:30             ║
║     | ■■■■■■□□□□ 75% Possible        ║
╚════════════════════════════════════════╝
```

### Confirm Phone
```
╔════════════════════════════════════════╗
║        Confirm Appointment             ║
║                                        ║
║  Patient: Pica Ovidiu                 ║
║  Time: 10:30                          ║
║  Date: 2026-03-14 10:30               ║
║                                        ║
║  Patient Phone Number:                ║
║  [ 0721234567      ] 10 digits        ║
║                                        ║
║  [ ✓ Confirm ]                        ║
║                                        ║
║  📱 Phone verified for security       ║
╚════════════════════════════════════════╝
```

### Presentation ID
```
╔════════════════════════════════════════╗
║          ✅ Digital Signin Created     ║
║                                        ║
║  Patient: Pica Ovidiu                 ║
║  Time: 10:30                          ║
║                                        ║
║  Show patient this number:            ║
║                                        ║
║        999                            ║
║                                        ║
║  [ 📋 Copy ]                          ║
║                                        ║
║  [ ✓ Done - Return to Dashboard ]    ║
╚════════════════════════════════════════╝
```

---

## 🔐 Security

✅ Phone verification prevents wrong patient match
✅ Fuzzy matching handles transcription errors
✅ Session tracking prevents data loss
✅ All data validated on backend
✅ No patient data stored locally
✅ WebSocket encrypted (wss in production)

---

## 🌍 Deploy

### Production Build
```bash
npm run build
```

Creates optimized bundle in `../frontend_dist/`

### Serve Locally
```bash
npm run preview
```

### Deploy to Server
Copy `frontend_dist/` to your web server

---

## 💬 Still Have Questions?

Read the full docs:
- `FRONTEND_SETUP.md` - Detailed setup guide
- `FRONTEND_COMPLETE.md` - All features documented
- `SYSTEM_RUNNING.md` - System status & testing

---

## 🎉 You're Ready!

```bash
# Terminal 1: Backend
python main.py --show-window

# Terminal 2: Frontend
cd frontend
npm run dev

# Browser: http://localhost:5173
```

**Start testing the complete digital signin system! 🚀**
