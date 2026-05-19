import json
import time
import ssl
import paho.mqtt.client as mqtt

BROKER = "mqtt-broker"
PORT = 8883
TOPIC = "factory/edge/telemetry"

client = mqtt.Client(client_id="compromised-edge-client", protocol=mqtt.MQTTv311)

client.tls_set(
    ca_certs="/app/certs/ca.crt",
    certfile="/app/certs/client.crt",
    keyfile="/app/certs/client.key",
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(True)

print("[OFFENSE - ATTACKER] Awaiting target network baseline setup (Sleeping 70 seconds)...")
time.sleep(70)  # Allows the defensive AI agent to comfortably train its model first

print(f"[OFFENSE - ATTACKER] Connecting to target network broker at {BROKER}...")
client.connect(BROKER, PORT, keepalive=60)

try:
    # ──► OPERATION 1: BRUTE FORCE DATA TAMPERING
    print("\n💥 [OFFENSE] Launching Attack Vector 1: Industrial Over-vibration Exploitation...")
    for _ in range(5):
        payload = {
            "timestamp": time.time(),
            "node_id": "vibration_sensor_01",
            "metrics": {
                "vibration_hz": 185.40,  # Extreme anomalies
                "temperature_c": 92.10,   # High spike
                "link_quality_qos": 12.4  # Drastic signal drop
            }
        }
        client.publish(TOPIC, json.dumps(payload), qos=1)
        time.sleep(3)

    # ──► OPERATION 2: STEALH / RECONNAISSANCE DRIFT
    print("\n🥷 [OFFENSE] Launching Attack Vector 2: Stealthy Thermal Drift (Evading Basic Thresholds)...")
    for step in range(5):
"""
Enterprise Attack Simulator - Security Testing Module
=======================================================
Simulates industrial control system attacks for validating anomaly detection.

Attack Vectors:
1. Over-vibration exploitation (threshold bypass)
2. Stealthy thermal drift (evading basic thresholds)
3. Link quality degradation (signal tampering)

Author: Ernest Nkunzimana (Zentra Ltd)
License: MIT
"""

import os
import sys
import signal
import logging
from enum import Enum

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

# Attack simulation parameters
BASELINE_DELAY = int(os.getenv("ATTACK_BASELINE_DELAY", "70"))
ATTACK_INTERVAL = int(os.getenv("ATTACK_INTERVAL", "3"))

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [ATTACK] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Get enterprise audit logger if available
audit_logger = get_audit_logger() if get_audit_logger else None

# ============================================================================
# Global State
# ============================================================================
client = None
running = True


class AttackVector(Enum):
    """Enumeration of attack types for logging."""
    OVER_VIBRATION = "OVER_VIBRATION"
    THERMAL_DRIFT = "THERMAL_DRIFT"
    LINK_DEGRADATION = "LINK_DEGRADATION"


def signal_handler(sig, frame):
    """Graceful shutdown on SIGTERM/SIGINT."""
    global running
    logger.warning("Shutdown signal received")
    running = False
    if client:
        client.disconnect()
    sys.exit(0)


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback."""
    if rc == 0:
        logger.info(f"✅ Attack simulator connected to {BROKER}:{PORT}")
        if audit_logger:
            audit_logger.log_event(
                event_type="ATTACK_MODULE_STARTED",
                severity=EventSeverity.INFO,
                user_id="attack-simulator",
                user_role=UserRole.ADMIN,
                description="Attack simulator connected for security testing",
                metadata={"module": "attack_simulator", "broker": BROKER},
            )
    else:
        logger.error(f"Connection failed with code {rc}")


def setup_mqtt_client() -> mqtt.Client:
    """Initialize MQTT client with mTLS security."""
    logger.info("Initializing attack simulator with mTLS...")
    
    mqtt_client = mqtt.Client(
        client_id="attack-simulator-client",
        protocol=mqtt.MQTTv311
    )
    mqtt_client.on_connect = on_connect
    
    try:
        mqtt_client.tls_set(
            ca_certs=CA_CERT,
            certfile=CLIENT_CERT,
            keyfile=CLIENT_KEY,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_3,
            ciphers=None
        )
        
        if TLS_INSECURE:
            logger.warning("⚠️  TLS_INSECURE=true (TEST MODE ONLY)")
            mqtt_client.tls_insecure_set(True)
        else:
            mqtt_client.tls_insecure_set(False)
        
        logger.info("✅ TLS configuration complete")
    except Exception as e:
        logger.error(f"TLS setup failed: {e}")
        raise
    
    return mqtt_client


def publish_attack_payload(
    attack_type: AttackVector,
    metrics: dict,
    attack_count: int = 1
) -> bool:
    """Publish a malicious payload to test anomaly detection."""
    try:
        payload = {
            "timestamp": time.time(),
            "node_id": "vibration_sensor_01",
            "metrics": metrics
        }
        msg_info = client.publish(TOPIC, json.dumps(payload), qos=1)
        msg_info.wait_for_publish(timeout=2.0)
        
        logger.info(f"🎯 [{attack_type.value}] Attack payload #{attack_count} delivered: {metrics}")
        
        if audit_logger:
            audit_logger.log_event(
                event_type="ATTACK_PAYLOAD_TRANSMITTED",
                severity=EventSeverity.CRITICAL,
                user_id="attack-simulator",
                user_role=UserRole.ADMIN,
                description=f"Attack vector '{attack_type.value}' injected for testing",
                metadata={
                    "attack_type": attack_type.value,
                    "payload": metrics,
                    "sequence": attack_count,
                },
            )
        return True
    except Exception as e:
        logger.error(f"Failed to publish attack payload: {e}")
        return False


def attack_vector_1_over_vibration():
    """
    Attack Vector 1: Over-vibration Exploitation
    Simulates extreme sensor values to bypass threshold-based detection.
    """
    logger.warning("\n" + "=" * 60)
    logger.warning("💥 ATTACK VECTOR 1: INDUSTRIAL OVER-VIBRATION EXPLOITATION")
    logger.warning("=" * 60)
    
    for i in range(5):
        metrics = {
            "vibration_hz": 185.40,      # Extreme spike (normal: 45-55)
            "temperature_c": 92.10,      # High spike (normal: 22-26)
            "link_quality_qos": 12.4     # Poor signal (normal: 94-99.9)
        }
        if not publish_attack_payload(AttackVector.OVER_VIBRATION, metrics, i + 1):
            return False
        time.sleep(ATTACK_INTERVAL)
    
    logger.info("✅ Over-vibration attack sequence complete")
    return True


def attack_vector_2_thermal_drift():
    """
    Attack Vector 2: Stealthy Thermal Drift
    Slowly increases temperature while keeping other metrics stable.
    This tests detection of gradual anomalies that bypass simple thresholds.
    """
    logger.warning("\n" + "=" * 60)
    logger.warning("🥷  ATTACK VECTOR 2: STEALTHY THERMAL DRIFT")
    logger.warning("=" * 60)
    
    for step in range(5):
        drifted_temp = 25.0 + (step * 4.0)
        metrics = {
            "vibration_hz": 51.20,           # Appear normal
            "temperature_c": round(drifted_temp, 2),
            "link_quality_qos": 95.0        # Appear normal
        }
        if not publish_attack_payload(AttackVector.THERMAL_DRIFT, metrics, step + 1):
            return False
        time.sleep(ATTACK_INTERVAL)
    
    logger.info("✅ Thermal drift attack sequence complete")
    return True


def attack_vector_3_link_degradation():
    """
    Attack Vector 3: Link Quality Degradation
    Simulates signal jamming or communication tampering.
    """
    logger.warning("\n" + "=" * 60)
    logger.warning("📡 ATTACK VECTOR 3: LINK QUALITY DEGRADATION")
    logger.warning("=" * 60)
    
    for step in range(5):
        degraded_quality = 95.0 - (step * 15.0)
        metrics = {
            "vibration_hz": round(50.0 + (step * 0.5), 2),
            "temperature_c": round(24.0 + (step * 0.2), 2),
            "link_quality_qos": max(10.0, degraded_quality)
        }
        if not publish_attack_payload(AttackVector.LINK_DEGRADATION, metrics, step + 1):
            return False
        time.sleep(ATTACK_INTERVAL)
    
    logger.info("✅ Link degradation attack sequence complete")
    return True


def main():
    """Main attack simulation loop."""
    global client, running
    
    logger.info("=" * 60)
    logger.info("KIRA: Attack Simulator (Security Testing Module)")
    logger.info("=" * 60)
    logger.info("Purpose: Test anomaly detection under attack conditions")
    logger.info(f"Baseline delay: {BASELINE_DELAY}s (allow AI to train)")
    logger.info("=" * 60)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup and connect
        client = setup_mqtt_client()
        
        logger.info(f"Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
        
        # Wait for baseline training
        logger.info(f"⏳ Waiting {BASELINE_DELAY}s for AI baseline training...")
        time.sleep(BASELINE_DELAY)
        
        if not running:
            return
        
        # Execute attack vectors
        logger.warning("\n🚀 LAUNCHING ATTACK SEQUENCES...\n")
        
        if not attack_vector_1_over_vibration():
            return
        
        time.sleep(10)  # Pause between attack vectors
        
        if not attack_vector_2_thermal_drift():
            return
        
        time.sleep(10)
        
        if not attack_vector_3_link_degradation():
            return
        
        logger.warning("\n" + "=" * 60)
        logger.warning("✅ ALL ATTACK SEQUENCES COMPLETE")
        logger.warning("Observe how the AI anomaly detector responds...")
        logger.warning("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("Attack simulation interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error in attack simulator: {e}", exc_info=True)
    finally:
        logger.info("Shutting down attack simulator...")
        if client:
            client.loop_stop()
            client.disconnect()
            time.sleep(1)
        # Slowly drift temperature up while keeping vibration relatively stable
        if audit_logger:
            audit_logger.log_event(
                event_type="ATTACK_MODULE_SHUTDOWN",
                severity=EventSeverity.INFO,
                user_id="attack-simulator",
                user_role=UserRole.ADMIN,
                description="Attack simulator shut down",
            )


if __name__ == "__main__":
    main()
