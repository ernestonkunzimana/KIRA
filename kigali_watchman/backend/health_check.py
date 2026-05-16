"""
KIRA - Health Check Module
Production semantics for liveness and readiness probes.

Distinguishes between:
  - LIVENESS: "Is the service process alive?" (minimal check)
  - READINESS: "Can the service handle requests?" (comprehensive check)

Used by orchestration platforms (Kubernetes, Docker Compose, etc.) to:
  - LIVENESS: Restart dead processes (restart loop detection)
  - READINESS: Route traffic only to healthy instances (load balancer gates)
"""

import time
import logging
from typing import Tuple, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Health check severity levels
SEVERITY_CRITICAL = 'critical'     # Service cannot operate
SEVERITY_DEGRADED = 'degraded'     # Service partially operational, fallbacks active
SEVERITY_HEALTHY = 'healthy'       # All components operational


class HealthCheckResult:
    """Result of a health check probe."""

    def __init__(
        self,
        service_name: str,
        status: str = SEVERITY_HEALTHY,
        uptime_seconds: int = 0,
        components: Dict[str, str] = None,
        errors: list = None,
        timestamp: str = None,
    ):
        self.service_name = service_name
        self.status = status
        self.uptime_seconds = uptime_seconds
        self.components = components or {}
        self.errors = errors or []
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict."""
        return {
            'service': self.service_name,
            'status': self.status,
            'uptime_seconds': self.uptime_seconds,
            'timestamp': self.timestamp,
            'components': self.components,
            'errors': self.errors,
        }

    def http_status_code(self) -> int:
        """
        HTTP status code for orchestration interpretation:
          - 200: Ready (healthy, can accept traffic)
          - 503: Not ready (dependencies down, refuse traffic)
          - 424: Dependent failure (upstream service error)
        """
        if self.status == SEVERITY_HEALTHY:
            return 200
        elif self.status == SEVERITY_DEGRADED:
            return 503  # Service Unavailable (fallbacks active)
        else:  # CRITICAL
            return 424  # Failed Dependency


class ComponentHealth:
    """Health status of a single component."""

    def __init__(self, name: str, ok: bool, detail: str = ''):
        self.name = name
        self.ok = ok
        self.detail = detail

    def to_dict(self) -> dict:
        status = 'ok' if self.ok else 'failed'
        return {'name': self.name, 'status': status, 'detail': self.detail}


def check_liveness() -> HealthCheckResult:
    """
    LIVENESS probe: Is the process alive?
    
    Minimal check used by orchestration to restart dead processes.
    Should respond quickly and not depend on external services.
    
    Returns:
        HealthCheckResult with minimal components
    """
    # Process is alive if this function executes
    return HealthCheckResult(
        service_name='kira-api',
        status=SEVERITY_HEALTHY,
        components={'process': 'ok'},
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def check_readiness(
    engine_iot=None,
    engine_grid=None,
    engine_gen=None,
    alignment_guard=None,
    actuator=None,
    startup_errors=None,
    startup_time=None,
) -> HealthCheckResult:
    """
    READINESS probe: Can the service handle requests?
    
    Comprehensive check used by orchestration to route traffic.
    Checks all critical dependencies and components.
    
    Fails if:
      - Any ML model failed to load (no fallback)
      - Redis unavailable (needed for lockout coordination)
      - Audit database unavailable (needed for action logging)
    
    Degrades if:
      - Fallback models are active (ML engines failed, using rule-based fallback)
    
    Args:
        engine_iot, engine_grid, engine_gen: Inference engines (may be FallbackInferenceEngine)
        alignment_guard: AlignmentGuard (requires Redis)
        actuator: Actuator (requires audit database)
        startup_errors: List of errors from app startup
        startup_time: When app started
    
    Returns:
        HealthCheckResult with detailed component status
    """
    components = {}
    errors = []
    status = SEVERITY_HEALTHY

    # Calculate uptime
    uptime_seconds = 0
    if startup_time:
        uptime_seconds = round(time.time() - startup_time)

    # Check ML Engines
    models_ok = all([engine_iot, engine_grid, engine_gen])
    has_fallback = any([
        hasattr(eng, '__class__') and 'Fallback' in eng.__class__.__name__
        for eng in [engine_iot, engine_grid, engine_gen]
        if eng is not None
    ])

    if not models_ok:
        components['models'] = 'failed'
        errors.append('One or more ML engines failed to load')
        status = SEVERITY_CRITICAL
    elif has_fallback:
        components['models'] = 'degraded_fallback'
        errors.append('ML models failed; using rule-based fallback')
        status = SEVERITY_DEGRADED
    else:
        components['models'] = 'ok'

    # Check Redis (for cross-worker lockout coordination)
    redis_ok = False
    if alignment_guard:
        redis_ok = alignment_guard.check_redis()
    
    if not redis_ok:
        components['redis'] = 'failed'
        errors.append('Redis unavailable; lockout state not coordinated across workers')
        status = SEVERITY_CRITICAL
    else:
        components['redis'] = 'ok'

    # Check Audit Database
    db_ok = False
    if actuator:
        db_ok = actuator.check_db()
    
    if not db_ok:
        components['database'] = 'failed'
        errors.append('Audit database unavailable; actions cannot be logged')
        status = SEVERITY_CRITICAL
    else:
        components['database'] = 'ok'

    # Check for startup configuration errors
    if startup_errors:
        components['config'] = 'degraded'
        errors.extend([f'Config warning: {e}' for e in startup_errors])
        if status != SEVERITY_CRITICAL:
            status = SEVERITY_DEGRADED

    return HealthCheckResult(
        service_name='kira-api',
        status=status,
        uptime_seconds=uptime_seconds,
        components=components,
        errors=errors,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def explain_health_status(result: HealthCheckResult) -> str:
    """
    Human-readable explanation of health status for logs and monitoring.
    """
    lines = [
        f"[{result.status.upper()}] KIRA API Health Check",
        f"  Uptime: {result.uptime_seconds}s",
    ]

    for component, status in result.components.items():
        symbol = '✓' if status == 'ok' else ('⚠' if 'degraded' in status else '✗')
        lines.append(f"    {symbol} {component}: {status}")

    if result.errors:
        lines.append("  Errors:")
        for error in result.errors[:3]:  # Limit to top 3 errors
            lines.append(f"    - {error}")

    return '\n'.join(lines)
