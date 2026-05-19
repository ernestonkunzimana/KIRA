# API Specification: Edge AI Anomaly Detection System

**Version:** 1.0  
**Last Updated:** May 19, 2026  
**Target Audience:** Integration engineers, DevOps, platform teams

---

## 1. MQTT Telemetry Protocol

### 1.1 Broker Configuration

```yaml
Host:           mqtt-broker
Port:           8883 (TLS) | 1883 (plaintext - dev only)
Protocol:       MQTTv3.1.1 / MQTT 5.0
TLS Version:    TLSv1.2+ (v1.3 recommended)
Authentication: Certificate-based (mTLS) + username/password
QoS:            1 (at-least-once delivery)
```

### 1.2 Telemetry Topic Schema

**Topic:** `factory/edge/telemetry`

**Message Format (JSON):**

```json
{
  "node_id": "factory-sensor-42",
  "timestamp": "2026-05-19T14:30:45Z",
  "metrics": {
    "vibration_hz": 45.2,
    "temperature_c": 32.1,
    "link_quality_qos": 85
  },
  "metadata": {
    "device_type": "vibration_sensor",
    "location": "Assembly Line A",
    "firmware_version": "2.1.0"
  }
}
```

### 1.3 Field Specifications

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `node_id` | string | Max 64 chars | Unique sensor/device identifier |
| `timestamp` | ISO 8601 | UTC | Event timestamp (mandatory) |
| `vibration_hz` | float | 0-200 Hz | Machinery vibration frequency |
| `temperature_c` | float | -40 to +85°C | Operating temperature |
| `link_quality_qos` | int | 0-100 | Signal strength / network QoS |
| `device_type` | string | - | Sensor type (e.g., "accelerometer") |
| `location` | string | - | Physical location for multi-site |
| `firmware_version` | string | - | Device firmware version |

### 1.4 Example: Publish Telemetry

**Python Client:**

```python
import json
import paho.mqtt.client as mqtt
from datetime import datetime

client = mqtt.Client(client_id="factory-sensor-42")

# Configure mTLS
client.tls_set(
    ca_certs="ca.crt",
    certfile="client.crt",
    keyfile="client.key",
    cert_reqs=mqtt.ssl.CERT_REQUIRED,
    tls_version=mqtt.ssl.PROTOCOL_TLSv1_2
)

client.connect("mqtt-broker", 8883, keepalive=60)

# Prepare telemetry payload
payload = {
    "node_id": "factory-sensor-42",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "metrics": {
        "vibration_hz": 45.2,
        "temperature_c": 32.1,
        "link_quality_qos": 85
    },
    "metadata": {
        "device_type": "vibration_sensor",
        "location": "Assembly Line A",
        "firmware_version": "2.1.0"
    }
}

# Publish
client.publish("factory/edge/telemetry", json.dumps(payload), qos=1)
client.loop_forever()
```

**Node.js / MQTT.js:**

```javascript
const mqtt = require('mqtt');
const fs = require('fs');

const options = {
  clientId: 'factory-sensor-42',
  ca: fs.readFileSync('ca.crt'),
  cert: fs.readFileSync('client.crt'),
  key: fs.readFileSync('client.key'),
  rejectUnauthorized: true
};

const client = mqtt.connect('mqtts://mqtt-broker:8883', options);

client.on('connect', () => {
  const payload = {
    node_id: 'factory-sensor-42',
    timestamp: new Date().toISOString(),
    metrics: {
      vibration_hz: 45.2,
      temperature_c: 32.1,
      link_quality_qos: 85
    }
  };
  
  client.publish('factory/edge/telemetry', JSON.stringify(payload), { qos: 1 });
});
```

---

## 2. Enterprise Webhook APIs

### 2.1 SIEM Webhook (Splunk HEC)

**Endpoint:** `https://splunk.example.com:8088/services/collector`

**Authentication:** Splunk HTTP Event Collector (HEC) token in Authorization header

**Request Format:**

```bash
curl -X POST https://splunk.example.com:8088/services/collector \
  -H "Authorization: Splunk YOUR_HEC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "timestamp": "2026-05-19T14:30:45Z",
      "event_type": "ANOMALY_DETECTED",
      "severity": "CRITICAL",
      "node_id": "edge-ai-agent-001",
      "target_asset": "factory-sensor-42",
      "anomaly_score": 0.92,
      "metrics": {
        "vibration_hz": 125.8,
        "temperature_c": 42.5,
        "link_quality_qos": 35
      }
    },
    "sourcetype": "_json",
    "source": "edge-ai-agent",
    "host": "edge-ai-agent-001"
  }'
```

**Response:**

```json
{
  "code": 0,
  "text": "Success"
}
```

### 2.2 Incident Management Webhook (PagerDuty Events API v2)

**Endpoint:** `https://events.pagerduty.com/v2/enqueue`

