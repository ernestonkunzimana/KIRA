"""
KIRA - Core API (Service 2)
Flask application with JWT auth, rate limiting, and the full actuator logic.

Endpoints:
  POST /auth/token              - Obtain JWT access token
  GET  /api/v1/health           - SRE health check (no auth required)
  POST /api/v1/predict          - Run inference + alignment + actuation
  POST /api/v1/predict/batch    - Batch prediction for multiple towers
  GET  /api/v1/audit            - Query audit log
  GET  /api/v1/audit/stats      - Action statistics
  GET  /api/v1/tower/<id>/status - Current lockout + model status for a tower
  POST /api/v1/override         - Human manual override (always requires auth)
  GET  /api/v1/model/info       - Model version and feature metadata

Run for development:
  python app.py

Run for production (from backend/ directory):
  gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()" --log-level info
"""

import os
import sys
import logging
import time

# Atomic Path Resolution: Ensures 'backend' and 'core' are findable regardless of CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Dynamic Log Path (Handles both local and Docker environments)
# Prefer explicit environment override, otherwise keep logs under the app directory
# to avoid attempting to write to container root ("/logs") when running as non-root.
LOG_DIR = os.environ.get('LOG_DIR') or os.path.join(BASE_DIR, 'logs')
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    # Best-effort: fall back to a writable temp dir if creation fails
    LOG_DIR = os.environ.get('LOG_DIR') or '/tmp/kira_logs'
    os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'system_audit.log')

from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string
import hashlib
import json as _json
from flask_jwt_extended import JWTManager, get_jwt_identity
from flask_caching import Cache
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

from config import get_config
from config_validator import validate_production_config, log_configuration_mode
from core.inference import EnsembleInferenceEngine, FallbackInferenceEngine
from core.alignment_guard import AlignmentGuard
from core.actuator import Actuator
from api.auth import register_auth_routes, require_auth, add_register_endpoint, jwt as jwt_manager
from health_check import check_liveness, check_readiness, explain_health_status

# Module-level cache so route decorators can access it
cache = Cache()
# Module-level compressor for gzip responses
compress = Compress()

# ---- Logging setup ----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger('kira.api')

# ---- Application state (loaded once at startup) ----
_engine_iot: EnsembleInferenceEngine = None
_engine_grid: EnsembleInferenceEngine = None
_engine_gen: EnsembleInferenceEngine = None
_alignment_guard: AlignmentGuard = None
_actuator: Actuator = None
_startup_time = None
_startup_errors = []
_mode = "PRODUCTION"  # Can be "DEGRADED" if models fail to load


