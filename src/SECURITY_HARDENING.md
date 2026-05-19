# Security Hardening Guide: Enterprise Edge AI System

**Classification:** INTERNAL USE - FOR SECURITY TEAMS  
**Version:** 1.0  
**Last Updated:** May 19, 2026  
**Audience:** Security engineers, DevOps, infrastructure teams

---

## Executive Summary

This guide addresses **critical security gaps** identified in the Enterprise Readiness Audit:

| Gap | Severity | Status | Mitigation |
|-----|----------|--------|-----------|
| Insecure TLS config | CRITICAL | ✅ Fixed | Use CA-signed certs, remove `tls_insecure_set(True)` |
| No secrets mgmt | CRITICAL | ✅ Fixed | Implement Vault/AWS Secrets Manager |
| No audit logging | CRITICAL | ✅ Fixed | Structured JSON audit trails with integrity hashing |
| Plaintext logs | HIGH | ✅ Fixed | Encrypt logs at rest, use SIEM ingestion |
| No access control | HIGH | ✅ Fixed | Implement MQTT ACLs + RBAC |
| No encryption at rest | HIGH | ✅ Fixed | Fernet encryption for model + logs |

---

## 1. TLS/PKI Hardening

### 1.1 Current (INSECURE) Implementation

```python
# ❌ PRODUCTION RISK: This code is INSECURE
client.tls_set(
    ca_certs="/app/certs/ca.crt",
    certfile="/app/certs/client.crt",
    keyfile="/app/certs/client.key",
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(True)  # ❌ BYPASSES HOSTNAME VERIFICATION - ENABLES MITM
```

**Security Issues:**
- `tls_insecure_set(True)` disables hostname verification
- TLSv1.2 is acceptable but v1.3 is preferred
- No cipher suite specification (uses system default)
- Self-signed certificates (acceptable for dev, not for production)

### 1.2 FIXED (Secure) Implementation

```python
import ssl
import certifi
import os

# ✅ PRODUCTION SECURE: Proper TLS configuration
client = mqtt.Client(client_id="edge-ai-analytics", protocol=mqtt.MQTTv311)

# 1. Use TLS 1.3 (latest secure version)
# 2. Require certificate verification
# 3. Specify strong cipher suites
# 4. DO NOT bypass hostname verification

ssl_context = ssl.create_default_context()

# Force TLS 1.3
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3

# Use only strong cipher suites
ssl_context.set_ciphers(
    'TLS_AES_256_GCM_SHA384:'           # Strongest AES
    'TLS_CHACHA20_POLY1305_SHA256:'     # ChaCha20 alternative
    'TLS_AES_128_GCM_SHA256'            # AES-128 fallback
)

# Enable certificate pinning (optional but recommended)
ssl_context.check_hostname = True  # Verify hostname matches certificate
ssl_context.verify_mode = ssl.CERT_REQUIRED

# Load CA bundle
ca_cert_path = os.environ.get(
    "EDGE_AI_CA_CERT_PATH",
    "/etc/tls/ca/ca-bundle.crt"
)
ssl_context.load_verify_locations(ca_cert_path)

# Load client certificate
certfile_path = os.environ.get(
    "EDGE_AI_CLIENT_CERT_PATH",
    "/etc/tls/client/client.crt"
)
keyfile_path = os.environ.get(
    "EDGE_AI_CLIENT_KEY_PATH",
    "/etc/tls/client/client.key"
)

ssl_context.load_cert_chain(
    certfile=certfile_path,
    keyfile=keyfile_path
)

# Restrict file permissions on private key
import os
os.chmod(keyfile_path, 0o600)  # Owner read/write only

# Attach SSL context to MQTT client
client.tls_set_context(ssl_context)

# ✅ DO NOT call tls_insecure_set(True) - this is SECURE now
# client.tls_insecure_set(True)  # DELETE THIS LINE

client.connect(BROKER, PORT, keepalive=60)
```

### 1.3 Certificate Management Strategy

#### 1.3.1 Public Key Infrastructure (PKI) Setup

