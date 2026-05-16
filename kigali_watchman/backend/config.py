"""
KIRA Backend - Configuration
Reads from .env file or environment variables.
Never hardcode secrets here. This file is safe to commit.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE_THIS_IN_PRODUCTION_NOW_32BYTES!')
    DEBUG = False

    # JWT (minimum 32 bytes for RFC 7518 HS256 compliance)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'CHANGE_THIS_JWT_SECRET_NOW_32bytes!!')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_EXPIRES_SECONDS', 3600))

    # Database (audit log)
    AUDIT_DB_PATH = os.environ.get('AUDIT_DB_PATH', 'kira_audit.db')

    # Rate limiting
    RATELIMIT_PREDICT = os.environ.get('RATELIMIT_PREDICT', '60 per minute')
    RATELIMIT_DEFAULT = '200 per minute'

    # ---- Rate Limit Storage ----
    # CRITICAL: Rate limiting state must be stored in Redis for production.
    # This ensures cross-worker coordination: all Gunicorn workers share the same limits.
    # If stored in-process memory, each worker has independent rate-limit state,
    # allowing clients to bypass limits by distributing requests across workers.
    # Example: 4 workers * 60 requests/minute = 240 effective limit (WRONG)
    # Flask-Limiter will fail fast if Redis is unavailable (proper fail-safe).
    # Alignment thresholds
    # These defaults are calibrated from real data distributions (0.75-0.93 typical on Kaggle).
    # After training, update AUTONOMOUS_THRESHOLD in .env to the printed 99th-percentile value.
    AUTONOMOUS_ACTION_THRESHOLD = float(os.environ.get('AUTONOMOUS_THRESHOLD', 0.88))
    ALERT_THRESHOLD = float(os.environ.get('ALERT_THRESHOLD', 0.65))
    ACTUATOR_LOCKOUT_SECONDS = int(os.environ.get('LOCKOUT_SECONDS', 600))

    # Redis (cross-worker lockout state)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Actuator (Twilio SMS - optional, disabled by default)
    TWILIO_ENABLED = os.environ.get('TWILIO_ENABLED', 'false').lower() == 'true'
    TWILIO_SID = os.environ.get('TWILIO_SID', '')
    TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN', '')
    TWILIO_FROM = os.environ.get('TWILIO_FROM', '')
    ALERT_PHONE = os.environ.get('ALERT_PHONE', '')

    # CORS (for Streamlit frontend)
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8501').split(',')


class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24h for dev convenience


class ProductionConfig(Config):
    DEBUG = False
    JWT_ACCESS_TOKEN_EXPIRES = 1800  # 30 min in prod


CONFIG_MAP = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}


def get_config() -> Config:
    env = os.environ.get('FLASK_ENV', 'development')
    return CONFIG_MAP.get(env, DevelopmentConfig)