**Authentication:** PagerDuty routing key in request body

**Request Format:**

```json
POST /v2/enqueue
Content-Type: application/json

{
  "routing_key": "YOUR_ROUTING_KEY",
  "event_action": "trigger",
  "payload": {
    "summary": "Critical anomaly detected: factory-sensor-42",
    "severity": "critical",
    "source": "edge-ai-agent-001",
    "custom_details": {
      "node_id": "edge-ai-agent-001",
      "target_asset": "factory-sensor-42",
      "anomaly_score": 0.92,
      "metrics": {
        "vibration_hz": 125.8,
        "temperature_c": 42.5,
        "link_quality_qos": 35
      },
      "recommended_action": "ISOLATE_CONTAINER",
      "timestamp": "2026-05-19T14:30:45Z"
    }
  }
}
```

**Response:**

```json
{
  "status": "success",
  "dedup_key": "edge-ai-001-factory-sensor-42-1526753445000"
}
```

### 2.3 Chat Webhook (Slack)

**Endpoint:** `https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK`

**Request Format:**

```json
POST /services/YOUR/SLACK/WEBHOOK
Content-Type: application/json

{
  "text": "🚨 Critical anomaly detected on factory-sensor-42",
  "attachments": [
    {
      "color": "danger",
      "title": "Anomaly Detection Alert",
      "fields": [
        {
          "title": "Edge Node",
          "value": "edge-ai-agent-001",
          "short": true
        },
        {
          "title": "Target Asset",
          "value": "factory-sensor-42",
          "short": true
        },
        {
          "title": "Anomaly Score",
          "value": "0.92",
          "short": true
        },
        {
          "title": "Severity",
          "value": "CRITICAL",
          "short": true
        },
        {
          "title": "Vibration (Hz)",
          "value": "125.8",
          "short": true
        },
        {
          "title": "Temperature (°C)",
          "value": "42.5",
          "short": true
        },
        {
          "title": "Link Quality (%)",
          "value": "35",
          "short": true
        },
        {
          "title": "Remediation",
          "value": "Container isolation triggered",
          "short": false
        }
      ],
      "footer": "Edge AI Anomaly Detection System",
      "ts": 1526753445
    }
  ]
}
```

**Response:**

```
ok
```

---

## 3. Security Event Audit Log (JSONL)

**File Location:** `/app/logs/audit/security_events.jsonl`

**Format:** One JSON object per line (JSONL - JSON Lines)

**Example Entries:**

```json
{"timestamp": "2026-05-19T14:30:00Z", "event_type": "CONNECTION_ESTABLISHED", "severity": "INFO", "node_id": "edge-ai-agent-001", "connection": {"broker": "mqtt-broker", "port": 8883, "success": true}, "integrity_hash": "abc123def456..."}

{"timestamp": "2026-05-19T14:30:15Z", "event_type": "MODEL_TRAINED", "severity": "INFO", "node_id": "edge-ai-agent-001", "training_config": {"samples_used": 30, "contamination_rate": 0.01, "hyperparameters": {"n_estimators": 100}}, "integrity_hash": "xyz789uvw012..."}

{"timestamp": "2026-05-19T14:32:45Z", "event_type": "COMPROMISE_DETECTED", "severity": "CRITICAL", "node_id": "edge-ai-agent-001", "target_asset": "factory-sensor-42", "anomaly_score": 0.92, "metrics": {"vibration_hz": 125.8, "temperature_c": 42.5, "link_quality_qos": 35}, "recommended_action": "ISOLATE_CONTAINER", "integrity_hash": "ijk123lmn456..."}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | UTC timestamp of event |
| `event_type` | string | Event type (see Event Types below) |
| `severity` | string | INFO, WARNING, CRITICAL, ALERT |
| `node_id` | string | Monitoring node identifier |
| `integrity_hash` | string | SHA-256 hash for tamper detection |
| `context` | object | Event-specific context |

### Event Types

```
CONNECTION_ESTABLISHED    - Successfully connected to broker
CONNECTION_FAILED         - Failed to connect to broker
AUTH_FAILURE             - Authentication/certificate failure
MODEL_TRAINED            - Baseline learning phase completed
MODEL_LOADED             - Cached model loaded from disk
ANOMALY_DETECTED         - Normal telemetry within baseline
COMPROMISE_DETECTED      - Anomalous telemetry detected
REMEDIATION_TRIGGERED    - Automatic remediation action initiated
DATA_PERSISTED           - Model serialized to disk
INTEGRITY_CHECK_PASSED   - Log file integrity verification passed
INTEGRITY_CHECK_FAILED   - Log tampering detected
```

---

## 4. Detection Metrics Log (JSONL)

**File Location:** `/app/logs/metrics/detection_metrics.jsonl`

**Format:** One JSON object per line (JSONL)

**Example Entry:**

```json
{
  "timestamp": "2026-05-19T14:30:45Z",
  "edge_node": "edge-ai-agent-001",
  "monitored_asset": "factory-sensor-42",
  "ai_prediction": 1,
  "anomaly_score": -0.15,
  "ground_truth": null,
  "telemetry": {
    "vibration_hz": 45.2,
    "temperature_c": 32.1,
    "link_quality_qos": 85
  },
  "integrity_hash": "sha256_hash_here"
}
```

### Field Definitions

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `timestamp` | ISO 8601 | - | UTC timestamp |
| `edge_node` | string | - | Monitoring node ID |
| `monitored_asset` | string | - | Sensor/asset being monitored |
| `ai_prediction` | int | 1, -1 | 1=Normal, -1=Anomaly |
| `anomaly_score` | float | -1.0 to +1.0 | Isolation Forest score |
| `ground_truth` | int | 1, -1, null | Ground truth label (if available) |
| `telemetry` | object | - | Raw metrics snapshot |

---

## 5. Evaluation Metrics Computation

### Confusion Matrix

```
             Predicted Normal    Predicted Anomaly
