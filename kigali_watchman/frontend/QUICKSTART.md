# KIRA Frontend — Quick Reference Guide

## 🚀 Getting Started (5 minutes)

### Step 1: Install

```bash
cd kigali_watchman/frontend
python -m venv venv
source venv/bin/activate  # Mac/Linux
# or
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Step 2: Configure

```bash
cp .env.template .env
# Edit .env and set KIRA_API_URL=http://localhost:5000
```

### Step 3: Run

```bash
# Option A: Using startup script
./start.sh           # Mac/Linux
start.bat            # Windows

# Option B: Direct Streamlit
streamlit run app.py
```

Dashboard opens at [http://localhost:8501](http://localhost:8501)

---

## 🔐 Authentication

### Login

- **Page**: Login tab (default on first load)
- **Fields**: Client ID, Password
- **Default Creds**:
  - `dashboard` / `kira-dashboard-2024`
  - `sensor_gateway` / `kira-sensor-2024`
  - `ops_team` / `kira-ops-2024`

### Register

- **Click**: "Create New Account" link on login page
- **Form Fields**:
  - Personal: First name, Last name, Email
  - Organization: Organization name, Department, Role
  - Account: Client ID, Phone (optional)
  - Credentials: Password, Confirm password
  - Preferences: Receive alerts, Receive reports
  - Terms: Accept T&C

### Password Requirements

- ✅ Minimum 8 characters
- ✅ At least 1 uppercase letter
- ✅ At least 1 lowercase letter
- ✅ At least 1 digit
- ✅ At least 1 special character (!@#$%^&*-_=+[]{};:,.<>?)

---

## 📊 Dashboard Overview

```text
┌─────────────────────────────────────────────────┐
│  🔋 KIRA  |  System-of-Systems Command Center   │
└─────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  System Health (4 cards)                         │
│  🟢 API | 🟢 ML Engines | 🟢 Redis | 🟢 Database │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  🗺️  Live Tower Map (Interactive Mapbox)         │
│  • Solar towers (green markers)                  │
│  • Generator towers (yellow markers)             │
│  • Click for details                             │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  Domain Analysis Tabs                            │
│  ┌────────┬─────────┬──────────────────────┐   │
│  │📡 IoT  │⚡ Grid  │⚙️  Generators        │   │
│  └────────┴─────────┴──────────────────────┘   │
│                                                  │
│  Each tab:                                       │
│  • Sensor input sliders (left)                   │
│  • Analysis results (right)                      │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  📋 Audit Trail                                  │
│  Filter by tower, query events, view logs       │
└──────────────────────────────────────────────────┘
``` 

---

## 🛠️ Sidebar Controls

### Session Info

- Shows logged-in Client ID
- Session status (✅ Active)
- User role

### Active Assets

- **View**: Click "View Towers" to expand
- **Info**: Tower ID, District, Backup type

### Manual Override

1. **Select Tower**: Dropdown of all towers
2. **Select Action**:
   - 0 = No Action
   - 1 = Switch Solar
   - 2 = Start Generator
   - 3 = Dispatch Technician
3. **Reason**: Enter reason (required for audit trail)
4. **Execute**: Click button to send override
5. **Confirm**: Toast message appears on success

---

## 📡 IoT Tab (Telecom Tower Failure)

### Input Parameters (Left Side)

| Slider | Range | Default | Unit |
|--------|-------|---------|------|
| CPU Usage | 0-100 | 50 | % |
| Memory Usage | 0-100 | 60 | % |
| Battery Level | 0-100 | 75 | % |
| Latency | 0-500 | 100 | ms |
| Packet Loss | 0-10 | 2 | % |
| Temperature | 10-80 | 40 | °C |
| Uptime | 0-500 | 100 | hrs |
| Workload | 1-5 | 2 | - |
| Error Count | 0-50 | 5 | - |

### Output (Right Side)

- **Decision**: ✅ Autonomous / ⚠️ Human Alert / 🔒 Blocked
- **Confidence**: Prediction confidence percentage
- **LSTM Urgency**: Class level (0-4)
- **Anomaly Score**: 0.0-1.0 range
- **Anomaly Flag**: ✅ No / 🚨 Yes
- **Feature Importance**: SHAP bar chart showing top drivers

---

## ⚡ Grid Tab (Power System Faults)

### Input Parameters (Left Side)

| Control | Options | Default |
|---------|---------|---------|
| Tower | Dropdown of all | Gasabo-A |
| Weather | Clear, Rainy, Storm, Wind, Snow | Clear |
| Maintenance | Completed, Scheduled, Pending | Completed |
| Health | Normal, Faulty, Overheated | Normal |
| Voltage | 1500-3000 V | 2200 |
| Current | 100-350 A | 215 |
| Load | 20-80 MW | 50 |
| Temperature | 15-50 °C | 28 |
| Wind Speed | 0-60 km/h | 18 |
| Fault Duration | 0-10 hrs | 1 |
| Downtime | 0-10 hrs | 1 |

### Output (Right Side)

- Same as IoT tab

---

## ⚙️ Generator Tab (Predictive Maintenance)

### Input Parameters (Left Side)

| Slider | Range | Default | Unit |
|--------|-------|---------|------|
| Vibration | 0-5.0 | 1.0 | g |
| Acoustic | 0-3.0 | 0.8 | kHz |
| Temperature | 30-120 | 70 | °C |
| Current | 5-30 | 15 | A |
| IMF_1 | -1.0 to 1.0 | 0 | - |
| IMF_2 | -0.5 to 0.5 | 0 | - |
| IMF_3 | -0.2 to 0.2 | 0 | - |

### Output (Right Side)

- Same as IoT/Grid tabs

---

## 📋 Audit Trail

### Query Interface

- **Filter by Tower**: "All" or specific tower ID
- **Record Limit**: 10-200 events
- **Query Button**: Fetch and display logs

### Results

- **Event Count**: Total matching events
- **Avg Confidence**: Average prediction confidence
- **Table Columns**:
  - Timestamp: When event occurred
  - Tower ID: Which tower
  - Action Name: What action was triggered
  - Confidence: Prediction confidence

---

## 🎨 Visual Design

### Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Primary (Success) | Green | #22c55e |
| Secondary (Info) | Blue | #3b82f6 |
| Danger (Error) | Red | #ef4444 |
| Warning | Yellow | #eab308 |
| Background | Dark | #0f1117 |
| Cards | Dark Gray | #1a1f35 |
| Border | Gray | #334155 |
| Text | Light | #e2e8f0 |
| Text (Muted) | Gray | #94a3b8 |

### Status Indicators

- **🟢 OK**: System healthy
- **🔴 FAIL**: System down
- **✅ YES**: Condition met
- **❌ NO**: Condition not met
- **⚠️**: Warning/caution
- **🔒**: Blocked/restricted

---

## 🔧 Troubleshooting

### "Backend Unreachable"

**Problem**: Dashboard shows "KIRA Backend Unreachable"

**Solution**:

1. Check backend is running: `ps aux | grep main.py`
2. Verify URL: Check `KIRA_API_URL` in `.env`
3. Start backend: `cd ../backend && python main.py`

### "Invalid Credentials"

**Problem**: Login fails with "Invalid credentials"

**Solution**:

1. Verify Client ID (case-sensitive)
2. Check password is correct
3. For new accounts, use registration page first

### "Session Timeout"

**Problem**: Dashboard stops responding

**Solution**:

1. Refresh page (browser F5)
2. Logout and login again
3. Check backend is still running

### "Sliders not updating"

**Problem**: Sensor sliders seem frozen

**Solution**:

1. Refresh page
2. Check browser console for errors
3. Restart Streamlit: `Ctrl+C` and `streamlit run app.py`

---

## 📁 File Structure

```text
frontend/
├── app.py                    # Main Streamlit app
├── auth.py                   # Authentication logic
├── pages_auth.py             # Login/signup UI
├── styles.py                 # CSS and theme
├── requirements.txt          # Dependencies
├── .env.template             # Config template
├── .streamlit/config.toml    # Streamlit settings
├── start.sh                  # Linux/Mac startup
├── start.bat                 # Windows startup
├── README.md                 # Full documentation
├── QUICKSTART.md             # This file
└── assets/
    └── rwanda_logo.png       # Brand logo
