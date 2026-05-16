"""
KIRA Command Center — System of Systems Dashboard
Real-time monitoring of 3 critical infrastructure domains with clean, modern UI.
"""

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import requests
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
from typing import Dict, Tuple
import time

from kira_auth import init_session_state, logout, get_session_info, authenticate_user
from pages_auth import render_login_page, render_signup_page, render_verify_page
from styles import THEME, GLOBAL_CSS, get_status_badge_html

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KIRA | Command Center",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialize Session ───────────────────────────────────────────────────────
init_session_state()

# ── Config ───────────────────────────────────────────────────────────────────
API_URL = os.environ.get('KIRA_API_URL', 'http://127.0.0.1:5001')
TOWERS_CSV = os.environ.get('TOWERS_CSV', os.path.join(os.path.dirname(__file__), '..', 'data', 'kigali_infra_data.csv'))

# ── Load Towers Data ─────────────────────────────────────────────────────────
@st.cache_data
def load_towers():
    try:
        return pd.read_csv(TOWERS_CSV)
    except FileNotFoundError:
        return pd.DataFrame({
            'tower_id': ['Gasabo-A', 'Nyarugenge-A', 'Kicukiro-A'],
            'district': ['Gasabo', 'Nyarugenge', 'Kicukiro'],
            'lat': [-1.9167, -1.9500, -1.9833],
            'lng': [30.1333, 30.0500, 30.1167],
            'backup_type': ['Solar', 'Generator', 'Solar'],
        })


# ── AUTHENTICATION GATE ──────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    
    # Page Selection (Login vs Signup)
    if st.session_state.current_page == "signup":
        render_signup_page()
        # Link to switch to login
        if st.button("Back to Login", use_container_width=False):
            st.session_state.current_page = "login"
            st.rerun()
    elif st.session_state.current_page == "verify":
        render_verify_page()
        if st.button("Back to Login", use_container_width=False):
            st.session_state.current_page = "login"
            st.rerun()
    else:
        render_login_page()
        # Link to switch to signup
        if st.button("Create New Account", use_container_width=False):
            st.session_state.current_page = "signup"
            st.rerun()
    
    st.stop()

# ── AUTHENTICATED DASHBOARD ──────────────────────────────────────────────────
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# Header with Brand
col_logo, col_title, col_logout = st.columns([1, 3, 1])

with col_logo:
    st.markdown("### 🔋 KIRA")

with col_title:
    st.markdown("#### System-of-Systems Command Center")

with col_logout:
    st.write("")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

st.divider()

# ── Sidebar Session Info ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 👤 Session Information")
    
    session = get_session_info()
    st.markdown(f"""
    **Client ID:** `{session['client_id']}`  
    **Role:** `operator`  
    **Status:** ✅ Active
    """)
    
    st.divider()
    # Live / Auto-refresh
    st.markdown("### 🔁 Live Mode")
    live_mode = st.checkbox('Live — auto-refresh health and map', value=False, key='live_mode')
    refresh_interval = st.slider('Refresh interval (s)', 2, 30, 5, key='refresh_interval')
    if live_mode:
        st.markdown(f"Auto-refreshing every {refresh_interval}s")
    
    # Active Assets
    st.markdown("### 📍 Active Assets")
    towers_df = load_towers()
    
    with st.expander("View Towers", expanded=True):
        for _, tower in towers_df.iterrows():
            st.markdown(f"""
            - **{tower['tower_id']}** ({tower['district']})  
              Backup: `{tower['backup_type']}`
            """)
    
    st.divider()
    
    # Manual Override
    st.markdown("### ⚡ Manual Override")
    
    override_tower = st.selectbox('Tower', towers_df['tower_id'].tolist(), key='override_tower')
    override_action = st.selectbox(
        'Action',
        [0, 1, 2, 3],
        format_func=lambda x: {
            0: '0 - No Action',
            1: '1 - Switch Solar',
            2: '2 - Start Generator',
            3: '3 - Dispatch Tech'
        }[x],
        key='override_action'
    )
    override_reason = st.text_input(
        'Reason',
        placeholder='Planned maintenance',
        key='override_reason'
    )
    
    if st.button('⚡ Execute Override', type='primary', use_container_width=True):
        if override_reason:
            district = towers_df[towers_df['tower_id'] == override_tower]['district'].values[0]
            with st.spinner('Authorizing override...'):
                try:
                    r = requests.post(
                        f'{API_URL}/api/v1/override',
                        json={
                            'tower_id': override_tower,
                            'district': district,
                            'action_class': override_action,
                            'reason': override_reason
                        },
                        headers={'Authorization': f'Bearer {st.session_state.token}'},
                        timeout=5
                    )
                    if r.status_code == 200:
                        st.success('✅ Override executed & logged')
                    else:
                        st.error(f'Override failed: {r.text}')
                except Exception as e:
                    st.error(f'Error: {e}')
        else:
            st.warning('Provide a reason for the override')