Actual Normal     TN (True Neg)      FP (False Pos)
Actual Anomaly    FN (False Neg)     TP (True Pos)
```

### Key Metrics

**Precision** = TP / (TP + FP)  
*"Of all predicted anomalies, how many were actually anomalies?"*

**Recall** = TP / (TP + FN)  
*"Of all actual anomalies, how many did we catch?"*

**F1 Score** = 2 × (Precision × Recall) / (Precision + Recall)  
*"Harmonic mean of precision and recall"*

**ROC-AUC** = Area under the ROC curve  
*"Overall discriminative power across all thresholds"*

### Command to Compute Metrics

```bash
docker-compose exec edge-ai-agent python /app/src/evaluate_performance.py

# Output:
# Precision: 0.94
# Recall: 0.91
# F1 Score: 0.92
# ROC-AUC: 0.96
# Confusion Matrix:
#   TN: 485  FP: 15
#   FN:   9  TP: 491
```

---

## 6. Rate Limiting & SLA

### MQTT Rate Limits

| Parameter | Limit | Notes |
|-----------|-------|-------|
| Messages/sec per client | 1000 | Burst allowed up to 5000 |
| Max message size | 256 KB | Compressed payloads recommended |
| Connection timeout | 60 sec | Server-side keep-alive |
| Max concurrent connections | 10,000 | Per broker instance |

### Webhook Rate Limits

| Service | Rate | Retry Policy |
|---------|------|--------------|
| Splunk HEC | 100 req/sec | Exponential backoff (2^n) |
| PagerDuty API | 10 req/sec | Queued internally |
| Slack API | 1 req/sec | Dedup + throttle |

### SLA (Service Level Agreement)

| Metric | Target |
|--------|--------|
| Availability | 99.99% uptime |
| Detection Latency | <100 ms |
| Webhook Delivery | <5 sec after event |
| Log Persistence | Guaranteed (retry until success) |

---

## 7. Error Codes & Responses

### MQTT Connection Errors

```
0   - Connection successful
1   - Incorrect protocol version
2   - Invalid client identifier
3   - Server unavailable
4   - Bad username/password
5   - Not authorized
6-255 - Reserved for future use
```

### Webhook HTTP Status Codes

```
200 - OK (success)
201 - Created
202 - Accepted (queued)
400 - Bad request (malformed JSON)
401 - Unauthorized (invalid token)
403 - Forbidden (rate limited)
429 - Too many requests
500 - Server error
502 - Bad gateway
503 - Service unavailable
```

### Error Response Format

```json
{
  "error": "INVALID_CREDENTIALS",
  "message": "TLS certificate verification failed",
  "code": 401,
  "timestamp": "2026-05-19T14:30:45Z",
  "request_id": "req-12345678"
}
```

---

## 8. Backward Compatibility

**Current API Version:** v1.0  
**Deprecation Policy:** 12-month notice before breaking changes  
**Versioning Scheme:** Semantic versioning (MAJOR.MINOR.PATCH)

---

## Appendix: Example Integrations

### Integration 1: ELK Stack (Elasticsearch + Logstash + Kibana)

**Logstash Configuration:**

```conf
input {
  file {
    path => "/app/logs/audit/security_events.jsonl"
    codec => json
    start_position => "beginning"
  }
}

filter {
  if [event_type] == "COMPROMISE_DETECTED" {
    mutate {
      add_tag => ["security_alert", "critical"]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "edge-ai-alerts-%{+YYYY.MM.dd}"
  }
}
```

### Integration 2: Datadog

**Configuration:**

```yaml
datadog_agent:
  logs:
    - type: file
      path: "/app/logs/audit/security_events.jsonl"
      service: "edge-ai-anomaly-detection"
      source: "edge-ai"
      parser: json
```

---

**For questions or integration support, contact:** support@zentra.rw
