"""
Tests: Health Check Semantics
Verifies liveness/readiness distinction and proper orchestration semantics.

Run: pytest tests/test_health_check.py -v
"""

import pytest
import time
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from health_check import (
    check_liveness,
    check_readiness,
    HealthCheckResult,
    SEVERITY_HEALTHY,
    SEVERITY_DEGRADED,
    SEVERITY_CRITICAL,
)


class TestLivenessProbe:

    def test_liveness_always_succeeds(self):
        """Liveness probe should always succeed if process is running."""
        result = check_liveness()
        assert result.status == SEVERITY_HEALTHY
        assert result.http_status_code() == 200

    def test_liveness_has_minimal_dependencies(self):
        """Liveness probe should not depend on external services."""
        # Should succeed without any engines or services
        result = check_liveness()
        assert result is not None
        assert 'process' in result.components


class TestReadinessProbe:

    def test_readiness_healthy_all_components_ok(self):
        """Readiness should be healthy when all components are operational."""
        mock_engine = MagicMock()
        mock_engine.__class__.__name__ = 'EnsembleInferenceEngine'
        mock_guard = MagicMock()
        mock_guard.check_redis.return_value = True
        mock_actuator = MagicMock()
        mock_actuator.check_db.return_value = True

        result = check_readiness(
            engine_iot=mock_engine,
            engine_grid=mock_engine,
            engine_gen=mock_engine,
            alignment_guard=mock_guard,
            actuator=mock_actuator,
            startup_errors=[],
            startup_time=time.time(),
        )

        assert result.status == SEVERITY_HEALTHY
        assert result.http_status_code() == 200
        assert result.components['models'] == 'ok'
        assert result.components['redis'] == 'ok'
        assert result.components['database'] == 'ok'

    def test_readiness_degraded_fallback_active(self):
        """Readiness should degrade when fallback models are active."""
        mock_fallback = MagicMock()
        mock_fallback.__class__.__name__ = 'FallbackInferenceEngine'
        mock_guard = MagicMock()
        mock_guard.check_redis.return_value = True
        mock_actuator = MagicMock()
        mock_actuator.check_db.return_value = True

        result = check_readiness(
            engine_iot=mock_fallback,
            engine_grid=mock_fallback,
            engine_gen=mock_fallback,
            alignment_guard=mock_guard,
            actuator=mock_actuator,
            startup_errors=[],
            startup_time=time.time(),
        )

        assert result.status == SEVERITY_DEGRADED
        assert result.http_status_code() == 503
        assert result.components['models'] == 'degraded_fallback'

    def test_readiness_critical_redis_down(self):
        """Readiness should fail if Redis is unavailable."""
        mock_engine = MagicMock()
        mock_guard = MagicMock()
        mock_guard.check_redis.return_value = False  # Redis unavailable
        mock_actuator = MagicMock()
        mock_actuator.check_db.return_value = True

        result = check_readiness(
            engine_iot=mock_engine,
            engine_grid=mock_engine,
            engine_gen=mock_engine,
            alignment_guard=mock_guard,
            actuator=mock_actuator,
            startup_errors=[],
            startup_time=time.time(),
        )

        assert result.status == SEVERITY_CRITICAL
        assert result.http_status_code() == 424
        assert result.components['redis'] == 'failed'
        assert 'Redis unavailable' in ' '.join(result.errors)

    def test_readiness_critical_database_down(self):
        """Readiness should fail if audit database is unavailable."""
        mock_engine = MagicMock()
        mock_guard = MagicMock()
        mock_guard.check_redis.return_value = True
        mock_actuator = MagicMock()
        mock_actuator.check_db.return_value = False  # DB unavailable

        result = check_readiness(
            engine_iot=mock_engine,
            engine_grid=mock_engine,
            engine_gen=mock_engine,
            alignment_guard=mock_guard,
            actuator=mock_actuator,
            startup_errors=[],
            startup_time=time.time(),
        )

        assert result.status == SEVERITY_CRITICAL
        assert result.http_status_code() == 424
        assert result.components['database'] == 'failed'
        assert 'Audit database unavailable' in ' '.join(result.errors)

    def test_readiness_critical_engines_missing(self):
        """Readiness should fail if ML engines failed to load."""
        result = check_readiness(
            engine_iot=None,  # Missing
            engine_grid=None,  # Missing
            engine_gen=None,  # Missing
            alignment_guard=MagicMock(),
            actuator=MagicMock(),
            startup_errors=[],
            startup_time=time.time(),
        )

        assert result.status == SEVERITY_CRITICAL
        assert result.http_status_code() == 424
        assert result.components['models'] == 'failed'

    def test_readiness_tracks_uptime(self):
        """Readiness should calculate correct uptime."""
        past_time = time.time() - 100  # 100 seconds ago

        result = check_readiness(
            engine_iot=MagicMock(),
            engine_grid=MagicMock(),
            engine_gen=MagicMock(),
            alignment_guard=MagicMock(),
            actuator=MagicMock(),
            startup_errors=[],
            startup_time=past_time,
        )

        assert result.uptime_seconds >= 100


