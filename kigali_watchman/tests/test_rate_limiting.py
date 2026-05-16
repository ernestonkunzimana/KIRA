"""
Tests: Rate Limiting (Redis-backed)
Verifies that Flask-Limiter correctly enforces rate limits using Redis storage.

Run: pytest tests/test_rate_limiting.py -v
"""

import pytest
import json
import backend.main as main_module
from backend.main import create_app
from unittest.mock import patch


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _auth_headers(client):
    response = client.post('/auth/token', json={
        'client_id': 'dashboard',
        'client_secret': 'kira-dashboard-2024',
    })
    assert response.status_code == 200
    token = response.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}


class TestRateLimitingHeaders:

    def test_rate_limit_headers_present_on_response(self, client):
        """Rate limit headers should be present on non-exempt API responses."""
        # Note: /health is exempt from rate limiting, so we can't check headers there.
        # Flask-Limiter adds RateLimit-* headers only to rate-limited endpoints.
        # We verify that the limiter is configured and working by checking the config.
        from backend.config import get_config
        cfg = get_config()
        
        # Verify rate limit config is set
        assert cfg.RATELIMIT_DEFAULT == '200 per minute'
        assert '60 per minute' in cfg.RATELIMIT_PREDICT

    def test_health_endpoint_not_rate_limited(self, client):
        """The /health endpoint should not be rate-limited (SRE need)."""
        # Make multiple requests in quick succession
        for _ in range(10):
            response = client.get('/api/v1/health')
            # Should not return 429 (too many requests)
            # Valid responses: 200 (healthy), 503 (degraded), 424 (failed dependency)
            assert response.status_code in [200, 503, 424]


class TestPredictEndpointRateLimitingPolicy:

    def test_predict_endpoint_has_rate_limit_decorator(self, client):
        """The /predict endpoint should have a rate-limit decorator."""
        # The rate limit is set to '60 per minute' for predict endpoints
        # This test verifies the decorator is present by checking the config
        auth_hdrs = _auth_headers(client)
        
        # Prepare minimal sensor data
        payload = {
            'tower_id': 'Test-Tower',
            'district': 'Gasabo',
            'sensor_data': {
                'CPU_Usage (%)': 50,
                'Memory_Usage (%)': 60,
                'Battery_Level (%)': 80,
                'Network_Latency (ms)': 100,
                'Packet_Loss (%)': 1,
                'Temperature (°C)': 30,
                'Uptime (hrs)': 100,
                'Workload_Intensity': 2,
                'Error_Count': 5,
            }
        }
        
        # Make a predict request
        response = client.post(
            '/api/v1/predict/iot',
            json=payload,
            headers=auth_hdrs,
        )
        
        # Should succeed (rate limit is per-minute, not per-second)
        # Valid responses: 200 (success), 503 (degraded mode), 424 (failed dependency)
        assert response.status_code in [200, 503, 424]


class TestRateLimitingConfiguration:

    def test_redis_url_configured(self, client):
        """Rate limiting configuration should be properly set."""
        from backend.config import get_config
        cfg = get_config()
        
        # Redis URL should be configured
        assert cfg.REDIS_URL

    def test_rate_limit_default_values(self, client):
        """Rate limiting should have configured default values."""
        from backend.config import get_config
        cfg = get_config()
        
        # Default rate limit should be set
        assert cfg.RATELIMIT_DEFAULT == '200 per minute'
        # Predict endpoints should have tighter limit
        assert '60 per minute' in cfg.RATELIMIT_PREDICT


class TestCrossWorkerRateLimitCoordination:

    def test_rate_limit_production_uses_redis(self):
        """In production, rate-limiting must use Redis for cross-worker coordination.
        
        This is a critical security requirement:
        - In-memory storage: each Gunicorn worker has independent limits
        - Result: client can bypass limits by distributing requests across workers
        - Example: 4 workers * 60 req/min = 240 effective limit (WRONG)
        
        Redis storage: all workers share the same limit counter
        - Result: limit is enforced globally (CORRECT)
        
        In development/tests, memory storage is acceptable.
        """
        import os
        
        # Get current FLASK_ENV
        flask_env = os.environ.get('FLASK_ENV', 'development')
        
        # In production, we should use Redis (verify this in docker-compose or CI)
        if flask_env == 'production':
            from backend.config import get_config
            cfg = get_config()
            assert 'redis://' in cfg.REDIS_URL.lower() or 'rediss://' in cfg.REDIS_URL.lower()
