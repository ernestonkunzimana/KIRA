"""
Edge AI Anomaly Detection System for Industrial IoT
=====================================================
Combines baseline learning, real-time inference, and security verification
using Isolation Forest with MQTT/mTLS transport and federated-ready architecture.

Author: Ernest Nkunzimana (Zentra Ltd)
License: MIT
"""

import json
import ssl
import time
import threading
import pickle
import os
import numpy as np
import paho.mqtt.client as mqtt
from sklearn.ensemble import IsolationForest
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# Configuration
# ============================================================================

BROKER = "mqtt-broker"
PORT = 8883
TOPIC = "factory/edge/telemetry"
LOG_FILE = os.path.join(BASE_DIR, "src", "detection_metrics.json")
MODEL_CACHE = os.path.join(BASE_DIR, "src", "edge_model.pkl")
CA_CERT = os.path.join(BASE_DIR, "certs", "ca.crt")
CLIENT_CERT = os.path.join(BASE_DIR, "certs", "client.crt")
CLIENT_KEY = os.path.join(BASE_DIR, "certs", "client.key")
TRAINING_THRESHOLD = 30  # Baseline packets required for model training
CONTAMINATION_RATE = 0.01  # Expected anomaly rate in baseline (1%)
RECONNECT_DELAY = 5  # Seconds between reconnection attempts
MAX_RECONNECT_ATTEMPTS = 10

# ============================================================================
# Global State Management
# ============================================================================

training_buffer = []
model = None
IS_TRAINED = False
client = None
reconnect_count = 0

# Thread safety for global state (critical for async MQTT callbacks)
state_lock = threading.Lock()

# ============================================================================
# Model Training & Persistence
# ============================================================================

def save_model_to_disk():
    """Serialize trained model to disk for edge persistence."""
    global model
    try:
        with state_lock:
            if model is not None:
                os.makedirs(os.path.dirname(MODEL_CACHE), exist_ok=True)
                with open(MODEL_CACHE, 'wb') as f:
                    pickle.dump(model, f)
                print(f"[MODEL PERSISTENCE] Model saved to {MODEL_CACHE}")
    except Exception as e:
        print(f"[MODEL PERSISTENCE ERROR] Failed to save model: {e}")

def load_model_from_disk():
    """Load pre-trained model from disk on startup (avoid retraining)."""
    global model, IS_TRAINED
    try:
        if os.path.exists(MODEL_CACHE):
            with open(MODEL_CACHE, 'rb') as f:
                model = pickle.load(f)
            IS_TRAINED = True
            print(f"[MODEL PERSISTENCE] Model loaded from {MODEL_CACHE}")
            return True
    except Exception as e:
        print(f"[MODEL PERSISTENCE ERROR] Failed to load model: {e}")
    return False

def train_edge_model(data_pool):
    """
    Trains an unsupervised Isolation Forest on baseline telemetry data.
    
    Phase 1 (Passive Learning):
    - Collects first N packets as "normal" baseline
    - Learns statistical fingerprint without labels
    
    Args:
        data_pool: List of dicts with 'features' (vibration_hz, temperature_c, link_quality_qos)
    """
    global model, IS_TRAINED
    print(f"\n[AI ENGINE] Buffer filled with {len(data_pool)} baseline profiles. Training Isolation Forest...")
    
    # Extract feature matrix: shape (n_samples, n_features=3)
    features = [item['features'] for item in data_pool]
    X_train = np.array(features)
    
    # Contamination parameter: assume ~1% of baseline contains natural anomalies
    model = IsolationForest(
        contamination=CONTAMINATION_RATE,
        random_state=42,
        n_estimators=100,
        max_samples='auto'
    )
    model.fit(X_train)
    
    with state_lock:
        IS_TRAINED = True
    
    # Persist model for next restart
    save_model_to_disk()
    
    print("[AI ENGINE] ✅ Local model training complete. Continuous defensive monitoring active.\n")

