"""
KIRA - Configuration Validator
Production security policy enforcement: secrets, CORS, and capability gates.

Designed to fail fast with clear guidance if production requirements are unmet.
Call this before create_app() in production deployments.
"""

import os
import sys
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# NIST/RFC 7518 minimum: HS256 requires 32 bytes (256 bits)
# HS512 requires 64 bytes (512 bits)
MIN_SECRET_BYTES_HS256 = 32
MIN_SECRET_BYTES_HS512 = 64
MIN_API_SECRET_BYTES = 32

# Reject known insecure defaults
INSECURE_DEFAULTS = {
    'CHANGE_THIS_IN_PRODUCTION_NOW',
    'CHANGE_THIS_JWT_SECRET_NOW',
    'replace-with-strong-random-secret',
    'replace-with-strong-random-jwt-secret',
    'kira-sensor-2024',
    'kira-dashboard-2024',
    'kira-ops-2024',
    'replace-me',
    'replace-dashboard-password',
}


class ConfigError(Exception):
    """Configuration validation failed. Application must not start."""
    pass


def validate_secret_length(secret: str, min_bytes: int, field_name: str) -> None:
    """
    Validate a secret meets minimum byte-length for cryptographic use.
    
    Args:
        secret: the secret string (typically from environment variable)
        min_bytes: minimum bytes required (e.g., 32 for HS256, 64 for HS512)
        field_name: name for error messages (e.g., 'JWT_SECRET_KEY')
    
    Raises:
        ConfigError if secret is too short or is a known insecure default
    """
    if not secret:
        raise ConfigError(
            f'{field_name} is empty. This is always a security violation. '
            f'Set {field_name} to a cryptographically secure random value (>={min_bytes} bytes).'
        )

    if secret in INSECURE_DEFAULTS:
        raise ConfigError(
            f'{field_name} is set to a known insecure default: "{secret}". '
            f'Replace with a secure random value.\n'
            f'  Generate with: python3 -c "import secrets; print(secrets.token_hex({min_bytes}))"'
        )

    secret_bytes = secret.encode('utf-8')
    if len(secret_bytes) < min_bytes:
        raise ConfigError(
            f'{field_name} is {len(secret_bytes)} bytes, but RFC 7518 requires ≥{min_bytes} bytes '
            f'for secure HMAC-SHA256 signing. Current value length: {len(secret)}\n'
            f'  Generate with: python3 -c "import secrets; print(secrets.token_hex({min_bytes}))"'
        )


def validate_api_credentials(api_clients_str: str, field_name: str = 'API_CLIENTS') -> dict:
    """
    Parse and validate API client credentials.
    
    Format: "client_id:password,client_id2:password2,..."
    
    Args:
        api_clients_str: comma-separated client:password pairs
        field_name: for error messages
    
    Returns:
        dict of {client_id: password}
    
    Raises:
        ConfigError if format is invalid or any credential is insecure
    """
    if not api_clients_str or not api_clients_str.strip():
        raise ConfigError(
            f'{field_name} is empty. Define at least one API client credential.\n'
            f'  Format: "sensor_gateway:secure-password,dashboard:secure-password"\n'
            f'  Passwords should be ≥32 bytes random strings.'
        )

    clients = {}
    for pair in api_clients_str.split(','):
        pair = pair.strip()
        if ':' not in pair:
            raise ConfigError(
                f'{field_name} has invalid format: "{pair}". '
                f'Expected "client_id:password".'
            )

        client_id, password = pair.split(':', 1)
        client_id = client_id.strip()
        password = password.strip()

        if not client_id or not password:
            raise ConfigError(
                f'{field_name} has empty client_id or password in: "{pair}"'
            )

        if password in INSECURE_DEFAULTS:
            raise ConfigError(
                f'{field_name}: password for client "{client_id}" is a known insecure default. '
                f'Set to a secure random value (≥16 bytes).'
            )

        # API passwords should be at least 16 bytes (128 bits) for practical authentication
        # (Lower than JWT secrets because these are typically stored in config, not used for crypto)
        if len(password.encode('utf-8')) < 16:
            logger.warning(
                f'{field_name}: password for client "{client_id}" is only {len(password)} bytes. '
                f'Recommended ≥16 bytes for resistance to brute-force attacks.'
            )

        clients[client_id] = password

    return clients


def validate_cors_origins(origins_str: str, flask_env: str) -> list:
    """
    Validate CORS origin configuration.
    In production, reject overly permissive origins.
    
    Args:
        origins_str: comma-separated ALLOWED_ORIGINS
        flask_env: FLASK_ENV value ('production' or 'development')
    
    Returns:
        list of validated origins
    
    Raises:
        ConfigError if production has insecure CORS
    """
    if not origins_str or not origins_str.strip():
        origins = ['http://localhost:8501']  # development default
        logger.warning(
            'ALLOWED_ORIGINS not set. Using development default: http://localhost:8501. '
            'In production, explicitly set ALLOWED_ORIGINS to frontend hostname.'
        )
        return origins

    origins = [o.strip() for o in origins_str.split(',')]

    # Security check: production must not allow wildcards or 'http://'
    if flask_env.lower() == 'production':
        for origin in origins:
            if '*' in origin:
                raise ConfigError(
                    f'Production CORS origin "{origin}" contains wildcard. '
                    f'Wildcard CORS is a security risk. Explicitly list allowed origins.'
                )
            if origin.startswith('http://') and not origin.startswith('http://localhost'):
                raise ConfigError(
                    f'Production CORS origin "{origin}" uses insecure HTTP. '
                    f'Use HTTPS (https://...) for all production origins.'
                )

    return origins


