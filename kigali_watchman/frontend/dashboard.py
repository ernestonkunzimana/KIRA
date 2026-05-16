"""
KIRA Command Center — System of Systems Dashboard
Real-time monitoring of 3 critical infrastructure domains:
  📡 Telecom IoT  |  ⚡ REG Power Grid  |  ⚙️ Backup Generators

Tower map reads from data/kigali_infra_data.csv (single source of truth).
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import requests
import datetime
import plotly.express as px
import plotly.graph_objects as go

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KIRA | Kigali Intelligent Resilience Agent",
    page_icon="🔋",
    layout="wide",
)

# Brand identity
LOGO_PATH = "assets/rwanda_logo.png"
col1, col2 = st.columns([1, 10])
with col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=80)
    else:
        st.markdown("### 🇷🇼")
with col2:
    st.title("KIRA: System-of-Systems Command Center")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #0f1117; }
    h1, h2, h3 { color: #e2e8f0; }
    .metric-card {
        background: linear-gradient(135deg, #1a1f35 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .status-green  { color: #22c55e; font-weight: bold; }
    .status-yellow { color: #eab308; font-weight: bold; }
    .status-red    { color: #ef4444; font-weight: bold; }
    .anomaly-badge {
        background: #7f1d1d;
        color: #fca5a5;
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.8rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ── Config ───────────────────────────────────────────────────────────────────
API_URL = os.environ.get('KIRA_API_URL', 'http://127.0.0.1:5001')
TOWERS_CSV = os.environ.get('TOWERS_CSV', os.path.join(os.path.dirname(__file__), '..', 'data', 'kigali_infra_data.csv'))

# ── Auth & Session ───────────────────────────────────────────────────────────
if 'token' not in st.session_state:
    st.session_state.token = None
if 'client_id' not in st.session_state:
    st.session_state.client_id = None

def login(client_id, password):
    try:
        r = requests.post(f'{API_URL}/auth/token',
                          json={'client_id': client_id, 'client_secret': password},
                          timeout=5)
        if r.status_code == 200:
            st.session_state.token = r.json().get('access_token')
            st.session_state.client_id = client_id
            st.toast(f'Welcome, {client_id}!', icon='🔑')
            return True
    except Exception as e:
        st.error(f'Auth error: {e}')
    return False

def logout():
    st.session_state.token = None
    st.session_state.client_id = None
    st.rerun()

# ── Login Overlay ─────────────────────────────────────────────────────────────
if not st.session_state.token:
    st.markdown("<h2 style='text-align: center;'>🔐 KIRA Secure Access</h2>", unsafe_allow_html=True)
    with st.container():
        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            with st.form("login_form"):
                uid = st.text_input("Client ID", value="dashboard")
                pwd = st.text_input("Password", type="password", value="kira-dashboard-2024")
                if st.form_submit_button("Authenticate System", use_container_width=True):
                    if login(uid, pwd):
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
            st.info("KIRA utilizes JWT-based immutable auth tokens for audit trail attribution.")
    st.stop()

TOKEN = st.session_state.token

# ── Tower data (single source of truth) ─────────────────────────────────────
@st.cache_data
def load_towers():
    try:
        return pd.read_csv(TOWERS_CSV)
    except FileNotFoundError:
        # Minimal fallback so dashboard still starts if CSV is missing
        return pd.DataFrame({
            'tower_id': ['Gasabo-A', 'Nyarugenge-A', 'Kicukiro-A'],
            'district': ['Gasabo', 'Nyarugenge', 'Kicukiro'],
            'lat': [-1.9167, -1.9500, -1.9833],
            'lng': [30.1333, 30.0500, 30.1167],
            'backup_type': ['Solar', 'Generator', 'Solar'],
        })

towers_df = load_towers()

# ── System Health Ribbon ──────────────────────────────────────────────────────
try:
    health_res = requests.get(f'{API_URL}/api/v1/health', timeout=3)
    health = health_res.json()
    comps = health.get('components', {})
    
    h_col1, h_col2, h_col3, h_col4 = st.columns(4)
    
    def status_chip(ok): return "🟢 OK" if ok else "🔴 FAIL"
    
    h_col1.metric("API Gateway", status_chip(health_res.status_code == 200))
    h_col2.metric("ML Ensembles", status_chip(comps.get('models') == 'ok'))
    h_col3.metric("Redis Lockout", status_chip(comps.get('redis') == 'ok'))
    h_col4.metric("Audit Database", status_chip(comps.get('database') == 'ok'))
    
    if health.get('status') != 'healthy':
        st.warning(f"⚠️ System Degraded: {', '.join(health.get('startup_errors', []))}")
except Exception:
    st.error("🚨 CRITICAL: KIRA Backend Unreachable. System offline.")
    st.stop()

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header('👤 Session')
    st.success(f"Logged in as: **{st.session_state.client_id}**")
    if st.button('🚪 Secure Logout', use_container_width=True):
        logout()

    st.divider()
    st.header('⚙️ System Controls')
    
    with st.expander('📍 Active Assets'):
        st.dataframe(towers_df[['tower_id', 'district', 'backup_type']], hide_index=True)

    st.subheader('🛡️ Manual Override')
    override_tower = st.selectbox('Tower', towers_df['tower_id'].tolist())
    override_action = st.selectbox('Action Class', [0, 1, 2, 3],
                                   format_func=lambda x: {
                                       0: '0 - No Action', 1: '1 - Switch Solar',
                                       2: '2 - Start Generator', 3: '3 - Dispatch Tech'
                                   }[x])
    override_reason = st.text_input('Reason', placeholder='e.g. Planned maintenance window')
    if st.button('⚡ Execute Override', type='primary', use_container_width=True):
        if TOKEN and override_reason:
            district = towers_df[towers_df['tower_id'] == override_tower]['district'].values[0]
            with st.spinner('Authorizing override...'):
                r = requests.post(f'{API_URL}/api/v1/override',
                                  json={'tower_id': override_tower, 'district': district,
                                        'action_class': override_action, 'reason': override_reason},
                                  headers={'Authorization': f'Bearer {TOKEN}'})
                if r.status_code == 200:
                    st.toast('Override executed & logged.', icon='⚡')
                else:
                    st.error(f'Override failed: {r.text}')
        else:
            st.warning('Provide a reason for the override.')


# ── Live Tower Map ────────────────────────────────────────────────────────────
st.subheader('🗺️ Live Tower Map — Kigali')

# Assign colour based on backup type
def tower_color(backup_type):
    return [34, 197, 94, 200] if backup_type == 'Solar' else [251, 191, 36, 200]

towers_df['color'] = towers_df['backup_type'].apply(tower_color)
towers_df['tooltip'] = towers_df.apply(
    lambda r: f"{r['tower_id']} | {r['district']} | {r['backup_type']}", axis=1)

layer = pdk.Layer(
    'ScatterplotLayer',
    towers_df,
    get_position='[lng, lat]',
    get_color='color',
    get_radius=800,
    pickable=True,
)
view_state = pdk.ViewState(latitude=-1.95, longitude=30.08, zoom=11.5, pitch=40)
st.pydeck_chart(pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={'text': '{tooltip}'},
    map_style='mapbox://styles/mapbox/dark-v10',
))

st.divider()


# ── Helper: send prediction and render result ─────────────────────────────────
def send_and_render(endpoint: str, sensor_data: dict, tower_id: str, district: str):
    if not TOKEN:
        st.error('❌ Not authenticated. Check backend connection.')
        return
    payload = {'tower_id': tower_id, 'district': district, 'sensor_data': sensor_data}
    try:
        res = requests.post(
            f'{API_URL}{endpoint}', json=payload,
            headers={'Authorization': f'Bearer {TOKEN}'}, timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            pred = data.get('prediction', {})
            align = data.get('alignment_verdict', {})

            # Decision colour
            decision = align.get('decision', '')
            if 'AUTONOMOUS' in decision:
                st.success(f"✅ **AUTONOMOUS ACTION**: {align.get('action_name', '')}")
            elif 'ALERT_HUMAN' in decision:
                st.warning(f"⚠️ **HUMAN REQUIRED**: {align.get('action_name', '')} — SMS Alert dispatched.")
            elif 'BLOCKED' in decision:
                st.info(f"🔒 **BLOCKED** ({decision}): {align.get('reasoning', '')[:120]}")

            # Metrics row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric('Confidence', f"{pred.get('confidence', 0)*100:.1f}%")
            m2.metric('LSTM Urgency', f"Class {pred.get('lstm_urgency_class', 'N/A')}")
            m3.metric('Anomaly Score', f"{pred.get('anomaly_score', 0):.4f}")
            anomaly = pred.get('anomaly_flag', False)
            m4.metric('Anomaly Flag', '🚨 YES' if anomaly else '✅ NO')

            # SHAP explanation
            shap = pred.get('shap_explanation')
            if shap:
                st.subheader('🔍 AI Decision Rationale')
                st.info(shap.get('human_readable', ''))
                
                top_drivers = shap.get('top_drivers', [])
                if top_drivers:
                    df_shap = pd.DataFrame(top_drivers, columns=['Feature', 'Impact'])
                    df_shap['Direction'] = df_shap['Impact'].apply(lambda x: 'Increase Failure Risk' if x > 0 else 'Decrease Failure Risk')
                    fig = px.bar(df_shap, x='Impact', y='Feature', orientation='h',
                                 color='Direction',
                                 color_discrete_map={'Increase Failure Risk': '#ef4444', 'Decrease Failure Risk': '#22c55e'},
                                 title='Local Feature Importance (SHAP)')
                    fig.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f'API error {res.status_code}: {res.text[:200]}')
    except requests.Timeout:
        st.error('⏱️ Request timed out. Backend may be starting up.')
    except Exception as e:
        st.error(f'Request failed: {e}')


# ── Tabs: 3 Domains ──────────────────────────────────────────────────────────
tab_iot, tab_grid, tab_gen = st.tabs([
    '📡 Telecom IoT', '⚡ REG Power Grid', '⚙️ Backup Generators'
])

# ── TAB 1: Telecom IoT ───────────────────────────────────────────────────────
with tab_iot:
    st.header('Telecom Tower Failure Prediction')
    st.caption('AI Brain: Autoencoder + LSTM + XGBoost | Dataset: IoT Device Failure')

    c1, c2 = st.columns(2)
    with c1:
        st.subheader('Simulate Sensor Telemetry')
        selected_tower = st.selectbox('Tower', towers_df['tower_id'], key='iot_tower')
        tower_district = towers_df[towers_df['tower_id'] == selected_tower]['district'].values[0]

        iot_data = {
            'CPU_Usage (%)':        st.slider('CPU Usage (%)', 0, 100, int(np.random.uniform(20, 90)), key='iot_cpu'),
            'Memory_Usage (%)':     st.slider('Memory Usage (%)', 0, 100, int(np.random.uniform(20, 85)), key='iot_mem'),
            'Battery_Level (%)':    st.slider('Battery Level (%)', 0, 100, int(np.random.uniform(10, 100)), key='iot_bat'),
            'Network_Latency (ms)': st.slider('Network Latency (ms)', 0, 500, int(np.random.uniform(10, 150)), key='iot_lat'),
            'Packet_Loss (%)':      st.slider('Packet Loss (%)', 0, 10, int(np.random.uniform(0, 3)), key='iot_pkt'),
            'Temperature (°C)':     st.slider('Temperature (°C)', 10, 80, int(np.random.uniform(20, 55)), key='iot_tmp'),
            'Uptime (hrs)':         st.slider('Uptime (hrs)', 0, 500, int(np.random.uniform(10, 200)), key='iot_upt'),
            'Workload_Intensity':   st.slider('Workload Intensity', 1, 5, 2, key='iot_wl'),
            'Error_Count':          st.slider('Error Count', 0, 50, int(np.random.uniform(0, 10)), key='iot_err'),
        }

    with c2:
        st.subheader('IoT Brain Analysis')
        if st.button('🧠 Run IoT Analysis', type='primary', key='iot_btn'):
            with st.spinner('Running ensemble inference...'):
                send_and_render('/api/v1/predict/iot', iot_data, selected_tower, tower_district)


# ── TAB 2: REG Power Grid ─────────────────────────────────────────────────────
with tab_grid:
    st.header('REG Power Grid Fault Prediction')
    st.caption('AI Brain: Autoencoder + LSTM + XGBoost | Dataset: Power System Faults')

    c1, c2 = st.columns(2)
    with c1:
        st.subheader('Simulate Grid State')
        selected_tower_g = st.selectbox('Tower', towers_df['tower_id'], key='grid_tower')
        district_g = towers_df[towers_df['tower_id'] == selected_tower_g]['district'].values[0]

        weather = st.selectbox('Weather Condition', ['Clear', 'Rainy', 'Thunderstorm', 'Windstorm', 'Snowy'])
        maintenance = st.selectbox('Maintenance Status', ['Completed', 'Scheduled', 'Pending'])
        health = st.selectbox('Component Health', ['Normal', 'Faulty', 'Overheated'])

        grid_data = {
            'Voltage (V)':              st.slider('Voltage (V)', 1500, 3000, int(np.random.normal(2200, 100)), key='grid_v'),
            'Current (A)':              st.slider('Current (A)', 100, 350, int(np.random.normal(215, 20)), key='grid_a'),
            'Power Load (MW)':          st.slider('Power Load (MW)', 20, 80, int(np.random.normal(50, 8)), key='grid_mw'),
            'Temperature (°C)':         st.slider('Temperature (°C)', 15, 50, int(np.random.normal(28, 5)), key='grid_t'),
            'Wind Speed (km/h)':        st.slider('Wind Speed (km/h)', 0, 60, int(np.random.normal(18, 8)), key='grid_w'),
            'Weather Condition':        weather,
            'Maintenance Status':       maintenance,
            'Component Health':         health,
            'Duration of Fault (hrs)':  st.slider('Fault Duration (hrs)', 0, 10, 1, key='grid_fd'),
            'Down time (hrs)':          st.slider('Downtime (hrs)', 0, 10, 1, key='grid_dt'),
        }

    with c2:
        st.subheader('Grid Brain Analysis')
        if st.button('🧠 Run Grid Analysis', type='primary', key='grid_btn'):
            with st.spinner('Running ensemble inference...'):
                send_and_render('/api/v1/predict/grid', grid_data, selected_tower_g, district_g)


# ── TAB 3: Backup Generators ─────────────────────────────────────────────────
with tab_gen:
    st.header('Backup Generator Predictive Maintenance')
    st.caption('AI Brain: Autoencoder + LSTM + XGBoost | Dataset: Predictive Maintenance')

    c1, c2 = st.columns(2)
    with c1:
        st.subheader('Simulate Mechanical Sensors')
        selected_tower_gen = st.selectbox('Tower', towers_df['tower_id'], key='gen_tower')
        district_gen = towers_df[towers_df['tower_id'] == selected_tower_gen]['district'].values[0]

        gen_data = {
            'vibration':  st.slider('Vibration (g)', 0.0, 5.0, float(np.random.uniform(0.5, 2.0)), step=0.1, key='gen_vib'),
            'acoustic':   st.slider('Acoustic (kHz)', 0.0, 3.0, float(np.random.uniform(0.3, 1.2)), step=0.1, key='gen_ac'),
            'temperature':st.slider('Temperature (°C)', 30, 120, int(np.random.uniform(50, 85)), key='gen_t'),
            'current':    st.slider('Current (A)', 5, 30, int(np.random.uniform(10, 20)), key='gen_cur'),
            'IMF_1':      st.slider('IMF_1', -1.0, 1.0, float(np.random.uniform(-0.3, 0.3)), step=0.01, key='gen_imf1'),
            'IMF_2':      st.slider('IMF_2', -0.5, 0.5, float(np.random.uniform(-0.1, 0.1)), step=0.01, key='gen_imf2'),
            'IMF_3':      st.slider('IMF_3', -0.2, 0.2, float(np.random.uniform(-0.05, 0.05)), step=0.01, key='gen_imf3'),
        }

    with c2:
        st.subheader('Generator Brain Analysis')
        if st.button('🧠 Run Generator Analysis', type='primary', key='gen_btn'):
            with st.spinner('Running ensemble inference...'):
                send_and_render('/api/v1/predict/generator', gen_data, selected_tower_gen, district_gen)


# ── Audit Trail & Analytics ──────────────────────────────────────────────────
st.divider()
st.subheader('📋 System-of-Systems Audit Trail')

col_a1, col_a2 = st.columns([1, 3])

with col_a1:
    st.write("### Filter Events")
    f_tower = st.selectbox('Tower Filter', ['All'] + towers_df['tower_id'].tolist())
    f_limit = st.slider('Record Limit', 10, 200, 50)
    load_audit = st.button('🔍 Query Audit Log', use_container_width=True)

with col_a2:
    if (load_audit or 'first_load' not in st.session_state) and TOKEN:
        st.session_state.first_load = True
        try:
            url = f'{API_URL}/api/v1/audit?limit={f_limit}'
            if f_tower != 'All':
                url += f'&tower_id={f_tower}'
            
            r = requests.get(url, headers={'Authorization': f'Bearer {TOKEN}'}, timeout=5)
            if r.status_code == 200:
                logs = r.json().get('logs', [])
                if logs:
                    df_audit = pd.DataFrame(logs)
                    
                    # Mini Stats
                    s1, s2 = st.columns(2)
                    s1.metric("Total Events", len(df_audit))
                    avg_conf = df_audit['confidence'].mean()
                    s2.metric("Avg Confidence", f"{avg_conf*100:.1f}%")
                    
                    # Action Chart
                    action_counts = df_audit['action_name'].value_counts().reset_index()
                    fig_audit = px.pie(action_counts, values='count', names='action_name', 
                                     title='Distribution of Dispatched Actions',
                                     hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                    fig_audit.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=300)
                    st.plotly_chart(fig_audit, use_container_width=True)

                    st.dataframe(df_audit[['timestamp', 'tower_id', 'action_name', 'confidence', 'triggered_by', 'hw_status']], 
                                 hide_index=True, use_container_width=True)
                else:
                    st.info('No events found for the selected filters.')
        except Exception as e:
            st.error(f'Audit Query Failed: {e}')

st.caption(f'Refreshed: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} UTC | KIRA Sentinel v2.4.0')