```bash
#!/bin/bash
# Generate self-signed root CA (valid for 10 years)

openssl genrsa -out ca.key 4096

openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/C=RW/ST=Kigali/L=Kigali/O=Zentra/CN=Edge AI CA"

# Generate server certificate (MQTT Broker)
openssl genrsa -out server.key 2048

openssl req -new -key server.key -out server.csr \
  -subj "/C=RW/ST=Kigali/L=Kigali/O=Zentra/CN=mqtt-broker"

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 365 \
  -addext "subjectAltName=DNS:mqtt-broker,DNS:localhost,IP:192.168.1.100"

# Generate client certificate (Edge AI Agent)
openssl genrsa -out client.key 2048

openssl req -new -key client.key -out client.csr \
  -subj "/C=RW/ST=Kigali/L=Kigali/O=Zentra/CN=edge-ai-agent"

openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out client.crt -days 365

# Set restrictive permissions
chmod 600 ca.key server.key client.key
chmod 644 ca.crt server.crt client.crt

# Verify certificate chain
openssl verify -CAfile ca.crt server.crt
openssl verify -CAfile ca.crt client.crt
```

#### 1.3.2 Certificate Rotation Policy

```bash
#!/bin/bash
# Automatic certificate renewal (run quarterly)

CERT_EXPIRY_DAYS=30
CLIENT_CERT="/etc/tls/client/client.crt"

# Check certificate expiry
expiry_date=$(openssl x509 -in $CLIENT_CERT -noout -enddate | cut -d= -f2)
expiry_epoch=$(date -d "$expiry_date" +%s)
current_epoch=$(date +%s)
days_remaining=$(( ($expiry_epoch - $current_epoch) / 86400 ))

if [ $days_remaining -lt $CERT_EXPIRY_DAYS ]; then
  echo "[CERT RENEWAL] Certificate expires in $days_remaining days. Renewing..."
  
  # Backup old certificate
  cp $CLIENT_CERT $CLIENT_CERT.backup-$(date +%Y%m%d)
  
  # Generate new certificate
  openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key \
    -out $CLIENT_CERT -days 365
  
  # Restart edge-ai-agent to load new certificate
  docker-compose restart edge-ai-agent
  
  echo "[CERT RENEWAL] ✅ Certificate renewed successfully"
fi
```

---

## 2. Secrets Management

### 2.1 Never Store Secrets in Code or Git

```bash
# ❌ DO NOT DO THIS
# Hardcoded in code or environment
os.environ["SPLUNK_HEC_TOKEN"] = "abcd1234efgh5678"
```

### 2.2 Use HashiCorp Vault (Recommended)

```bash
# 1. Install and run Vault locally (dev mode)
vault server -dev

# 2. Enable KV secrets engine
vault secrets enable -path=secret kv

# 3. Store certificates
vault kv put secret/edge-ai/mqtt \
  ca_cert=@ca.crt \
  client_cert=@client.crt \
  client_key=@client.key

# 4. Store API tokens
vault kv put secret/edge-ai/webhooks \
  splunk_hec_token="YOUR_HEC_TOKEN" \
  pagerduty_routing_key="YOUR_ROUTING_KEY" \
  slack_webhook="https://hooks.slack.com/..."

# 5. Enable AppRole authentication
vault auth enable approle

vault write auth/approle/role/edge-ai \
  token_ttl=24h \
  token_max_ttl=48h

# Get credentials
vault read auth/approle/role/edge-ai/role-id
vault write -f auth/approle/role/edge-ai/secret-id
```

**Python Integration:**

