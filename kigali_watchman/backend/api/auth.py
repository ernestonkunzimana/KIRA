"""
KIRA - JWT Authentication
Service 2, API Layer

Token-based authentication for all prediction and actuator endpoints.
The /auth/token endpoint issues tokens for valid credentials.
All other sensitive endpoints require a valid Bearer token.

Security features:
  - Brute-force detection: tracks failed auth attempts per IP
  - All auth attempts are logged for audit trail
  - JWT tokens have expiration (1 hour production, 24h dev)
  - Rate limiting on /auth/token endpoint (10 per minute)
"""

import logging
import os
import secrets
import smtplib
import ssl
import time
import json
from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import (
    JWTManager, create_access_token, verify_jwt_in_request,
    get_jwt_identity, get_jwt,
)
import requests
import bcrypt

logger = logging.getLogger(__name__)
jwt = JWTManager()

# In production these come from a DB or secrets manager.
# For this project: set via environment variable or .env file.
# Format: comma-separated "clientid:password" pairs
# Example: API_CLIENTS=sensor_gateway:pw1,dashboard:pw2,ops_team:pw3
_DEFAULT_CLIENTS = {
    'sensor_gateway': 'kira-sensor-2024',
    'dashboard':      'kira-dashboard-2024',
    'ops_team':       'kira-ops-2024',
}

_AUTH_STORE_PATH = os.environ.get(
    'AUTH_STORE_PATH',
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'auth_accounts.json'),
)

# Runtime-only stores for newly registered accounts and confirmation codes.
_REGISTERED_CLIENTS = {}
_PENDING_VERIFICATIONS = {}

# Brute-force detection tracker
_auth_tracker = None


def get_auth_tracker():
    """Lazy-load the authentication security tracker."""
    global _auth_tracker
    if _auth_tracker is None:
        from security_audit import AuthenticationSecurityTracker
        _auth_tracker = AuthenticationSecurityTracker()
    return _auth_tracker


def _load_auth_store() -> dict:
    """Load the on-disk account store used for verified registrations."""
    try:
        if os.path.exists(_AUTH_STORE_PATH):
            with open(_AUTH_STORE_PATH, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
                if isinstance(data, dict):
                    data.setdefault('accounts', {})
                    data.setdefault('pending', {})
                    return data
    except Exception as exc:
        logger.warning(f'AUTH STORE LOAD FAILED: {exc}')

    return {'accounts': {}, 'pending': {}}


def _save_auth_store(store: dict) -> None:
    """Persist the account store to disk."""
    os.makedirs(os.path.dirname(_AUTH_STORE_PATH), exist_ok=True)
    tmp_path = f'{_AUTH_STORE_PATH}.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as handle:
        json.dump(store, handle, indent=2, sort_keys=True)
    os.replace(tmp_path, _AUTH_STORE_PATH)


def _sync_runtime_cache() -> None:
    """Keep in-memory verification state aligned with the store."""
    store = _load_auth_store()
    _REGISTERED_CLIENTS.clear()
    _REGISTERED_CLIENTS.update(store.get('accounts', {}))
    _PENDING_VERIFICATIONS.clear()
    _PENDING_VERIFICATIONS.update(store.get('pending', {}))


def get_valid_clients() -> dict:
    """Return machine/service clients from env or defaults.

    Note: registered human accounts are stored with hashed passwords
    and are validated separately in the token endpoint.
    """
    _sync_runtime_cache()
    raw = os.environ.get('API_CLIENTS', '')
    if not raw:
        clients = dict(_DEFAULT_CLIENTS)
    else:
        clients = {}
        for pair in raw.split(','):
            parts = pair.strip().split(':')
            if len(parts) == 2:
                clients[parts[0]] = parts[1]
        clients = clients or dict(_DEFAULT_CLIENTS)

    return clients


def _generate_verification_code() -> str:
    # Cryptographically secure 6-digit numeric code
    return f"{secrets.randbelow(900000) + 100000:06d}"


def _send_email_verification(email: str, client_id: str, code: str) -> tuple[bool, str]:
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user or 'no-reply@kira.local')

    if not smtp_host or not smtp_user or not smtp_password:
        return False, 'SMTP not configured'

    message = (
        f"Subject: KIRA account verification\n"
        f"To: {email}\n"
        f"From: {smtp_from}\n\n"
        f"Your KIRA verification code is {code}.\n\n"
        f"Client ID: {client_id}\n"
        f"This code expires in 10 minutes."
    )

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [email], message)
        return True, 'Email sent'
    except Exception as exc:
        logger.warning(f'EMAIL VERIFICATION FAILED: {exc}')
        return False, str(exc)