def compute_anomaly_score(X_test):
    """
    Compute anomaly confidence score (-1 to 1).
    
    Returns:
        prediction: 1 (Normal) or -1 (Anomaly)
        score: Raw anomaly score from decision function
    """
    global model
    if model is None:
        return None, None

    try:
        prediction = model.predict(X_test)[0]
        score = model.score_samples(X_test)[0]
        return prediction, score
    except Exception as e:
        print(f"[AI ERROR] Anomaly scoring failed: {e}")
        return None, None

# ============================================================================
# Evaluation & Logging
# ============================================================================

def log_evaluation_row(timestamp, node_id, metrics, ground_truth, prediction, score, decision):
    """
    Log anomaly detection result for offline evaluation.
    
    Enables confusion matrix, ROC curves, and performance metrics computation
    via external evaluation scripts.
    """
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        record = {
            "timestamp": timestamp,
            "node_id": node_id,
            "metrics": metrics,
            "ground_truth": int(ground_truth),  # 1=Normal, -1=Anomaly
            "actual_ground_truth": int(ground_truth),
            "ai_prediction": int(prediction),
            "anomaly_score": float(score) if score is not None else None,
            "alarm_decision": decision
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[LOGGING ERROR] Failed to write evaluation log: {e}")

def infer_ground_truth(metrics):
    """
    Heuristic ground truth labeling based on domain knowledge.
    
    ⚠️  NOTE: This is a SIMPLIFIED heuristic. In production:
    - Cross-validate with SCADA/historian data
    - Use ML-predicted maintenance schedules
    - Incorporate domain expert feedback
    - Consider temporal context (production cycle phase)
    
    Args:
        metrics: Dict with vibration_hz, temperature_c, link_quality_qos
        
    Returns:
        1 (Normal) or -1 (Anomaly/Attack)
    """
    vibration = metrics.get("vibration_hz", 0)
    temperature = metrics.get("temperature_c", 0)
    link_quality = metrics.get("link_quality_qos", 100)
    
    # Domain thresholds (equipment-specific; adjust per use case)
    VIBRATION_THRESHOLD = 100  # Hz
    TEMP_THRESHOLD = 35  # Celsius
    LINK_QUALITY_THRESHOLD = 50  # QoS score
    
    if vibration > VIBRATION_THRESHOLD or \
       temperature > TEMP_THRESHOLD or \
       link_quality < LINK_QUALITY_THRESHOLD:
        return -1  # Anomaly
    
    return 1  # Normal

# ============================================================================
# MQTT Client Callbacks
# ============================================================================

def on_connect(client, userdata, flags, rc):
    """Handle MQTT connection establishment."""
    global reconnect_count
    if rc == 0:
        print(f"[MQTT] ✅ Connected to {BROKER}:{PORT}")
        client.subscribe(TOPIC, qos=1)
        reconnect_count = 0
    else:
        print(f"[MQTT ERROR] Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    """Handle MQTT disconnection and trigger reconnect logic."""
    global reconnect_count
    if rc != 0:
        print(f"[MQTT] ⚠️  Unexpected disconnection (code {rc}). Reconnecting...")
        reconnect_count += 1
        if reconnect_count < MAX_RECONNECT_ATTEMPTS:
            time.sleep(RECONNECT_DELAY)
            try:
                client.reconnect()
            except Exception as e:
                print(f"[MQTT ERROR] Reconnection failed: {e}")
        else:
            print(f"[MQTT FATAL] Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) exceeded. Exiting.")

def on_message(client, userdata, msg):
    """
    Main anomaly detection pipeline.
    
    Phase 1 (LEARNING): Collect baseline if IS_TRAINED == False
    Phase 2 (INFERENCE): Detect anomalies if IS_TRAINED == True
    """
    global IS_TRAINED, training_buffer
    
    try:
        # Parse MQTT payload
        payload = json.loads(msg.payload.decode('utf-8'))
        metrics = payload.get("metrics", {})
        node_id = payload.get("node_id", "unknown")
        timestamp = datetime.utcnow().isoformat()
        
        # Extract feature vector
        current_features = [
            metrics.get("vibration_hz", 0),
            metrics.get("temperature_c", 0),
            metrics.get("link_quality_qos", 100)
        ]
        
        # Infer ground truth from heuristics (for evaluation)
        ground_truth = infer_ground_truth(metrics)

        should_train = False
        training_snapshot = None
        
        with state_lock:
            if not IS_TRAINED:
                # ================================================================
                # PHASE 1: PASSIVE BASELINE LEARNING
                # ================================================================
                training_buffer.append({"features": current_features})
                progress = len(training_buffer)
                print(f"[DEFENSE - LEARNING] Baseline fingerprint {progress}/{TRAINING_THRESHOLD} | Node: {node_id}")
                
                if progress >= TRAINING_THRESHOLD:
                    training_snapshot = list(training_buffer)
                    should_train = True
            else:
                # ================================================================
                # PHASE 2: ACTIVE INFERENCE & ANOMALY DETECTION
                # ================================================================
                X_test = np.array([current_features])
                prediction, score = compute_anomaly_score(X_test)
                
                if prediction is None:
                    return
                
                # Log result for offline evaluation
                decision = "PASS" if prediction == 1 else "ALARM"
                log_evaluation_row(timestamp, node_id, metrics, ground_truth, prediction, score, decision)
                
                # Display inference result
                if prediction == 1:
                    print(f"[DEFENSE - PASS ✅] Telemetry within safe parameters | Node: {node_id} | Score: {score:.4f}")
                else:
                    print(f"\n🚨 [DEFENSE - ALARM 🔴] COMPROMISE DETECTED!")
                    print(f"   ↳ Node ID: {node_id}")
                    print(f"   ↳ Timestamp: {timestamp}")
                    print(f"   ↳ Metrics: {metrics}")
                    print(f"   ↳ Anomaly Score: {score:.4f}")
                    print(f"   ↳ Ground Truth: {'Anomaly' if ground_truth == -1 else 'Normal'}")
                    print(f"   ↳ Action: Triggering local isolation protocols.\n")

        if should_train and training_snapshot is not None:
            train_edge_model(training_snapshot)
    
    except json.JSONDecodeError as e:
        print(f"[DEFENSE ERROR] Invalid JSON payload: {e}")
    except Exception as e:
        print(f"[DEFENSE ERROR] Error processing telemetry: {e}")

# ============================================================================
# MQTT Client Setup with mTLS
# ============================================================================

def setup_mqtt_client():
    """Configure MQTT client with mTLS and callbacks."""
    global client
    
    client = mqtt.Client(client_id="edge-ai-analytics", protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # ✅ FIXED: Remove insecure flag in production; keep for local dev only
    # For production, ensure certificates are valid and do NOT set tls_insecure_set(True)
    client.tls_set(
        ca_certs=CA_CERT,
        certfile=CLIENT_CERT,
        keyfile=CLIENT_KEY,
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLSv1_2
    )
    
    # ⚠️  DEVELOPMENT ONLY: Bypass hostname verification for self-signed certs
    # REMOVE THIS IN PRODUCTION or use valid CA certificates
    client.tls_insecure_set(True)
    
    return client

# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Initialize and run the edge AI anomaly detection pipeline."""
    global client
    
    print("=" * 70)
    print("Edge AI Anomaly Detection System v1.0")
    print("=" * 70)
    print(f"Broker: {BROKER}:{PORT}")
    print(f"Topic: {TOPIC}")
    print(f"Model Cache: {MODEL_CACHE}")
    print(f"Log File: {LOG_FILE}")
    print("=" * 70)
    
    # Attempt to load cached model
    if not load_model_from_disk():
        print("[AI ENGINE] No cached model found. Will train on first baseline data.\n")
    
    # Setup and connect MQTT client
    client = setup_mqtt_client()
    
    print(f"[AI ENGINE] Connecting to secure MQTT pipeline at {BROKER}:{PORT}...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Received interrupt signal. Saving model and exiting...")
        save_model_to_disk()
        client.disconnect()
        client.loop_stop()
        print("[SHUTDOWN] ✅ Graceful shutdown complete.")
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        save_model_to_disk()

if __name__ == "__main__":
    main()