# ── System Health Status ─────────────────────────────────────────────────────
st.markdown("### 🔍 System Health Status")

@st.cache_data(ttl=5)
def _cached_health(api_url: str):
    return requests.get(f'{api_url}/api/v1/health', timeout=3).json()

try:
    if st.session_state.get('live_mode'):
        # Live: fetch fresh health data (no cache)
        health_res = requests.get(f'{API_URL}/api/v1/health', timeout=3)
        health = health_res.json()
    else:
        # Cached health for faster loads
        health = _cached_health(API_URL)
    comps = health.get('components', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
                    border: 1px solid {THEME['border']}; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">🟢</div>
            <div style="color: {THEME['text_muted']}; font-size: 0.85rem; margin-bottom: 8px;">API Gateway</div>
            <div style="color: {THEME['primary']}; font-weight: 700;">OK</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        ml_status = "🟢 OK" if comps.get('models') == 'ok' else "🔴 FAIL"
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
                    border: 1px solid {THEME['border']}; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">🧠</div>
            <div style="color: {THEME['text_muted']}; font-size: 0.85rem; margin-bottom: 8px;">ML Ensembles</div>
            <div style="color: {THEME['primary']}; font-weight: 700;">{ml_status}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        redis_status = "🟢 OK" if comps.get('redis') == 'ok' else "🔴 FAIL"
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
                    border: 1px solid {THEME['border']}; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">⚙️</div>
            <div style="color: {THEME['text_muted']}; font-size: 0.85rem; margin-bottom: 8px;">Redis Cache</div>
            <div style="color: {THEME['primary']}; font-weight: 700;">{redis_status}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        db_status = "🟢 OK" if comps.get('database') == 'ok' else "🔴 FAIL"
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {THEME['card_bg']} 0%, #1e293b 100%);
                    border: 1px solid {THEME['border']}; border-radius: 12px; padding: 16px; text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">💾</div>
            <div style="color: {THEME['text_muted']}; font-size: 0.85rem; margin-bottom: 8px;">Audit Database</div>
            <div style="color: {THEME['primary']}; font-weight: 700;">{db_status}</div>
        </div>
        """, unsafe_allow_html=True)
    
    if health.get('status') != 'healthy':
        st.warning(f"⚠️ System Degraded: {', '.join(health.get('startup_errors', []))}")

except Exception as e:
    st.error(f"🚨 CRITICAL: KIRA Backend Unreachable. Error: {e}")
    st.stop()

# Auto-refresh: when live_mode is enabled, wait 'refresh_interval' seconds and rerun
if st.session_state.get('live_mode'):
    time.sleep(st.session_state.get('refresh_interval', 5))
    st.experimental_rerun()

st.divider()

# ── Live Tower Map ───────────────────────────────────────────────────────────
st.markdown("### 🗺️ Live Tower Map — Kigali")

towers_df = load_towers()

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

# ── Helper Function: Send Prediction ─────────────────────────────────────────
def send_and_render(endpoint: str, sensor_data: dict, tower_id: str, district: str):
    """Send prediction request and render results."""
    if not st.session_state.token:
        st.error('❌ Not authenticated')
        return
    
    payload = {'tower_id': tower_id, 'district': district, 'sensor_data': sensor_data}
    
    # Client-side short-term caching: reuse prediction for same payload within 5s
    cache_key = f"pred:{endpoint}:{tower_id}:{hash(str(sorted(sensor_data.items())))}"
    cached = st.session_state.get('_pred_cache', {})
    cached_entry = cached.get(cache_key)
    if cached_entry and (time.time() - cached_entry['ts'] < 5):
        data = cached_entry['value']
    else:
        try:
            res = requests.post(
                f'{API_URL}{endpoint}',
                json=payload,
                headers={'Authorization': f'Bearer {st.session_state.token}'},
                timeout=10,
            )
        except requests.Timeout:
            st.error('⏱️ Request timed out')
            return
        except Exception as e:
            st.error(f'Error: {e}')
            return

        if res.status_code == 200:
            data = res.json()
            # store in session cache
            cached.setdefault(cache_key, {})
            cached[cache_key] = {'ts': time.time(), 'value': data}
            st.session_state['_pred_cache'] = cached
        else:
            st.error(f'API error {res.status_code}')
            return
        
        if data:
            pred = data.get('prediction', {})
            align = data.get('alignment_verdict', {})
            
            # Decision
            decision = align.get('decision', '')
            if 'AUTONOMOUS' in decision:
                st.success(f"✅ **AUTONOMOUS ACTION**: {align.get('action_name', '')}")
            elif 'ALERT_HUMAN' in decision:
                st.warning(f"⚠️ **HUMAN REQUIRED**: {align.get('action_name', '')}")
            elif 'BLOCKED' in decision:
                st.info(f"🔒 **BLOCKED**: {align.get('reasoning', '')[:120]}")
            
            # Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric('Confidence', f"{pred.get('confidence', 0)*100:.1f}%")
            m2.metric('LSTM Urgency', f"Class {pred.get('lstm_urgency_class', 'N/A')}")
            m3.metric('Anomaly Score', f"{pred.get('anomaly_score', 0):.4f}")
            anomaly = pred.get('anomaly_flag', False)
            m4.metric('Anomaly Flag', '🚨 YES' if anomaly else '✅ NO')
            
            # SHAP
            shap = pred.get('shap_explanation')
            if shap:
                st.subheader('🔍 AI Decision Rationale')
                st.info(shap.get('human_readable', ''))
                
                top_drivers = shap.get('top_drivers', [])
                if top_drivers:
                    df_shap = pd.DataFrame(top_drivers, columns=['Feature', 'Impact'])
                    df_shap['Direction'] = df_shap['Impact'].apply(
                        lambda x: 'Increase Risk' if x > 0 else 'Decrease Risk'
                    )
                    fig = px.bar(
                        df_shap, x='Impact', y='Feature', orientation='h',
                        color='Direction',
                        color_discrete_map={
                            'Increase Risk': '#ef4444',
                            'Decrease Risk': '#22c55e'
                        },
                        title='Feature Importance (SHAP)'
                    )
                    fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f'API error {res.status_code}')
    
    # note: exceptions are handled per-request above; no outer try/except required here


# ── Tabs: 3 Infrastructure Domains ───────────────────────────────────────────
st.markdown("### 🔄 Domain-Specific Analysis")

tab_iot, tab_grid, tab_gen = st.tabs(['📡 Telecom IoT', '⚡ REG Power Grid', '⚙️ Backup Generators'])

# IoT Tab
with tab_iot:
    st.header('Telecom Tower Failure Prediction')
    st.caption('Ensemble: Autoencoder + LSTM + XGBoost')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader('Sensor Telemetry')
        selected_tower = st.selectbox('Tower', towers_df['tower_id'], key='iot_tower')
        tower_district = towers_df[towers_df['tower_id'] == selected_tower]['district'].values[0]
        
        iot_data = {
            'CPU_Usage (%)': st.slider('CPU Usage (%)', 0, 100, 50, key='iot_cpu'),
            'Memory_Usage (%)': st.slider('Memory Usage (%)', 0, 100, 60, key='iot_mem'),
            'Battery_Level (%)': st.slider('Battery Level (%)', 0, 100, 75, key='iot_bat'),
            'Network_Latency (ms)': st.slider('Latency (ms)', 0, 500, 100, key='iot_lat'),
            'Packet_Loss (%)': st.slider('Packet Loss (%)', 0, 10, 2, key='iot_pkt'),
            'Temperature (°C)': st.slider('Temperature (°C)', 10, 80, 40, key='iot_tmp'),
            'Uptime (hrs)': st.slider('Uptime (hrs)', 0, 500, 100, key='iot_upt'),
            'Workload_Intensity': st.slider('Workload', 1, 5, 2, key='iot_wl'),
            'Error_Count': st.slider('Error Count', 0, 50, 5, key='iot_err'),
        }
    
    with col2:
        st.subheader('Analysis Results')
        if st.button('🧠 Run Analysis', type='primary', key='iot_btn', use_container_width=True):
            send_and_render('/api/v1/predict/iot', iot_data, selected_tower, tower_district)

# Grid Tab
with tab_grid:
    st.header('REG Power Grid Fault Prediction')
    st.caption('Ensemble: Autoencoder + LSTM + XGBoost')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader('Grid State')
        selected_tower_g = st.selectbox('Tower', towers_df['tower_id'], key='grid_tower')
        district_g = towers_df[towers_df['tower_id'] == selected_tower_g]['district'].values[0]
        
        weather = st.selectbox('Weather', ['Clear', 'Rainy', 'Thunderstorm', 'Windstorm'], key='weather')
        maintenance = st.selectbox('Maintenance', ['Completed', 'Scheduled', 'Pending'], key='maint')
        health_status = st.selectbox('Health', ['Normal', 'Faulty', 'Overheated'], key='health')
        
        grid_data = {
            'Voltage (V)': st.slider('Voltage (V)', 1500, 3000, 2200, key='v'),
            'Current (A)': st.slider('Current (A)', 100, 350, 215, key='a'),
            'Power Load (MW)': st.slider('Load (MW)', 20, 80, 50, key='mw'),
            'Temperature (°C)': st.slider('Temp (°C)', 15, 50, 28, key='temp'),
            'Wind Speed (km/h)': st.slider('Wind (km/h)', 0, 60, 18, key='wind'),
            'Weather Condition': weather,
            'Maintenance Status': maintenance,
            'Component Health': health_status,
            'Duration of Fault (hrs)': st.slider('Fault Duration (hrs)', 0, 10, 1, key='fd'),
            'Down time (hrs)': st.slider('Downtime (hrs)', 0, 10, 1, key='dt'),
        }
    
    with col2:
        st.subheader('Analysis Results')
        if st.button('🧠 Run Analysis', type='primary', key='grid_btn', use_container_width=True):
            send_and_render('/api/v1/predict/grid', grid_data, selected_tower_g, district_g)

# Generator Tab
with tab_gen:
    st.header('Backup Generator Predictive Maintenance')
    st.caption('Ensemble: Autoencoder + LSTM + XGBoost')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader('Mechanical Sensors')
        selected_tower_gen = st.selectbox('Tower', towers_df['tower_id'], key='gen_tower')
        district_gen = towers_df[towers_df['tower_id'] == selected_tower_gen]['district'].values[0]
        
        gen_data = {
            'vibration': st.slider('Vibration (g)', 0.0, 5.0, 1.0, step=0.1, key='vib'),
            'acoustic': st.slider('Acoustic (kHz)', 0.0, 3.0, 0.8, step=0.1, key='ac'),
            'temperature': st.slider('Temperature (°C)', 30, 120, 70, key='gen_t'),
            'current': st.slider('Current (A)', 5, 30, 15, key='cur'),
            'IMF_1': st.slider('IMF_1', -1.0, 1.0, 0.0, step=0.01, key='imf1'),
            'IMF_2': st.slider('IMF_2', -0.5, 0.5, 0.0, step=0.01, key='imf2'),
            'IMF_3': st.slider('IMF_3', -0.2, 0.2, 0.0, step=0.01, key='imf3'),
        }
    
    with col2:
        st.subheader('Analysis Results')
        if st.button('🧠 Run Analysis', type='primary', key='gen_btn', use_container_width=True):
            send_and_render('/api/v1/predict/generator', gen_data, selected_tower_gen, district_gen)

st.divider()

# ── Audit Trail ──────────────────────────────────────────────────────────────
st.markdown("### 📋 Audit Trail")

col_a1, col_a2 = st.columns([1, 3])

with col_a1:
    f_tower = st.selectbox('Filter by Tower', ['All'] + towers_df['tower_id'].tolist())
    f_limit = st.slider('Records', 10, 200, 50)
    load_audit = st.button('🔍 Query Log', use_container_width=True)

with col_a2:
    if load_audit and st.session_state.token:
        try:
            url = f'{API_URL}/api/v1/audit?limit={f_limit}'
            if f_tower != 'All':
                url += f'&tower_id={f_tower}'
            
            r = requests.get(url, headers={'Authorization': f'Bearer {st.session_state.token}'}, timeout=5)
            if r.status_code == 200:
                logs = r.json().get('logs', [])
                if logs:
                    df_audit = pd.DataFrame(logs)
                    
                    s1, s2 = st.columns(2)
                    s1.metric("Total Events", len(df_audit))
                    s2.metric("Avg Confidence", f"{df_audit['confidence'].mean()*100:.1f}%")
                    
                    st.dataframe(
                        df_audit[['timestamp', 'tower_id', 'action_name', 'confidence']],
                        hide_index=True, use_container_width=True
                    )
                else:
                    st.info('No events found')
        except Exception as e:
            st.error(f'Query Failed: {e}')

st.caption(f'🕐 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} UTC | KIRA v2.4.0')