def _send_sms_verification(phone: str, client_id: str, code: str) -> tuple[bool, str]:
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_FROM_NUMBER')

    if not account_sid or not auth_token or not from_number:
        return False, 'SMS not configured'

    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    body = {
        'From': from_number,
        'To': phone,
        'Body': f'KIRA verification code: {code} for {client_id}. Expires in 10 minutes.',
    }

    try:
        response = requests.post(url, data=body, auth=(account_sid, auth_token), timeout=10)
        if response.status_code in (200, 201):
            return True, 'SMS sent'
        return False, response.text
    except Exception as exc:
        logger.warning(f'SMS VERIFICATION FAILED: {exc}')
        return False, str(exc)


def register_auth_routes(app):
    """Register the /auth/token endpoint on the Flask app."""

    @app.route('/auth/token', methods=['POST'])
    def get_token():
        """
        POST /auth/token
        Body: {"client_id": "sensor_gateway", "password": "..."}
        Returns: {"access_token": "...", "expires_in": 3600}
        
        Implements:
          - Brute-force detection (5 failures in 5 min -> block)
          - Audit logging
          - Rate limiting (enforced by limiter in main.py)
        """
        from security_audit import log_auth_event
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        client_id = data.get('client_id', '').strip()
        # Accept both 'password' and 'client_secret' so the dashboard and direct API calls both work
        password = (data.get('password') or data.get('client_secret') or '').strip()

        valid_clients = get_valid_clients()
        ip_address = request.remote_addr

        if not client_id or not password:
            return jsonify({'error': 'client_id and password/client_secret required'}), 400

        # Check for brute-force attempts
        tracker = get_auth_tracker()
        attempt_count, is_suspicious = tracker.record_failed_attempt(ip_address)
        
        if is_suspicious:
            log_auth_event(client_id, False, ip_address, reason='Brute-force block')
            return jsonify({'error': 'Too many failed attempts. Try again later.'}), 429

        # Check machine/service clients first (plaintext password comparison)
        if valid_clients.get(client_id) == password:
            # Successful machine client authentication: clear failure history
            tracker.record_successful_attempt(ip_address)
            log_auth_event(client_id, True, ip_address)
        # Then check registered human accounts (bcrypt hashed passwords)
        elif client_id in _REGISTERED_CLIENTS:
            account = _REGISTERED_CLIENTS[client_id]
            # Account must be verified before token issuance
            if not account.get('verified'):
                log_auth_event(client_id, False, ip_address, reason='Account not verified')
                logger.warning(f'AUTH FAILED: client_id={client_id} not verified | ip={ip_address}')
                return jsonify({'error': 'Account verification required. Check /auth/verify'}), 403
            # Check bcrypt hashed password
            password_hash = account.get('password_hash', '')
            if not password_hash or not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                log_auth_event(client_id, False, ip_address, reason='Invalid password')
                logger.warning(f'AUTH FAILED: client_id={client_id} invalid password | ip={ip_address}')
                return jsonify({'error': 'Invalid credentials'}), 401
            # Successful human account authentication: clear failure history
            tracker.record_successful_attempt(ip_address)
            log_auth_event(client_id, True, ip_address)
        else:
            # Client ID not found in either machine clients or registered accounts
            log_auth_event(client_id, False, ip_address, reason='Invalid credentials')
            logger.warning(f'AUTH FAILED: client_id={client_id} not found | ip={ip_address}')
            return jsonify({'error': 'Invalid credentials'}), 401

        token = create_access_token(
            identity=client_id,
            additional_claims={'client_id': client_id, 'role': 'api_client'},
        )

        logger.info(f'AUTH SUCCESS: client_id={client_id} | ip={ip_address}')
        return jsonify({
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 3600),
            'client_id': client_id,
        }), 200


