"""
Tests: Config Validator
Verifies production security policies are enforced at startup.

Run: pytest tests/test_config_validator.py -v
"""

import os
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config_validator import (
    validate_secret_length,
    validate_api_credentials,
    validate_cors_origins,
    validate_redis_url,
    validate_twilio_config,
    ConfigError,
    MIN_SECRET_BYTES_HS256,
)


class TestSecretValidation:

    def test_empty_secret_rejected(self):
        """Empty secrets must always be rejected."""
        with pytest.raises(ConfigError, match='empty'):
            validate_secret_length('', MIN_SECRET_BYTES_HS256, 'TEST_SECRET')

    def test_known_insecure_default_rejected(self):
        """Known placeholder values must be rejected."""
        with pytest.raises(ConfigError, match='insecure default'):
            validate_secret_length(
                'CHANGE_THIS_IN_PRODUCTION_NOW',
                MIN_SECRET_BYTES_HS256,
                'SECRET_KEY'
            )

    def test_short_secret_rejected(self):
        """Secret below minimum bytes must be rejected with guidance."""
        with pytest.raises(ConfigError, match='bytes') as exc_info:
            validate_secret_length('short', MIN_SECRET_BYTES_HS256, 'JWT_SECRET_KEY')
        assert 'token_hex' in str(exc_info.value)  # Includes generation guidance

    def test_secure_secret_accepted(self):
        """A 32-byte+ secret should be accepted."""
        secure_secret = 'a' * 64  # Well above minimum
        # Should not raise
        validate_secret_length(secure_secret, MIN_SECRET_BYTES_HS256, 'TEST_SECRET')

    def test_utf8_multibyte_counted_correctly(self):
        """Multibyte UTF-8 characters are counted by byte, not character."""
        # '🔐' is 4 bytes in UTF-8
        emoji_secret = '🔐' * 8  # 32 bytes
        validate_secret_length(emoji_secret, MIN_SECRET_BYTES_HS256, 'TEST_SECRET')


class TestAPICredentialsValidation:

    def test_empty_credentials_rejected(self):
        """Empty API_CLIENTS must be rejected."""
        with pytest.raises(ConfigError, match='empty'):
            validate_api_credentials('')

    def test_malformed_format_rejected(self):
        """Credentials without ':' separator must be rejected."""
        with pytest.raises(ConfigError, match='invalid format'):
            validate_api_credentials('bad_format_no_colon')

    def test_missing_client_id_rejected(self):
        """Missing client_id in a credential must be rejected."""
        with pytest.raises(ConfigError, match='empty'):
            validate_api_credentials(':password')

    def test_missing_password_rejected(self):
        """Missing password in a credential must be rejected."""
        with pytest.raises(ConfigError, match='empty'):
            validate_api_credentials('client_id:')

    def test_multiple_credentials_parsed(self):
        """Multiple comma-separated credentials should be parsed correctly."""
        creds = validate_api_credentials('client1:pass1,client2:pass2')
        assert creds == {'client1': 'pass1', 'client2': 'pass2'}

    def test_insecure_default_password_rejected(self):
        """Known placeholder passwords must be rejected."""
        with pytest.raises(ConfigError, match='insecure default'):
            validate_api_credentials('sensor_gateway:replace-me')

    def test_whitespace_trimmed(self):
        """Whitespace around credentials should be trimmed."""
        creds = validate_api_credentials('  client1 : pass1 , client2 : pass2  ')
        assert creds == {'client1': 'pass1', 'client2': 'pass2'}


class TestCORSValidation:

    def test_empty_origins_defaults_to_localhost(self):
        """Empty ALLOWED_ORIGINS should default to localhost for development."""
        origins = validate_cors_origins('', 'development')
        assert 'http://localhost:8501' in origins

    def test_multiple_origins_parsed(self):
        """Multiple comma-separated origins should be parsed."""
        origins = validate_cors_origins('https://app1.com,https://app2.com', 'production')
        assert 'https://app1.com' in origins
        assert 'https://app2.com' in origins

    def test_production_rejects_wildcard_cors(self):
        """Production must reject wildcard CORS."""
        with pytest.raises(ConfigError, match='wildcard'):
            validate_cors_origins('*', 'production')
        
        with pytest.raises(ConfigError, match='wildcard'):
            validate_cors_origins('https://*.example.com', 'production')

    def test_production_rejects_http_non_localhost(self):
        """Production must reject insecure HTTP for non-localhost origins."""
        with pytest.raises(ConfigError, match='insecure HTTP'):
            validate_cors_origins('http://example.com', 'production')

    def test_production_allows_https(self):
        """Production should allow HTTPS origins."""
        origins = validate_cors_origins('https://secure.example.com', 'production')
        assert 'https://secure.example.com' in origins

    def test_development_allows_localhost_http(self):
        """Development should allow http://localhost."""
        origins = validate_cors_origins('http://localhost:8501', 'development')
        assert 'http://localhost:8501' in origins


class TestRedisValidation:

    def test_empty_redis_url_rejected(self):
        """Empty REDIS_URL must be rejected."""
        with pytest.raises(ConfigError, match='empty'):
            validate_redis_url('', 'production')

    def test_production_rejects_localhost_redis(self):
        """Production must reject localhost Redis."""
        with pytest.raises(ConfigError, match='localhost'):
            validate_redis_url('redis://localhost:6379/0', 'production')

    def test_development_allows_localhost_redis(self):
        """Development should allow localhost Redis."""
        url = validate_redis_url('redis://localhost:6379/0', 'development')
        assert url == 'redis://localhost:6379/0'

    def test_production_allows_remote_redis(self):
        """Production should allow remote Redis."""
        url = validate_redis_url('redis://redis.example.com:6379/0', 'production')
        assert url == 'redis://redis.example.com:6379/0'


class TestTwilioValidation:

    def test_disabled_twilio_returns_empty_config(self):
        """When disabled, Twilio config should be empty."""
        config = validate_twilio_config(False, 'sid', 'token', 'from', 'to')
        assert config['enabled'] is False
        assert config['sid'] == ''

    def test_enabled_missing_sid_rejected(self):
        """Enabled Twilio without SID must be rejected."""
        with pytest.raises(ConfigError, match='missing'):
            validate_twilio_config(True, '', 'token', 'from_phone', 'alert_phone')

    def test_enabled_missing_token_rejected(self):
        """Enabled Twilio without token must be rejected."""
        with pytest.raises(ConfigError, match='missing'):
            validate_twilio_config(True, 'sid', '', 'from_phone', 'alert_phone')

    def test_enabled_complete_config_accepted(self):
        """Enabled Twilio with all fields should be accepted."""
        config = validate_twilio_config(
            True,
            'REDACTED_TWILIO_SID',
            'auth_token_here',
            '+1234567890',
            '+0987654321'
        )
        assert config['enabled'] is True
        assert config['sid'] == 'REDACTED_TWILIO_SID'