```python
import hvac
import os
from pathlib import Path

class VaultSecretManager:
    """Retrieve secrets from HashiCorp Vault at runtime."""
    
    def __init__(self, vault_url="http://localhost:8200"):
        self.client = hvac.Client(url=vault_url)
        
        # Use AppRole for authentication
        role_id = os.environ.get("VAULT_ROLE_ID")
        secret_id = os.environ.get("VAULT_SECRET_ID")
        
        self.client.auth.approle.login(
            role_id=role_id,
            secret_id=secret_id
        )
    
    def get_mqtt_certs(self):
        """Retrieve MQTT certificates from Vault."""
        secrets = self.client.secrets.kv.v2.read_secret_version(
            path="edge-ai/mqtt"
        )
        
        data = secrets['data']['data']
        
        # Write certificates to temporary files
        ca_path = Path("/tmp/ca.crt")
        ca_path.write_bytes(data['ca_cert'].encode())
        ca_path.chmod(0o600)
        
        cert_path = Path("/tmp/client.crt")
        cert_path.write_bytes(data['client_cert'].encode())
        cert_path.chmod(0o600)
        
        key_path = Path("/tmp/client.key")
        key_path.write_bytes(data['client_key'].encode())
        key_path.chmod(0o600)
        
        return str(ca_path), str(cert_path), str(key_path)
    
    def get_webhook_tokens(self):
        """Retrieve webhook credentials from Vault."""
        secrets = self.client.secrets.kv.v2.read_secret_version(
            path="edge-ai/webhooks"
        )
        
        return secrets['data']['data']

# Usage in application
vault = VaultSecretManager()
ca_cert, client_cert, client_key = vault.get_mqtt_certs()
webhooks = vault.get_webhook_tokens()

# Configure MQTT with secrets from Vault
client.tls_set(
    ca_certs=ca_cert,
    certfile=client_cert,
    keyfile=client_key,
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLSv1_3
)
```

### 2.3 AWS Secrets Manager Alternative

```bash
# Store secrets in AWS
aws secretsmanager create-secret \
  --name edge-ai/mqtt-certs \
  --secret-string file://secrets.json

# Retrieve in Python
import boto3
import json

secrets_client = boto3.client('secretsmanager')

response = secrets_client.get_secret_value(
    SecretId='edge-ai/mqtt-certs'
)

secrets = json.loads(response['SecretString'])
ca_cert = secrets['ca_cert']
client_cert = secrets['client_cert']
client_key = secrets['client_key']
```

---

## 3. Audit Logging & Integrity

### 3.1 Structured Audit Logs

All security events logged in JSONL format with integrity hashing:

```json
{
  "timestamp": "2026-05-19T14:30:45Z",
  "event_type": "COMPROMISE_DETECTED",
  "severity": "CRITICAL",
  "node_id": "edge-ai-agent-001",
  "target_asset": "factory-sensor-42",
  "anomaly_score": 0.92,
  "integrity_hash": "sha256_computed_hash_here"
}
```

**Integrity Hash Computation:**

```python
import hashlib
import json

def compute_integrity_hash(event):
    """Compute SHA-256 hash of event (excluding hash field)."""
    # Remove hash field if present
    event_copy = {k: v for k, v in event.items() if k != "integrity_hash"}
    
    # Sort keys for deterministic hashing
    event_str = json.dumps(event_copy, sort_keys=True)
    
    # Compute SHA-256
    return hashlib.sha256(event_str.encode()).hexdigest()

# Usage
event = {
    "timestamp": "2026-05-19T14:30:45Z",
    "event_type": "ANOMALY_DETECTED",
    "node_id": "edge-ai-001"
}

event["integrity_hash"] = compute_integrity_hash(event)
print(json.dumps(event))
```

### 3.2 Log Integrity Verification

```python
def verify_log_integrity(log_file):
    """Verify all entries in log file have not been tampered."""
    
    tampered_count = 0
    verified_count = 0
    
    with open(log_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                stored_hash = record.pop("integrity_hash", None)
                computed_hash = compute_integrity_hash(record)
                
                if stored_hash == computed_hash:
                    verified_count += 1
                else:
                    print(f"[TAMPER ALERT] Line {line_num}: Hash mismatch!")
                    print(f"  Expected: {stored_hash}")
                    print(f"  Computed: {computed_hash}")
                    tampered_count += 1
            
            except json.JSONDecodeError:
                print(f"[ERROR] Line {line_num}: Invalid JSON")
    
    print(f"\n[INTEGRITY REPORT]")
    print(f"  Verified entries: {verified_count}")
    print(f"  Tampered entries: {tampered_count}")
    print(f"  Status: {'✅ CLEAN' if tampered_count == 0 else '❌ TAMPERED'}")
    
    return tampered_count == 0

# Usage
verify_log_integrity("/app/logs/audit/security_events.jsonl")
```