```text

---

## 📞 Common Tasks

### Change API URL
Edit `.env`:
```text
KIRA_API_URL=http://your-server:5000
```

### Add New Analysis Domain
1. Add new tab in `app.py`
2. Create sliders for domain parameters
3. Call `send_and_render()` with new endpoint
4. Backend must have `/api/v1/predict/new_domain`

### Customize Colors
Edit `frontend/styles.py`:
```python
THEME = {
    "primary": "#YOUR_COLOR",
    # ... other colors
}
```

### Change Page Layout
Edit Streamlit config in `.streamlit/config.toml`:
```toml
[client]
toolbarMode = "minimal"     # or "viewer"
showErrorDetails = false
```

---

## 🔐 Security Notes

- ✅ All API calls use JWT Bearer tokens
- ✅ Passwords never logged or displayed
- ✅ HTTPS recommended for production
- ✅ Rate limiting on `/auth/token` (10 per minute)
- ✅ Brute-force detection (5 fails in 5 min = block)
- ✅ Complete audit trail of actions
- ✅ Sessions expire after 1 hour (configurable)

---

## 📈 Performance Tips

- **Large datasets**: Limit audit records to 50
- **Multiple domains**: Switch tabs instead of reloading
- **Slow sliders**: Check backend CPU/memory
- **API timeouts**: Increase timeout in `auth.py` if needed

---

## 📚 Additional Resources

- **Backend API**: See `backend/main.py`
- **Auth Details**: See `backend/api/auth.py`
- **Security**: See `backend/security_audit.py`
- **Models**: See `backend/core/inference.py`

