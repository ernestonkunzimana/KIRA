# KIRA Frontend — Command Center UI

Modern, clean, and responsive web interface for the KIRA (Kigali Intelligent Resilience Agent) system. Features enterprise-grade authentication, real-time monitoring, and predictive analytics across three critical infrastructure domains.

## 🎯 Features

### Authentication
- **Complete Login System**: Secure JWT-based authentication with brute-force protection
- **Full Registration**: Comprehensive signup form with email validation and password strength checking
- **Session Management**: Persistent session state and secure token handling
- **Role-Based Access**: Support for multiple user roles and departments

### Dashboard
- **System Health Monitoring**: Real-time status of API, ML engines, database, and cache
- **Live Tower Map**: Interactive Mapbox visualization of infrastructure across Kigali
- **Domain-Specific Analysis**:
  - 📡 Telecom IoT: Device failure prediction
  - ⚡ REG Power Grid: Power system fault detection
  - ⚙️ Backup Generators: Predictive maintenance
- **AI Explainability**: SHAP-based feature importance visualization
- **Audit Trail**: Complete event logging and compliance tracking

### UI/UX
- **Dark Theme**: Modern dark mode optimized for 24/7 monitoring
- **Responsive Design**: Adapts to desktop and mobile screens
- **Smooth Animations**: Subtle transitions and interactive feedback
- **Accessibility**: ARIA labels and keyboard navigation support

## 📋 Architecture

```
frontend/
├── app.py                 # Main Streamlit application
├── auth.py               # Authentication logic and utilities
├── pages_auth.py         # Login and signup page components
├── styles.py             # Centralized CSS and theme system
├── dashboard.py          # Legacy dashboard (deprecated)
├── requirements.txt      # Python dependencies
├── .env.template         # Environment configuration template
├── .streamlit/
│   └── config.toml       # Streamlit configuration
└── assets/
    └── rwanda_logo.png   # Brand logo
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip or conda
- Backend API running on `http://localhost:5000`

### Installation

1. **Clone and navigate to frontend directory**:
   ```bash
   cd kigali_watchman/frontend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate      # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.template .env
   # Edit .env and set KIRA_API_URL to your backend URL
   ```

5. **Run the application**:
   ```bash
   streamlit run app.py
   ```

   The dashboard will open at `http://localhost:8501`

## 🔐 Authentication

### Default Credentials (Development)

```
Client ID: dashboard
Password: kira-dashboard-2024
```

Other pre-configured accounts:
- `sensor_gateway` / `kira-sensor-2024`
- `ops_team` / `kira-ops-2024`

### Creating New Accounts

1. Click "Create New Account" on login page
2. Fill in personal and organization information
3. Choose a strong password (8+ chars, uppercase, lowercase, digit, special char)
4. Accept terms and create account
5. Use your `client_id` and password to login

## 📊 Using the Dashboard

### Login Flow
1. Enter `Client ID` and `Password`
2. Click "Sign In"
3. Dashboard loads with your session

### System Health
- **Green (🟢 OK)**: System component is healthy
- **Red (🔴 FAIL)**: Component is down or degraded
- Check sidebar for full status details

### Running Predictions

#### Telecom IoT Tab
- Select a tower
- Adjust sensor sliders (CPU, Memory, Temperature, etc.)
- Click "Run Analysis" to get failure prediction
- View confidence, anomaly scores, and SHAP explanation

#### Power Grid Tab
- Select tower and weather conditions
- Adjust grid state parameters
- Run analysis for fault prediction

#### Backup Generator Tab
- Select tower and mechanical sensors
- Run analysis for maintenance predictions

### Manual Overrides
- Use sidebar to select tower and action
- Provide reason for audit trail
- Click "Execute Override"
- System logs the override for compliance

### Audit Trail
- Filter by tower or view all events
- Adjust record limit (10-200)
- Query displays timestamp, action, confidence, and operator

## 🎨 Customization

### Theme Colors
Edit `frontend/styles.py` to customize colors:

```python
THEME = {
    "primary": "#22c55e",      # Green
    "secondary": "#3b82f6",    # Blue
    "danger": "#ef4444",       # Red
    # ...
}
```

### Streamlit Settings
Edit `.streamlit/config.toml` for Streamlit behavior:

```toml
[theme]
primaryColor = "#22c55e"
backgroundColor = "#0f1117"
font = "sans serif"
```

## 📡 API Integration

The frontend communicates with the backend via REST API:

- **Login**: `POST /auth/token`
- **Predictions**: `POST /api/v1/predict/{domain}` (iot, grid, generator)
- **Overrides**: `POST /api/v1/override`
- **Health**: `GET /api/v1/health`
- **Audit**: `GET /api/v1/audit`

All sensitive endpoints require Bearer token in header:
```
Authorization: Bearer <token>
```

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KIRA_API_URL` | `http://localhost:5000` | Backend API URL |
| `TOWERS_CSV` | `../data/kigali_infra_data.csv` | Tower data source |
| `STREAMLIT_SERVER_PORT` | `8501` | Server port |
| `DEBUG` | `false` | Enable debug mode |

## 🛠️ Development

### Running Tests
```bash
# Test authentication
pytest frontend/test_auth.py

# Test UI components
pytest frontend/test_pages.py
```

### Code Structure

- **`auth.py`**: User authentication, session management, validation
- **`pages_auth.py`**: Login and signup UI components
- **`styles.py`**: Centralized CSS, colors, and theme
- **`app.py`**: Main Streamlit application with tabs and visualizations

### Adding New Domains

1. Add new tab in `app.py` with domain-specific sliders
2. Create endpoint handler in backend (`/api/v1/predict/new_domain`)
3. Update sidebar tower selection if needed
4. Test with backend predictions

## 📚 Documentation

- **Backend API**: See `backend/main.py` for endpoint definitions
- **Security**: See `backend/security_audit.py` for auth mechanisms
- **Models**: See `backend/core/` for inference logic

## 🚨 Troubleshooting

### Backend Unreachable
```
Error: CRITICAL: KIRA Backend Unreachable
```
- Check `KIRA_API_URL` in `.env`
- Ensure backend is running: `python backend/main.py`
- Check firewall and port 5000

### Invalid Credentials
```
Error: Invalid credentials
```
- Verify `Client ID` spelling (case-sensitive)
- Reset password if account exists
- Check backend for user creation

### Session Timeout
- Sessions expire after 1 hour (dev) or as configured
- Login again to continue using dashboard

### Slow Predictions
- Check backend API performance
- Monitor system health status
- Verify tower data is loaded

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review backend logs: `tail -f logs/kira.log`
3. Contact the KIRA operations team

## 📄 License

KIRA Frontend © 2024 Kigali Infrastructure Authority
