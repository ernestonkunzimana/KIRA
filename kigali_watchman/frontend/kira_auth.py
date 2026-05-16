"""
KIRA Frontend: Authentication Module
Handles login, signup, and session management.
"""

import streamlit as st
import requests
import json
from datetime import datetime
from typing import Optional, Dict, Tuple
import re
import os

# Load API URL from environment, secrets, or default.
# Avoid accessing Streamlit secrets in a way that can raise when no
# secrets.toml is present. Prefer env var fallback and safely probe
# `st.secrets` inside a guarded try/except.
API_URL = os.getenv("KIRA_API_URL", "http://127.0.0.1:5001")
try:
    if hasattr(st, "secrets"):
        try:
            val = None
            if hasattr(st.secrets, "get"):
                val = st.secrets.get("KIRA_API_URL")
            if not val:
                try:
                    val = st.secrets["KIRA_API_URL"]
                except Exception:
                    val = val
            if val:
                API_URL = val
        except Exception:
            pass
except Exception:
            API_URL = os.getenv("KIRA_API_URL", "http://127.0.0.1:5001")


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_strong_password(password: str) -> Tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    return True, "Password is strong"


def authenticate_user(client_id: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Authenticate user with backend."""
    try:
        response = requests.post(
            f"{API_URL}/auth/token",
            json={"client_id": client_id, "client_secret": password},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            return True, token, None

        error = response.json().get("error", "Authentication failed")
        return False, None, error
    except requests.Timeout:
        return False, None, "Connection timeout. Backend may be offline."
    except Exception as e:
        return False, None, f"Network error: {str(e)}"


def register_user(user_data: Dict) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict]]:
    """Register a new user via backend signup endpoint."""
    try:
        response = requests.post(
            f"{API_URL}/auth/register",
            json=user_data,
            timeout=10,
        )

        if response.status_code == 201:
            data = response.json()
            return True, data.get("client_id"), None, data

        error = response.json().get("error", "Registration failed")
        return False, None, error, None
    except requests.Timeout:
        return False, None, "Connection timeout. Backend may be offline.", None
    except Exception as e:
        return False, None, f"Network error: {str(e)}", None


def verify_registration(client_id: str, code: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Verify a pending registration using the backend verification code."""
    try:
        response = requests.post(
            f"{API_URL}/auth/verify",
            json={"client_id": client_id, "code": code},
            timeout=10,
        )

        if response.status_code == 200:
            return True, client_id, None

        error = response.json().get("error", "Verification failed")
        return False, None, error
    except requests.Timeout:
        return False, None, "Connection timeout. Backend may be offline."
    except Exception as e:
        return False, None, f"Network error: {str(e)}"


def init_session_state():
    """Initialize session state variables."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "token" not in st.session_state:
        st.session_state.token = None
    if "client_id" not in st.session_state:
        st.session_state.client_id = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    if "login_time" not in st.session_state:
        st.session_state.login_time = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "login"
    if "pending_client_id" not in st.session_state:
        st.session_state.pending_client_id = None
    if "pending_password" not in st.session_state:
        st.session_state.pending_password = None
    if "pending_verification_code" not in st.session_state:
        st.session_state.pending_verification_code = None


def logout():
    """Log out the current user."""
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.client_id = None
    st.session_state.user_role = None
    st.session_state.login_time = None
    st.session_state.current_page = "login"
    st.rerun()


def get_session_info() -> Dict:
    """Get current session information."""
    return {
        "authenticated": st.session_state.get("authenticated", False),
        "client_id": st.session_state.get("client_id"),
        "token": st.session_state.get("token"),
        "user_role": st.session_state.get("user_role"),
        "login_time": st.session_state.get("login_time"),
    }