def create_app() -> Flask:
    """Application factory. Called by gunicorn and tests."""
    global _engine_iot, _engine_grid, _engine_gen, _alignment_guard, _actuator, _startup_time, _startup_errors

    # ---- Configuration validation (fail-fast security checks) ----
    log_configuration_mode()
    try:
        is_prod, errors = validate_production_config()
        if errors and is_prod:
            # In production, any validation error is fatal
            for err in errors:
                logger.critical(f'CONFIG ERROR: {err}')
            sys.exit(1)
    except Exception as e:
        logger.critical(f'Config validation failed: {e}')
        sys.exit(1)

    # Reset mutable startup state on each app-factory invocation.
    # This prevents duplicate stale errors when tests create multiple app instances.
    _startup_errors = []

    app = Flask(__name__)
    cfg = get_config()
    app.config.from_object(cfg)

    # Determine environment early (used by cache and limiter setup)
    flask_env = os.environ.get('FLASK_ENV', 'development')

    # ---- Extensions ----
    jwt_manager.init_app(app)

    # ---- Cache (Redis if available, fallback to in-memory) ----
    # Configure cache backend based on environment and availability
    if flask_env == 'production' and cfg.REDIS_URL:
        app.config['CACHE_TYPE'] = 'RedisCache'
        app.config['CACHE_REDIS_URL'] = cfg.REDIS_URL
    else:
        app.config['CACHE_TYPE'] = 'SimpleCache'
    cache.init_app(app)
    # Initialize response compression
    compress.init_app(app)
    
    # Rate limiter: use Redis in production, memory in development/tests
    limiter_storage = cfg.REDIS_URL if flask_env == 'production' else 'memory://'
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[cfg.RATELIMIT_DEFAULT],
        storage_uri=limiter_storage,
    )
    CORS(app, resources={r"/api/*": {"origins": cfg.ALLOWED_ORIGINS}, r"/auth/*": {"origins": cfg.ALLOWED_ORIGINS}})

    # Security response headers
    @app.after_request
    def set_security_headers(response):
        # HSTS only when behind TLS; safe default header if TLS is present
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        response.headers.setdefault('Permissions-Policy', 'geolocation=()')
        # Content Security Policy — minimal default; adapt for templates/assets as needed
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'")
        return response

    # ---- Load ML artefacts with NASA-style Fail-Safe ----
    _startup_time = time.time()
    
    # IoT Engine
    try:
        _engine_iot = EnsembleInferenceEngine(domain='iot')
    except Exception as e:
        logger.error(f'FAIL-SAFE: IoT Model load failed. Falling back to rule-based: {e}')
        _engine_iot = FallbackInferenceEngine(domain='iot')
        _startup_errors.append(f'iot: {e}')

    # Grid Engine
    try:
        _engine_grid = EnsembleInferenceEngine(domain='grid')
    except Exception as e:
        logger.error(f'FAIL-SAFE: Grid Model load failed. Falling back to rule-based: {e}')
        _engine_grid = FallbackInferenceEngine(domain='grid')
        _startup_errors.append(f'grid: {e}')

    # Generator Engine
    try:
        _engine_gen = EnsembleInferenceEngine(domain='gen')
    except Exception as e:
        logger.error(f'FAIL-SAFE: Gen Model load failed. Falling back to rule-based: {e}')
        _engine_gen = FallbackInferenceEngine(domain='gen')
        _startup_errors.append(f'gen: {e}')

    # ---- Instantiate core components ----
    _alignment_guard = AlignmentGuard(
        autonomous_threshold=cfg.AUTONOMOUS_ACTION_THRESHOLD,
        alert_threshold=cfg.ALERT_THRESHOLD,
        lockout_seconds=cfg.ACTUATOR_LOCKOUT_SECONDS,
        redis_url=cfg.REDIS_URL,
    )

    twilio_cfg = {
        'enabled': cfg.TWILIO_ENABLED,
        'sid': cfg.TWILIO_SID,
        'token': cfg.TWILIO_TOKEN,
        'from': cfg.TWILIO_FROM,
        'to': cfg.ALERT_PHONE,
    }
    _actuator = Actuator(
        audit_db_path=cfg.AUDIT_DB_PATH,
        simulation_mode=True,  # Set False when hardware is connected
        twilio_config=twilio_cfg,
    )

    # ---- Register routes ----
    register_auth_routes(app)
    add_register_endpoint(app)
    _register_routes(app, limiter)

    logger.info('KIRA Service 2 (Core API) started successfully')
    return app