### 3.3 Immutable Audit Log (Blockchain Optional)

For high-compliance environments, consider blockchain audit ledger:

```python
from web3 import Web3
from datetime import datetime

class BlockchainAuditLedger:
    """Immutable audit trail using Ethereum-compatible blockchain."""
    
    def __init__(self, rpc_url="http://localhost:8545"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contract_address = "0x..."  # Your audit contract address
    
    def log_security_event(self, event_type, severity, details):
        """Record security event on blockchain."""
        
        # Hash event data
        event_hash = Web3.keccak(
            text=json.dumps(details, sort_keys=True)
        )
        
        # Call smart contract to record event
        tx_hash = self.contract.functions.logEvent(
            event_type,
            severity,
            event_hash,
            timestamp=int(datetime.utcnow().timestamp())
        ).transact()
        
        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"[BLOCKCHAIN AUDIT] Event recorded: {receipt.transactionHash.hex()}")
```

---

## 4. Access Control & RBAC

### 4.1 MQTT ACL Configuration

```conf
# mosquitto/config.conf
listener 8883
protocol mqtt
require_certificate true
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
tls_version tlsv1.3
allow_anonymous false
password_file /etc/mosquitto/passwd
acl_file /etc/mosquitto/acl.conf
```

**Password File (generate with `mosquitto_passwd`):**

```bash
# Create password file
mosquitto_passwd -c /etc/mosquitto/passwd edge-ai-agent

# Add more users
mosquitto_passwd -b /etc/mosquitto/passwd splunk_collector splunk_password
mosquitto_passwd -b /etc/mosquitto/passwd factory_sensor_01 sensor_password
```

**ACL File (`/etc/mosquitto/acl.conf`):**

```conf
# Edge AI Agent (full access to factory data)
user edge-ai-agent
topic readwrite factory/edge/telemetry
topic readwrite factory/edge/control
topic read factory/edge/config

# Factory Sensors (write-only)
user factory_sensor_01
topic write factory/edge/telemetry/sensor_01

user factory_sensor_02
topic write factory/edge/telemetry/sensor_02

# Splunk Collector (read-only)
user splunk_collector
topic read factory/edge/telemetry
topic read factory/edge/alerts

# Admin (all topics)
user mqtt_admin
topic readwrite #
```

### 4.2 RBAC for Remediation Actions

```python
from enum import Enum
from functools import wraps

class Role(Enum):
    VIEWER = "viewer"           # Read-only access
    ANALYST = "analyst"         # Can view alerts, run analysis
    OPERATOR = "operator"       # Can trigger non-destructive remediation
    ADMIN = "admin"             # Full access including destructive actions

class Permission(Enum):
    VIEW_LOGS = "view:logs"
    VIEW_ALERTS = "view:alerts"
    TRIGGER_CONTAINER_ISOLATION = "action:isolate_container"
    TRIGGER_NETWORK_ISOLATION = "action:isolate_network"
    ROLLBACK_REMEDIATION = "action:rollback"
    MANAGE_USERS = "admin:manage_users"

# Define role-based permissions
ROLE_PERMISSIONS = {
    Role.VIEWER: {Permission.VIEW_LOGS, Permission.VIEW_ALERTS},
    Role.ANALYST: {Permission.VIEW_LOGS, Permission.VIEW_ALERTS},
    Role.OPERATOR: {
        Permission.VIEW_LOGS,
        Permission.VIEW_ALERTS,
        Permission.TRIGGER_CONTAINER_ISOLATION
    },
    Role.ADMIN: {perm for perm in Permission}
}

def require_permission(permission: Permission):
    """Decorator to enforce permission checks."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_role = kwargs.get('user_role', Role.VIEWER)
            
            if permission not in ROLE_PERMISSIONS[user_role]:
                raise PermissionError(
                    f"User role {user_role.value} cannot {permission.value}"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Usage
@require_permission(Permission.TRIGGER_CONTAINER_ISOLATION)
def isolate_container(container_id: str, user_role: Role):
    """Isolate container (requires OPERATOR or ADMIN role)."""
    print(f"Isolating container {container_id}...")
    # ... implementation
```

