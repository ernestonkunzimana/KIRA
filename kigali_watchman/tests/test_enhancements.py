import pytest
import json
import backend.main as main_module
from backend.main import create_app


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


def test_health_extended(client):
    """Verify that the health check includes component status."""
    response = client.get('/api/v1/health')
    # Health endpoint may return 200 (healthy), 503 (degraded), or 424 (dependency failure)
    assert response.status_code in [200, 503, 424]
    data = json.loads(response.data)

    assert 'models' in data['components']
    assert 'timestamp' in data


def test_cors_headers(client):
    """Verify that CORS headers are present."""
    response = client.options('/api/v1/health', headers={
        'Origin': 'http://localhost:8501',
        'Access-Control-Request-Method': 'GET'
    })
    assert response.status_code == 200
    assert response.headers.get('Access-Control-Allow-Origin') == 'http://localhost:8501'


def test_docs_endpoint(client):
    """Verify that the documentation endpoint is accessible."""
    response = client.get('/docs')
    assert response.status_code == 200
    assert b'KIRA Core API Documentation' in response.data


def test_audit_limit_validation_returns_400(client):
    """Non-numeric audit limit should be rejected with a clear client error."""
    response = client.get('/api/v1/audit?limit=abc', headers=_auth_headers(client))
    assert response.status_code == 400
    assert 'limit must be an integer' in response.get_json()['error']


def test_tower_status_handles_engines_without_metadata(client):
    """Tower status must not crash when fallback engines expose get_model_info only."""
    class DummyEngine:
        def __init__(self, version):
            self._version = version

        def get_model_info(self):
            return {'version': self._version, 'status': 'DEGRADED_FAIL_SAFE'}

    old_iot, old_grid, old_gen = main_module._engine_iot, main_module._engine_grid, main_module._engine_gen
    try:
        main_module._engine_iot = DummyEngine('FALLBACK_IOT')
        main_module._engine_grid = DummyEngine('FALLBACK_GRID')
        main_module._engine_gen = DummyEngine('FALLBACK_GEN')

        response = client.get('/api/v1/tower/Gasabo-A/status', headers=_auth_headers(client))
        assert response.status_code == 200
        data = response.get_json()
        assert data['models']['iot'] == 'FALLBACK_IOT'
        assert data['models']['grid'] == 'FALLBACK_GRID'
        assert data['models']['gen'] == 'FALLBACK_GEN'
    finally:
        main_module._engine_iot, main_module._engine_grid, main_module._engine_gen = old_iot, old_grid, old_gen


def test_create_app_resets_startup_errors():
    """Repeated app factory calls should not retain stale startup errors."""
    main_module._startup_errors = ['stale-error']
    create_app()
    assert 'stale-error' not in main_module._startup_errors