def require_auth(fn):
    """
    Decorator: requires a valid JWT Bearer token.
    Usage: @require_auth on any Flask route.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            # Token verified; client has been authenticated
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f'AUTH REJECTED: {e} | ip={request.remote_addr} | path={request.path}')
            return jsonify({
                'error': 'Unauthorized',
                'detail': 'Valid Bearer token required. POST /auth/token to obtain one.',
            }), 401
    return wrapper


def add_register_endpoint(app):
    """Add /auth/register endpoint for new user registration."""
    from security_audit import log_auth_event
    
    @app.route('/auth/register', methods=['POST'])
    def register():
        """
        POST /auth/register
        Body: {
            "client_id": "john.doe_ops",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "organization": "REG",
            "department": "Operations",
            "role": "Operator"
        }
        Returns: {"client_id": "...", "message": "Registration successful"}
        
        Implements:
          - Email validation
          - Password strength validation
          - Duplicate client_id detection
          - Audit logging
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'JSON body required'}), 400
        
        required_fields = ['client_id', 'password', 'first_name', 'last_name', 'email']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400
        
        client_id = data.get('client_id', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()
        
        # Validation: client_id format
        if len(client_id) < 3:
            return jsonify({'error': 'Client ID must be at least 3 characters'}), 400
        
        # Validation: email format
        if '@' not in email:
            return jsonify({'error': 'Valid email required'}), 400
        
        # Validation: password strength
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        phone = (data.get('phone') or '').strip()
        if not phone and not email:
            return jsonify({'error': 'Provide at least an email or phone number for verification'}), 400

        # Check for existing client_id (in production, check database)
        valid_clients = get_valid_clients()
        if client_id in valid_clients or client_id in _REGISTERED_CLIENTS:
            log_auth_event(client_id, False, request.remote_addr, reason='Client ID already exists')
            return jsonify({'error': 'Client ID already registered'}), 409

        store = _load_auth_store()
        
        verification_code = _generate_verification_code()
        expires_at = time.time() + 600

        # Hash the password before storing
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        account_record = {
            'password_hash': password_hash,
            'first_name': data.get('first_name', '').strip(),
            'last_name': data.get('last_name', '').strip(),
            'email': email,
            'phone': phone,
            'organization': data.get('organization', '').strip(),
            'department': data.get('department', '').strip(),
            'role': data.get('role', '').strip(),
            'verified': False,
            'created_at': time.time(),
        }
        pending_record = {
            'code': verification_code,
            'expires_at': expires_at,
            'email_sent': False,
            'sms_sent': False,
        }

        store['accounts'][client_id] = account_record
        store['pending'][client_id] = pending_record
        _REGISTERED_CLIENTS[client_id] = account_record
        _PENDING_VERIFICATIONS[client_id] = pending_record
        _save_auth_store(store)

        email_sent, email_message = _send_email_verification(email, client_id, verification_code)
        sms_sent, sms_message = (False, 'SMS not provided')
        if phone:
            sms_sent, sms_message = _send_sms_verification(phone, client_id, verification_code)

        _PENDING_VERIFICATIONS[client_id]['email_sent'] = email_sent
        _PENDING_VERIFICATIONS[client_id]['sms_sent'] = sms_sent
        store = _load_auth_store()
        if client_id in store.get('pending', {}):
            store['pending'][client_id]['email_sent'] = email_sent
            store['pending'][client_id]['sms_sent'] = sms_sent
            _save_auth_store(store)

        logger.info(f'NEW REGISTRATION: client_id={client_id} | email={email} | phone={phone} | organization={data.get("organization")}')
        log_auth_event(client_id, True, request.remote_addr, reason='New account registration pending verification')

        channels = []
        if email_sent:
            channels.append('email')
        if sms_sent:
            channels.append('sms')

        return jsonify({
            'client_id': client_id,
            'message': 'Registration created. Verify your account using the code sent to email or phone.',
            'verification_required': True,
            'delivery_pending': (not email_sent and not sms_sent),
            'channels': channels,
            'email_confirmation': email_sent,
            'sms_confirmation': sms_sent,
            'email_error': email_message if not email_sent else None,
            'sms_error': sms_message if not sms_sent else None,
            'verification_code': verification_code if (not email_sent and not sms_sent) else None,
        }), 201

    @app.route('/auth/verify', methods=['POST'])
    def verify_registration():
        """Confirm a pending registration using the verification code."""
        data = request.get_json(silent=True) or {}
        client_id = data.get('client_id', '').strip()
        code = data.get('code', '').strip()

        if not client_id or not code:
            return jsonify({'error': 'client_id and code are required'}), 400

        pending = _PENDING_VERIFICATIONS.get(client_id)
        user = _REGISTERED_CLIENTS.get(client_id)

        if not pending or not user:
            return jsonify({'error': 'No pending verification found'}), 404

        if time.time() > pending['expires_at']:
            return jsonify({'error': 'Verification code expired'}), 410

        if pending['code'] != code:
            return jsonify({'error': 'Invalid verification code'}), 401

        user['verified'] = True
        _REGISTERED_CLIENTS[client_id] = user
        _PENDING_VERIFICATIONS.pop(client_id, None)

        store = _load_auth_store()
        if client_id in store.get('accounts', {}):
            store['accounts'][client_id]['verified'] = True
        store.get('pending', {}).pop(client_id, None)
        _save_auth_store(store)

        log_auth_event(client_id, True, request.remote_addr, reason='Account verified')
        return jsonify({
            'client_id': client_id,
            'message': 'Account verified successfully. You can now sign in.',
        }), 200