---

## 5. Encryption at Rest

### 5.1 Encrypt Models Before Persistence

```python
from cryptography.fernet import Fernet
import pickle
import os

class EncryptedModelStore:
    """Securely store trained models with encryption."""
    
    def __init__(self, encryption_key: bytes = None):
        """
        Initialize with encryption key.
        
        Key can be generated with:
        key = Fernet.generate_key()
        """
        if encryption_key is None:
            # Load from environment
            key_str = os.environ.get("ENCRYPTION_KEY")
            if not key_str:
                raise ValueError("ENCRYPTION_KEY not set in environment")
            encryption_key = key_str.encode()
        
        self.cipher = Fernet(encryption_key)
    
    def save_model(self, model, path: str):
        """Save and encrypt model."""
        
        # Serialize model
        plaintext = pickle.dumps(model)
        
        # Encrypt
        ciphertext = self.cipher.encrypt(plaintext)
        
        # Write to disk
        with open(path, 'wb') as f:
            f.write(ciphertext)
        
        print(f"[ENCRYPTION] Model saved (encrypted): {path}")
    
    def load_model(self, path: str):
        """Load and decrypt model."""
        
        # Read encrypted data
        with open(path, 'rb') as f:
            ciphertext = f.read()
        
        # Decrypt
        plaintext = self.cipher.decrypt(ciphertext)
        
        # Deserialize
        model = pickle.loads(plaintext)
        
        return model

# Usage
store = EncryptedModelStore(encryption_key=os.environ["ENCRYPTION_KEY"])
store.save_model(trained_model, "/app/src/edge_model.pkl.enc")
loaded_model = store.load_model("/app/src/edge_model.pkl.enc")
```

**Generate Encryption Key:**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Output: 7A-character-Fernet-key_with_equals_sign
# Store in environment: export ENCRYPTION_KEY="your_key_here"
```

### 5.2 Encrypt Audit Logs

```bash
# Encrypt log file (AES-256-GCM)
openssl enc -aes-256-cbc -salt -in security_events.jsonl \
  -out security_events.jsonl.enc \
  -k "$(echo $ENCRYPTION_PASSWORD | md5sum | awk '{print $1}')"

# Decrypt when needed
openssl enc -aes-256-cbc -d -in security_events.jsonl.enc \
  -out security_events.jsonl \
  -k "$(echo $ENCRYPTION_PASSWORD | md5sum | awk '{print $1}')"
```

---

## 6. Network Segmentation

### 6.1 Docker Network Isolation

```yaml
# docker-compose.yml
version: '3.8'

networks:
  edge-ai-secure:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: br-edge-ai
    ipam:
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1

services:
  edge-ai-agent:
    image: edge-ai:latest
    networks:
      - edge-ai-secure
    expose:
      - "9090"  # Prometheus metrics (internal only)
    # Restrict capabilities
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    security_opt:
      - no-new-privileges:true
    read_only_root_filesystem: true
    tmpfs:
      - /tmp
      - /run

  mosquitto:
    image: eclipse-mosquitto:latest
    networks:
      - edge-ai-secure
    expose:
      - "8883"  # MQTT TLS (internal only)
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
```

### 6.2 Kubernetes Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: edge-ai-network-policy
  namespace: edge-ai
spec:
  podSelector:
    matchLabels:
      app: edge-ai-agent
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow MQTT from sensors
    - from:
        - podSelector:
            matchLabels:
              app: factory-sensor
      ports:
        - protocol: TCP
          port: 8883
  egress:
    # Allow egress to MQTT broker
    - to:
        - podSelector:
            matchLabels:
              app: mosquitto
      ports:
        - protocol: TCP
          port: 8883
    # Allow DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53
    # Allow webhook egress to external APIs
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 443
```

---

## 7. Compliance Checklist

### NIST Cybersecurity Framework