def _register_routes(app: Flask, limiter: Limiter):

    # ------------------------------------------------------------------ #
    #  GET /api/v1/health                                                  #
    #  SRE health check - Lens/Docker will poll this                       #
    #  NOT rate-limited (orchestration requirement)                        #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/health', methods=['GET'])
    @limiter.exempt  # CRITICAL: Health checks must never be rate-limited
    @cache.cached(timeout=5)
    def health():
        """
        Production health check with liveness/readiness semantics.
        
        Used by orchestration platforms (Kubernetes, Docker Compose) to:
          - READINESS: Route traffic only to healthy instances (HTTP 200)
          - LIVENESS: Detect dead processes (HTTP non-200)
          - DEPENDENCY: Fail fast if critical services (Redis, DB) are down
        
        Returns:
          HTTP 200: Service is ready and healthy
          HTTP 503: Service is degraded (fallbacks active) but operational
          HTTP 424: Service has unrecoverable failures (e.g., Redis down)
        """
        result = check_readiness(
            engine_iot=_engine_iot,
            engine_grid=_engine_grid,
            engine_gen=_engine_gen,
            alignment_guard=_alignment_guard,
            actuator=_actuator,
            startup_errors=_startup_errors,
            startup_time=_startup_time,
        )

        http_status = result.http_status_code()

        # Log health status (useful for monitoring and debugging)
        if http_status != 200:
            logger.warning(explain_health_status(result))
        else:
            logger.debug(f"Health check: {result.status}")

        return jsonify(result.to_dict()), http_status

    # ------------------------------------------------------------------ #
    #  GET /docs                                                           #
    #  Minimal API Documentation                                           #
    # ------------------------------------------------------------------ #
    @app.route('/docs', methods=['GET'])
    def api_docs():
        # Serve an interactive Swagger UI that consumes the OpenAPI JSON at /openapi.json
        swagger_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset='utf-8' />
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            <title>KIRA API - Swagger UI</title>
            <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@4/swagger-ui.css" />
            <style>body { margin:0; background:#f7fafc; }</style>
        </head>
        <body>
            <header style="padding:20px; background:#fff; border-bottom:1px solid #e6edf3;">
                <h1 style="margin:0; font-family:Segoe UI, Roboto, Arial; color:#2c3e50;">KIRA Core API Documentation</h1>
                <p style="margin:6px 0 0;color:#586069;">Interactive API reference (Swagger UI)</p>
            </header>
            <div id="swaggerui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
            <script>
            window.onload = function() {
                const ui = SwaggerUIBundle({
                    url: '/openapi.json',
                    dom_id: '#swaggerui',
                    presets: [SwaggerUIBundle.presets.apis],
                    layout: 'BaseLayout'
                });
            };
            </script>
        </body>
        </html>
        """
        return render_template_string(swagger_html)


    @app.route('/openapi.json', methods=['GET'])
    def openapi_spec():
        """Return a minimal OpenAPI spec describing core endpoints."""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "KIRA Core API",
                "version": "v1",
                "description": "OpenAPI spec for KIRA core endpoints."
            },
            "servers": [{"url": f"http://{request.host}"}],
            "paths": {
                "/auth/token": {
                    "post": {
                        "summary": "Obtain access token",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "client_id": {"type": "string"},
                                            "password": {"type": "string"}
                                        },
                                        "required": ["client_id", "password"]
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {"description": "Access token returned"},
                            "400": {"description": "Invalid request"}
                        }
                    }
                },
                "/api/v1/health": {
                    "get": {"summary": "Health check","responses": {"200": {"description": "health status"}}}
                },
                "/api/v1/predict/iot": {
                    "post": {
                        "summary": "IoT prediction",
                        "security": [{"bearerAuth": []}],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "tower_id": {"type": "string"},
                                            "district": {"type": "string"},
                                            "sensor_data": {"type": "object"}
                                        },
                                        "required": ["tower_id", "district", "sensor_data"]
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "prediction result"}, "401": {"description": "unauthorized"}}
                    }
                },
                "/api/v1/predict/grid": {
                    "post": {"summary": "Grid prediction","security": [{"bearerAuth": []}],"responses": {"200": {"description": "prediction result"}}}
                },
                "/api/v1/predict/generator": {
                    "post": {"summary": "Generator prediction","security": [{"bearerAuth": []}],"responses": {"200": {"description": "prediction result"}}}
                }
            },
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
                }
            }
        }
        return jsonify(spec)

    # ------------------------------------------------------------------ #
    #  POST /api/v1/predict                                                #
    #  Main inference + alignment + actuation endpoint                     #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/predict/iot', methods=['POST'])
    @require_auth
    @limiter.limit(app.config.get('RATELIMIT_PREDICT', '60 per minute'))
    def predict_iot():
        if _engine_iot is None:
            return jsonify({'error': 'IoT Model not loaded. Service is degraded.'}), 503
        return _handle_predict_request(_engine_iot, 'IOT')

    @app.route('/api/v1/predict/grid', methods=['POST'])
    @require_auth
    @limiter.limit(app.config.get('RATELIMIT_PREDICT', '60 per minute'))
    def predict_grid():
        if _engine_grid is None:
            return jsonify({'error': 'Grid Model not loaded.'}), 503
        return _handle_predict_request(_engine_grid, 'GRID')

    @app.route('/api/v1/predict/generator', methods=['POST'])
    @require_auth
    @limiter.limit(app.config.get('RATELIMIT_PREDICT', '60 per minute'))
    def predict_generator():
        if _engine_gen is None:
            return jsonify({'error': 'Generator Model not loaded.'}), 503
        return _handle_predict_request(_engine_gen, 'GENERATOR')

    def _handle_predict_request(engine, subsystem_name):
        """Helper to handle the prediction logic for any subsystem."""
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        tower_id = data.get('tower_id', '').strip()
        district = data.get('district', '').strip()
        sensor_data = data.get('sensor_data')

        # Input validation
        if not tower_id:
            return jsonify({'error': 'tower_id is required'}), 400
        if not district:
            return jsonify({'error': 'district is required'}), 400
        if not sensor_data or not isinstance(sensor_data, dict):
            return jsonify({'error': 'sensor_data dict is required'}), 400

        client_id = get_jwt_identity()

        # Short-term cache responses for identical requests to improve latency
        try:
            cache_key_raw = f"predict:{subsystem_name}:{tower_id}:{_json.dumps(sensor_data, sort_keys=True)}"
            cache_key = hashlib.sha256(cache_key_raw.encode('utf-8')).hexdigest()
            cached = cache.get(cache_key)
            if cached is not None:
                return jsonify(cached), 200
        except Exception:
            # Cache key generation should never fail the request
            cache_key = None

        # 1. Inference
        try:
            inference_result = engine.predict(
                sensor_data=sensor_data, compute_shap=True)
        except ValueError as e:
            logger.warning(
                f'PREDICT REJECTED: tower={tower_id} | reason={e} | client={client_id}')
            return jsonify({
                'error': 'Invalid sensor data',
                'detail': str(e),
                'tower_id': tower_id,
            }), 422

        predicted_class = inference_result['predicted_class']
        confidence = inference_result['confidence']
        action_name = inference_result['action_name']

        # 2. Alignment guard evaluation
        verdict = _alignment_guard.evaluate(
            predicted_class=predicted_class,
            action_name=action_name,
            confidence=confidence,
            tower_id=tower_id,
        )

        # 3. Actuate if approved
        action_result = None
        if verdict.should_execute:
            action_result = _actuator.execute(
                action_class=predicted_class,
                action_name=verdict.action_name,
                tower_id=tower_id,
                district=district,
                confidence=confidence,
                shap_explanation=inference_result.get('shap_explanation'),
                triggered_by='AUTONOMOUS',
            )
        elif verdict.decision == 'APPROVED_ALERT_HUMAN':
            # Use the PUBLIC dispatch_alert interface so the alert is written to the audit log
            alert_msg = (
                f'[KIRA ALERT] Tower {tower_id} ({district}): '
                f'{verdict.action_name} recommended (conf={confidence:.4f}). '
                f'Human confirmation required. {verdict.reasoning}'
            )
            action_result = _actuator.dispatch_alert(
                message=alert_msg,
                tower_id=tower_id,
                district=district,
                confidence=confidence,
                shap_explanation=inference_result.get('shap_explanation'),
                triggered_by='ALERT_ONLY',
            )

        # 4. Build response
        response = {
            'tower_id': tower_id,
            'district': district,
            'prediction': inference_result,
            'alignment_verdict': verdict.to_dict(),
            'action_executed': action_result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'client_id': client_id,
            'subsystem': subsystem_name,
        }

        logger.info(
            f'PREDICT [{subsystem_name}] | tower={tower_id} | action={verdict.action_name} '
            f'| conf={confidence:.4f} | decision={verdict.decision}'
        )
        # Cache the response for a short TTL (5 seconds) for identical requests
        try:
            if cache_key:
                cache.set(cache_key, response, timeout=5)
        except Exception:
            pass
        return jsonify(response), 200



    # ------------------------------------------------------------------ #
    #  POST /api/v1/override                                               #
    #  Human manual override - executes action regardless of confidence    #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/override', methods=['POST'])
    @require_auth
    @limiter.limit('10 per minute')
    def manual_override():
        """
        Human engineers call this to force an action.
        Body: {"tower_id": "...", "district": "...", "action_class": 1, "reason": "..."}
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'JSON body required'}), 400

        tower_id = data.get('tower_id', '').strip()
        district = data.get('district', '').strip()
        action_class = data.get('action_class')
        reason = data.get('reason', 'Human override - no reason provided')
        client_id = get_jwt_identity()

        if not tower_id or not district:
            return jsonify({'error': 'tower_id and district required'}), 400
        if action_class is None or action_class not in range(4):
            return jsonify({'error': 'action_class must be 0, 1, 2, or 3'}), 400

        logger.warning(
            f'HUMAN OVERRIDE: action={action_class} | tower={tower_id} '
            f'| operator={client_id} | reason={reason}'
        )

        action_result = _actuator.execute(
            action_class=int(action_class),
            action_name=f'human_override_{action_class}',
            tower_id=tower_id,
            district=district,
            confidence=1.0,  # Human confirmed = maximum confidence
            shap_explanation={'human_readable': f'Manual override by {client_id}: {reason}'},
            triggered_by=f'HUMAN_OVERRIDE:{client_id}',
        )

        return jsonify({
            'status': 'override_executed',
            'operator': client_id,
            'reason': reason,
            'action_result': action_result,
        }), 200

    # ------------------------------------------------------------------ #
    #  GET /api/v1/audit                                                   #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/audit', methods=['GET'])
    @require_auth
    def get_audit():
        """
        GET /api/v1/audit?limit=50&tower_id=Kacyiru-A&district=Gasabo
        Returns the audit log with optional filters.
        """
        limit_raw = request.args.get('limit', '100')
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return jsonify({'error': 'limit must be an integer'}), 400

        if limit < 1:
            return jsonify({'error': 'limit must be >= 1'}), 400
        limit = min(limit, 500)

        tower_id = request.args.get('tower_id')
        district = request.args.get('district')

        logs = _actuator.get_audit_log(
            limit=limit, tower_id=tower_id, district=district)

        return jsonify({
            'count': len(logs),
            'filters': {'tower_id': tower_id, 'district': district},
            'logs': logs,
        }), 200

    @app.route('/api/v1/audit/stats', methods=['GET'])
    @require_auth
    def get_audit_stats():
        return jsonify(_actuator.get_audit_stats()), 200

    # ------------------------------------------------------------------ #
    #  GET /api/v1/tower/<tower_id>/status                                 #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/tower/<tower_id>/status', methods=['GET'])
    @require_auth
    @cache.cached(timeout=30)
    def tower_status(tower_id: str):
        def _model_version(engine):
            if engine is None:
                return None
            if hasattr(engine, 'metadata') and isinstance(engine.metadata, dict):
                return engine.metadata.get('version')
            if hasattr(engine, 'get_model_info'):
                info = engine.get_model_info() or {}
                return info.get('version') or info.get('status')
            return None

        lockout = _alignment_guard.get_tower_lockout_status(tower_id)
        return jsonify({
            'tower_id': tower_id,
            'lockout': lockout,
            'models': {
                'iot': _model_version(_engine_iot),
                'grid': _model_version(_engine_grid),
                'gen': _model_version(_engine_gen),
            }
        }), 200

    # ------------------------------------------------------------------ #
    #  GET /api/v1/model/info                                              #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/model/info', methods=['GET'])
    @require_auth
    @cache.cached(timeout=30)
    def model_info():
        if _engine_iot is None or _engine_grid is None or _engine_gen is None:
            return jsonify({'error': 'Models not fully loaded'}), 503
        resp = jsonify({
            'iot': _engine_iot.get_model_info(),
            'grid': _engine_grid.get_model_info(),
            'gen': _engine_gen.get_model_info(),
        })
        # Allow clients to cache model info for short period
        resp.headers['Cache-Control'] = 'public, max-age=30'
        return resp, 200

    # ------------------------------------------------------------------ #
    #  GET /                                                              #
    #  Friendly root endpoint for browser/ops checks                      #
    # ------------------------------------------------------------------ #
    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            'service': 'KIRA Core API',
            'status': 'ok',
            'docs': '/docs',
            'health': '/api/v1/health',
        }), 200

    # ---- Error handlers ----
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Endpoint not found', 'path': request.path}), 404

    @app.errorhandler(429)
    def rate_limited(e):
        logger.warning(f'RATE LIMIT: ip={request.remote_addr} | path={request.path}')
        return jsonify({
            'error': 'Rate limit exceeded',
            'detail': 'Too many requests. Slow down sensor polling frequency.',
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f'INTERNAL ERROR: {e}')
        return jsonify({'error': 'Internal server error'}), 500


# ------------------------------------------------------------------ #
#  Utility                                                             #
# ------------------------------------------------------------------ #
def _action_to_status(action_class: int, confidence: float) -> str:
    """Map prediction to R/Y/G status for dashboard."""
    if action_class == 0:
        return 'green'
    if action_class in (1, 2) and confidence >= 0.85:
        return 'red' if action_class == 2 else 'yellow'
    return 'yellow'


# ---- Entry point ----
if __name__ == '__main__':
    env = os.environ.get('FLASK_ENV', 'development')
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f'Starting KIRA API in {env} mode on port {port}')
    app.run(host='0.0.0.0', port=port, debug=(env == 'development'))