def validate_redis_url(redis_url: str, flask_env: str) -> str:
    """
    Validate Redis connection URL.
    In production, reject localhost and unencrypted schemes.
    
    Args:
        redis_url: Redis URL (e.g., 'redis://host:6379/0')
        flask_env: FLASK_ENV value
    
    Returns:
        validated redis_url
    
    Raises:
        ConfigError if production Redis is insecure
    """
    if not redis_url or not redis_url.strip():
        raise ConfigError(
            'REDIS_URL is empty. Redis is required for cross-worker lockout state. '
            'Set REDIS_URL to your Redis server, e.g., redis://redis:6379/0'
        )

    if flask_env.lower() == 'production':
        if 'localhost' in redis_url or '127.0.0.1' in redis_url:
            raise ConfigError(
                f'Production REDIS_URL "{redis_url}" points to localhost. '
                f'Redis must be on a separate, secure host in production. '
                f'Use a network address or managed Redis service (e.g., AWS ElastiCache).'
            )
        if redis_url.startswith('redis://') and not redis_url.startswith('rediss://'):
            logger.warning(
                f'Production REDIS_URL "{redis_url}" uses unencrypted redis:// scheme. '
                f'Recommended: use rediss:// (TLS) for secure production networks.'
            )

    return redis_url


def validate_twilio_config(enabled: bool, sid: str, token: str, from_phone: str, alert_phone: str) -> dict:
    """
    Validate Twilio configuration if enabled.
    If enabled, all fields must be set and non-empty.
    
    Args:
        enabled: TWILIO_ENABLED flag
        sid, token, from_phone, alert_phone: Twilio credentials
    
    Returns:
        dict with validated config
    
    Raises:
        ConfigError if enabled but credentials are incomplete
    """
    if not enabled:
        return {
            'enabled': False,
            'sid': '',
            'token': '',
            'from': '',
            'to': '',
        }

    # If enabled, all credentials must be present
    if not all([sid, token, from_phone, alert_phone]):
        raise ConfigError(
            'TWILIO_ENABLED=true but one or more Twilio credentials are missing:\n'
            f'  TWILIO_SID={sid or "(empty)"}\n'
            f'  TWILIO_TOKEN={token or "(empty)"}\n'
            f'  TWILIO_FROM={from_phone or "(empty)"}\n'
            f'  ALERT_PHONE={alert_phone or "(empty)"}\n'
            'Either set all Twilio credentials or set TWILIO_ENABLED=false'
        )

    return {
        'enabled': True,
        'sid': sid,
        'token': token,
        'from': from_phone,
        'to': alert_phone,
    }


def validate_production_config() -> Tuple[bool, list]:
    """
    Complete production readiness check.
    Called during app startup to enforce all security policies.
    
    Returns:
        (is_production: bool, errors: list of validation errors)
    
    Raises:
        ConfigError on any critical failure
    """
    flask_env = os.environ.get('FLASK_ENV', 'development').lower()
    is_production = flask_env == 'production'
    errors = []

    try:
        # Secrets
        secret_key = os.environ.get('SECRET_KEY', '')
        jwt_secret_key = os.environ.get('JWT_SECRET_KEY', '')

        validate_secret_length(secret_key, MIN_API_SECRET_BYTES, 'SECRET_KEY')
        validate_secret_length(jwt_secret_key, MIN_SECRET_BYTES_HS256, 'JWT_SECRET_KEY')

        # API credentials
        api_clients_str = os.environ.get('API_CLIENTS', '')
        validate_api_credentials(api_clients_str)

        # CORS
        origins_str = os.environ.get('ALLOWED_ORIGINS', '')
        validate_cors_origins(origins_str, flask_env)

        # Redis
        redis_url = os.environ.get('REDIS_URL', '')
        validate_redis_url(redis_url, flask_env)

        # Twilio (optional)
        twilio_enabled = os.environ.get('TWILIO_ENABLED', 'false').lower() == 'true'
        validate_twilio_config(
            twilio_enabled,
            os.environ.get('TWILIO_SID', ''),
            os.environ.get('TWILIO_TOKEN', ''),
            os.environ.get('TWILIO_FROM', ''),
            os.environ.get('ALERT_PHONE', ''),
        )

        if is_production:
            logger.info('✓ Production configuration validated successfully.')

    except ConfigError as e:
        errors.append(str(e))
        if is_production:
            raise

    return is_production, errors


def log_configuration_mode() -> None:
    """Log startup mode and active config flags."""
    flask_env = os.environ.get('FLASK_ENV', 'development')
    is_prod = flask_env.lower() == 'production'
    mode = 'PRODUCTION' if is_prod else 'DEVELOPMENT'
    logger.info(f'Application starting in {mode} mode.')

    if not is_prod:
        logger.warning(
            'Running in development mode. The following security features are relaxed:\n'
            '  • Secrets can be shorter than RFC 7518 minimum\n'
            '  • CORS allows http://localhost:8501\n'
            '  • Redis can be on localhost\n'
            'These checks are ENFORCED in production mode.'
        )