- [ ] **Identify**: Map all data flows and assets (MQTT broker, edge agent, SIEM)
- [ ] **Protect**: Implement TLS, encryption, RBAC, secrets management
- [ ] **Detect**: Deploy audit logging and anomaly detection
- [ ] **Respond**: Automated remediation engine with incident escalation
- [ ] **Recover**: Data backups, model snapshots, disaster recovery plan

### PCI-DSS (Payment Card Industry)

- [ ] Requirement 2: Change default credentials and remove unnecessary services
- [ ] Requirement 3: Encrypt data at rest (Fernet encryption)
- [ ] Requirement 4: Encrypt data in transit (TLS 1.3)
- [ ] Requirement 6: Develop secure code (SAST scanning)
- [ ] Requirement 8: Identify users and restrict access (RBAC, MQTT ACLs)
- [ ] Requirement 10: Maintain audit logs (JSONL with integrity hashing)

### ISO 27001 (Information Security)

- [ ] A.5.1.1: Information security policies approved by management
- [ ] A.6.1.2: Security clearance procedures defined
- [ ] A.7.1.1: Information security roles and responsibilities
- [ ] A.9.1.1: Access control policy documented
- [ ] A.10.1.1: Audit logging and monitoring policy
- [ ] A.12.4.1: Logging and monitoring of events

---

## 8. Security Testing

### 8.1 TLS Configuration Testing

```bash
# Test TLS version
openssl s_client -connect mqtt-broker:8883 -tls1_2
# Should fail if TLS 1.2 enforced minimum

openssl s_client -connect mqtt-broker:8883 -tls1_3
# Should succeed (TLS 1.3 supported)

# Test cipher suites
openssl s_client -connect mqtt-broker:8883 \
  -cipher 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256'
```

### 8.2 Penetration Testing

```bash
# Test MQTT authentication bypass
mosquitto_sub -h mqtt-broker -p 8883 \
  -t 'factory/edge/telemetry' \
  --insecure  # Should fail without valid certificate

# Test ACL enforcement
# Connect as user1 and try to access topic user2 can write to
mosquitto_pub -h mqtt-broker -p 8883 \
  -u user1 -P password1 \
  -t 'factory/edge/telemetry/sensor_02' \
  -m 'test' \
  --cert client.crt --key client.key \
  --cafile ca.crt
# Should fail if ACLs properly enforced
```

### 8.3 Log Integrity Testing

```bash
# Modify log file to simulate tampering
sed -i 's/CRITICAL/INFO/' /app/logs/audit/security_events.jsonl

# Run integrity check
docker-compose exec edge-ai-agent python -c "
from enterprise_audit_logger import EnterpriseAuditLogger
audit = EnterpriseAuditLogger()
result = audit.verify_log_integrity('/app/logs/audit/security_events.jsonl')
print(result)
"
# Should report: tampered_entries: 1, verified: False
```

---

## Incident Response Procedure

If a security incident is detected:

1. **Immediate Actions** (0-5 min):
   - Trigger automated isolation (container/network)
   - Send CRITICAL alert to PagerDuty
   - Snapshot system state for forensics
   - Post alert to #security-incidents Slack channel

2. **Investigation** (5-30 min):
   - Pull audit logs for event timeline
   - Check log integrity for tampering
   - Review SIEM dashboards (Splunk/ELK)
   - Identify attack vectors and compromised assets

3. **Containment** (30-60 min):
   - Execute remediation playbooks
   - Isolate compromised network segments
   - Block attacker IP addresses
   - Scale up monitoring

4. **Recovery** (1-4 hours):
   - Restore models from backups
   - Verify system integrity
   - Restart edge-ai-agent services
   - Validate detection accuracy post-recovery

5. **Post-Incident** (24 hours):
   - Root cause analysis (RCA)
   - Document lessons learned
   - Update remediation playbooks
   - Brief stakeholders

---

## References

- OWASP IoT Security Guidelines: https://owasp.org/www-project-iot-security/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- PCI-DSS Requirements: https://www.pcisecuritystandards.org/
- TLS 1.3 RFC: https://tools.ietf.org/html/rfc8446
- MQTT Security Best Practices: https://mosquitto.org/security/

---

**For security issues or vulnerability disclosures, contact:** security@zentra.rw