class TestHealthCheckResult:

    def test_http_status_code_mapping(self):
        """HTTP status codes should map correctly to health states."""
        healthy = HealthCheckResult(service_name='test', status=SEVERITY_HEALTHY)
        assert healthy.http_status_code() == 200

        degraded = HealthCheckResult(service_name='test', status=SEVERITY_DEGRADED)
        assert degraded.http_status_code() == 503

        critical = HealthCheckResult(service_name='test', status=SEVERITY_CRITICAL)
        assert critical.http_status_code() == 424

    def test_result_serialization(self):
        """HealthCheckResult should serialize to JSON-safe dict."""
        result = HealthCheckResult(
            service_name='test-service',
            status=SEVERITY_HEALTHY,
            uptime_seconds=42,
            components={'model': 'ok', 'redis': 'ok'},
            errors=[],
        )

        data = result.to_dict()
        assert data['service'] == 'test-service'
        assert data['status'] == SEVERITY_HEALTHY
        assert data['uptime_seconds'] == 42
        assert data['components'] == {'model': 'ok', 'redis': 'ok'}
        assert data['errors'] == []
        assert 'timestamp' in data


class TestOrchestratorIntegration:

    def test_kubernetes_liveness_probe_usage(self):
        """Kubernetes uses liveness to detect dead processes."""
        # Liveness should always succeed (process is alive)
        result = check_liveness()
        assert result.http_status_code() == 200

    def test_kubernetes_readiness_probe_usage(self):
        """Kubernetes uses readiness to prevent traffic to unhealthy instances."""
        mock_engine = MagicMock()
        mock_guard = MagicMock()
        mock_guard.check_redis.return_value = False  # Simulate Redis down

        result = check_readiness(
            engine_iot=mock_engine,
            engine_grid=mock_engine,
            engine_gen=mock_engine,
            alignment_guard=mock_guard,
            actuator=MagicMock(),
            startup_errors=[],
            startup_time=time.time(),
        )

        # Readiness should fail (don't route traffic)
        assert result.http_status_code() != 200

    def test_docker_health_semantics(self):
        """Docker Compose uses health checks to restart containers."""
        # Service is ready
        healthy_result = check_readiness(
            engine_iot=MagicMock(),
            engine_grid=MagicMock(),
            engine_gen=MagicMock(),
            alignment_guard=MagicMock(),
            actuator=MagicMock(),
            startup_errors=[],
            startup_time=time.time(),
        )
        assert healthy_result.http_status_code() == 200

        # Service has unrecoverable failure (no retry, restart)
        critical_result = check_readiness(
            engine_iot=None,
            engine_grid=None,
            engine_gen=None,
            alignment_guard=MagicMock(),
            actuator=MagicMock(),
            startup_errors=[],
            startup_time=time.time(),
        )
        assert critical_result.http_status_code() != 200
