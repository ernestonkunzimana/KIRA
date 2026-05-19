import time
print("[SYSTEM INFO] IoT Sensor Fleet initialized and monitoring telemetry...")
while True:
    time.sleep(10)


import json
import time
import random
import ssl
import paho.mqtt.client as mqtt

# Configuration variables mirroring Docker Compose environment
BROKER = "mqtt-broker"
PORT = 8883
TOPIC = "factory/edge/telemetry"

def generate_telemetry_payload():
    """Generates continuous stream data mimicking an industrial sensor node."""
    return {
        "timestamp": time.time(),
        "node_id": "vibration_sensor_01",
        "metrics": {
            "vibration_hz": round(random.uniform(45.0, 55.0), 2),
            "temperature_c": round(random.uniform(22.0, 26.0), 2),
            "link_quality_qos": round(random.uniform(94.0, 99.9), 1)
        }
    }

# Initialize MQTT Client with a clean v3.1.1 protocol session
client = mqtt.Client(client_id="trusted-edge-client", protocol=mqtt.MQTTv311)

# SENIOR ENGINEERING ARCHITECTURE: Apply Mutual TLS (mTLS) parameters
client.tls_set(
    ca_certs="/app/certs/ca.crt",
    certfile="/app/certs/client.crt",
    keyfile="/app/certs/client.key",
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_2
)

# Bypass strict server hostname checking for local Docker bridge networks
client.tls_insecure_set(True)

print(f"[SENSOR INFRA] Attempting encrypted connection to mTLS Broker at {BROKER}:{PORT}...")
try:
    client.connect(BROKER, PORT, keepalive=60)
except Exception as e:
    print(f"[FATAL ERROR] Cryptographic connection handshake failed: {e}")
    exit(1)

# Enter the execution loop streaming telemetry every 2 seconds
client.loop_start()
try:
    while True:
        payload = generate_telemetry_payload()
        serialized_data = json.dumps(payload)
        
        # Publish payload with Quality of Service level 1 (Guaranteed delivery)
        info = client.publish(TOPIC, serialized_data, qos=1)
        info.wait_for_publish()
        
        print(f"[STREAM SUCCESS] Packet delivered -> {serialized_data}")
        time.sleep(2)
except KeyboardInterrupt:
    print("[SYSTEM STOP] Orderly shutdown triggered by operator.")
finally:
    client.loop_stop()
    client.disconnect()

@@
"""
Enterprise IoT Sensor Fleet - Trusted Data Source
==================================================
Simulates industrial IoT sensor telemetry with proper mTLS security,
structured logging, and graceful error handling.

Author: Ernest Nkunzimana (Zentra Ltd)
License: MIT
"""

import json
import time
import random
import ssl
import os
import signal
import sys
import logging
import paho.mqtt.client as mqtt
from datetime import datetime

try:
    from enterprise_audit_logger import get_audit_logger, EventSeverity, UserRole
except ImportError:
    get_audit_logger = None

# ============================================================================
# Configuration (from environment variables)
# ============================================================================
BROKER = os.getenv("MQTT_BROKER", "mqtt-broker")
PORT = int(os.getenv("MQTT_PORT", "8883"))
TOPIC = os.getenv("MQTT_TOPIC", "factory/edge/telemetry")

# TLS Configuration
CA_CERT = os.getenv("MQTT_CA_CERT", "/app/certs/ca.crt")
CLIENT_CERT = os.getenv("MQTT_CLIENT_CERT", "/app/certs/client.crt")
CLIENT_KEY = os.getenv("MQTT_CLIENT_KEY", "/app/certs/client.key")
TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "false").lower() == "true"

# Publishing parameters
PUBLISH_INTERVAL = int(os.getenv("SENSOR_PUBLISH_INTERVAL", "2"))
MAX_RECONNECT_ATTEMPTS = 10

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [SENSOR] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Get enterprise audit logger if available
audit_logger = get_audit_logger() if get_audit_logger else None

# ============================================================================
# Global State
# ============================================================================
client = None
reconnect_count = 0
running = True


def signal_handler(sig, frame):
    """Graceful shutdown on SIGTERM/SIGINT."""
    global running
    logger.warning("Shutdown signal received (SIGTERM/SIGINT)")
    running = False
    if client:
        client.disconnect()
    sys.exit(0)


def generate_telemetry_payload() -> dict:
    """Generate synthetic IoT sensor telemetry (normal baseline)."""
    return {
        "timestamp": time.time(),
        "node_id": "vibration_sensor_01",
        "metrics": {
            "vibration_hz": round(random.uniform(45.0, 55.0), 2),
            "temperature_c": round(random.uniform(22.0, 26.0), 2),
            "link_quality_qos": round(random.uniform(94.0, 99.9), 1)
        }
    }


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback."""
    global reconnect_count
    if rc == 0:
        logger.info(f"✅ Connected to MQTT broker {BROKER}:{PORT}")
        reconnect_count = 0
        
        # Log successful connection
        if audit_logger:
            audit_logger.log_event(
                event_type="CONNECTION_ESTABLISHED",
                severity=EventSeverity.INFO,
                user_id="iot-sensor-fleet",
                user_role=UserRole.OPERATOR,
                description=f"Sensor fleet connected to MQTT broker",
                metadata={
                    "broker": BROKER,
                    "port": PORT,
                    "client_id": "trusted-edge-client",
                },
            )
    else:
        logger.error(f"❌ Connection failed with code {rc}")
        if audit_logger:
            audit_logger.log_event(
                event_type="CONNECTION_FAILED",
                severity=EventSeverity.WARNING,
                user_id="iot-sensor-fleet",
                user_role=UserRole.OPERATOR,
                description=f"MQTT connection failed (code {rc})",
                metadata={"error_code": rc},
            )


def on_disconnect(client, userdata, rc):
    """MQTT disconnection callback."""
    if rc != 0:
        logger.warning(f"Unexpected disconnection (code {rc}), attempting to reconnect...")
    else:
        logger.info("Gracefully disconnected from MQTT broker")


def on_publish(client, userdata, mid):
    """MQTT publish acknowledgment callback."""
    logger.debug(f"Message {mid} published successfully")


def setup_mqtt_client() -> mqtt.Client:
    """Initialize and configure MQTT client with mTLS security."""
    logger.info("Initializing MQTT client with mTLS security...")
    
    mqtt_client = mqtt.Client(
        client_id="trusted-edge-client",
        protocol=mqtt.MQTTv311
    )
    
    # Set callbacks
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_publish = on_publish
    
    # ====================================================================
    # SECURITY FIX: Proper TLS/mTLS Configuration (PRODUCTION)
    # ====================================================================
    try:
        mqtt_client.tls_set(
            ca_certs=CA_CERT,
            certfile=CLIENT_CERT,
            keyfile=CLIENT_KEY,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_3,  # Use TLS 1.3 for enhanced security
            ciphers=None  # Use system defaults (no weak ciphers)
        )
        
        # WARNING: Only disable hostname verification for local testing
        # PRODUCTION: Remove this line and ensure cert CN matches broker hostname
        if TLS_INSECURE:
            logger.warning("⚠️  TLS_INSECURE=true (DEVELOPMENT ONLY)")
            mqtt_client.tls_insecure_set(True)
        else:
            mqtt_client.tls_insecure_set(False)
            logger.info("✅ Hostname verification enabled (production-ready)")
        
        logger.info(f"✅ TLS configured: CA={CA_CERT}, Cert={CLIENT_CERT}")
    except Exception as e:
        logger.error(f"❌ TLS configuration failed: {e}")
        raise
    
    return mqtt_client


def connect_to_broker(mqtt_client: mqtt.Client) -> bool:
    """Attempt connection with exponential backoff retry."""
    global reconnect_count
    
    for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
        try:
            logger.info(f"Connecting to {BROKER}:{PORT} (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...")
            mqtt_client.connect(BROKER, PORT, keepalive=60)
            return True
        except Exception as e:
            reconnect_count += 1
            backoff = min(2 ** attempt, 30)  # Exponential backoff, max 30 seconds
            logger.warning(f"Connection attempt {attempt} failed: {e}. Retrying in {backoff}s...")
            time.sleep(backoff)
    
    logger.error(f"❌ Failed to connect after {MAX_RECONNECT_ATTEMPTS} attempts")
    return False


def main():
    """Main sensor fleet loop."""
    global client, running
    
    logger.info("=" * 60)
    logger.info("KIRA: IoT Sensor Fleet (Trusted Node)")
    logger.info("=" * 60)
    logger.info(f"Broker: {BROKER}:{PORT}")
    logger.info(f"Topic: {TOPIC}")
    logger.info(f"Publish interval: {PUBLISH_INTERVAL}s")
    logger.info(f"TLS Insecure mode: {TLS_INSECURE}")
    logger.info("=" * 60)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup MQTT client
        client = setup_mqtt_client()
        
        # Connect to broker
        if not connect_to_broker(client):
            logger.critical("Failed to establish connection to MQTT broker")
            sys.exit(1)
        
        # Start background event loop
        client.loop_start()
        
        # Main telemetry loop
        logger.info("Starting telemetry stream...")
        message_count = 0
        
        while running:
            try:
                payload = generate_telemetry_payload()
                serialized = json.dumps(payload)
                
                # Publish with QoS 1 (at-least-once delivery)
                msg_info = client.publish(TOPIC, serialized, qos=1)
                msg_info.wait_for_publish(timeout=1.0)
                
                message_count += 1
                logger.debug(f"[PUBLISH] Message {message_count}: {serialized}")
                
                time.sleep(PUBLISH_INTERVAL)
            except Exception as e:
                logger.error(f"Error publishing message: {e}")
                if audit_logger:
                    audit_logger.log_event(
                        event_type="PUBLISH_ERROR",
                        severity=EventSeverity.WARNING,
                        user_id="iot-sensor-fleet",
                        user_role=UserRole.OPERATOR,
                        description=f"Failed to publish telemetry: {str(e)}",
                    )
        
    except KeyboardInterrupt:
        logger.info("Shutdown initiated (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Graceful shutdown
        logger.info("Shutting down gracefully...")
        if client:
            client.loop_stop()
            client.disconnect()
            time.sleep(1)  # Allow time for disconnect message
        logger.info("Sensor fleet stopped")
        
        if audit_logger:
            audit_logger.log_event(
                event_type="SYSTEM_SHUTDOWN",
                severity=EventSeverity.INFO,
                user_id="iot-sensor-fleet",
                user_role=UserRole.OPERATOR,
                description="Sensor fleet shut down gracefully",
                metadata={"messages_published": message_count},
            )


if __name__ == "__main__":
    main()
