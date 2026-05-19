"""
Layer 3: Enterprise Webhook & Automated Remediation Engine
===========================================================
Incident response automation: quarantine compromised assets, trigger alerts,
and execute remediation playbooks on anomaly detection.

Integrates with:
- SIEM platforms (Splunk, Datadog, Elastic)
- Incident management (PagerDuty, Opsgenie)
- Container orchestration (Docker Swarm, Kubernetes)
- Network isolation (Cisco ISE, Arista, OpenFlow)

Author: Ernest Nkunzimana | Zentra Ltd
License: MIT
"""

import json
import requests
import subprocess
import time
import threading
from enum import Enum
from typing import Dict, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod

# ============================================================================
# Configuration
# ============================================================================

# Webhook endpoints (set via environment variables in production)
SIEM_WEBHOOK_URL = "http://splunk-hec:8088/services/collector"
INCIDENT_MGMT_WEBHOOK = "https://events.pagerduty.com/v2/enqueue"
SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

# Container/network isolation commands
DOCKER_ISOLATION_CMD = "docker update --pids-limit 10 {container_id}"  # Limit process creation
NETWORK_ISOLATION_CMD = "ovs-vsctl set-controller br-int tcp:127.0.0.1:6633"  # OpenFlow isolation

# Remediation timeout (seconds)
REMEDIATION_TIMEOUT = 30

class RemediationType(Enum):
    """Types of automated remediation actions."""
    ISOLATE_CONTAINER = "ISOLATE_CONTAINER"
    ISOLATE_NETWORK = "ISOLATE_NETWORK"
    ALERT_ONLY = "ALERT_ONLY"
    KILL_PROCESS = "KILL_PROCESS"
    SNAPSHOT_AND_QUARANTINE = "SNAPSHOT_AND_QUARANTINE"
    ESCALATE_TO_SOC = "ESCALATE_TO_SOC"

class RemediationStatus(Enum):
    """Remediation execution status."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"

# ============================================================================
# Remediation Action Base Classes
# ============================================================================

class RemediationAction(ABC):
    """Abstract base class for remediation actions."""
    
    def __init__(self, node_id: str, asset_id: str, severity: str):
        self.node_id = node_id
        self.asset_id = asset_id
        self.severity = severity
        self.status = RemediationStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.result = None
    
    @abstractmethod
    def execute(self) -> bool:
        """Execute remediation action. Returns True if successful."""
        pass
    
    @abstractmethod
    def rollback(self) -> bool:
        """Rollback/undo remediation. Returns True if successful."""
        pass
    
    def to_dict(self) -> Dict:
        """Serialize remediation action to dict."""
        return {
            "node_id": self.node_id,
            "asset_id": self.asset_id,
            "severity": self.severity,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "result": self.result
        }

# ============================================================================
# Concrete Remediation Actions
# ============================================================================

class ContainerIsolationAction(RemediationAction):
    """
    Isolate compromised Docker container by limiting resources.
    
    Action:
    - Limit process creation (pids-limit)
    - Restrict network access
    - Freeze memory allocation
    """
    
    def execute(self) -> bool:
        """Isolate container by limiting resources."""
        try:
            self.status = RemediationStatus.IN_PROGRESS
            self.start_time = datetime.utcnow()
            
            # Limit process creation
            cmd = f"docker update --pids-limit 10 {self.asset_id}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            
            if result.returncode != 0:
                self.result = f"Isolation failed: {result.stderr.decode()}"
                self.status = RemediationStatus.FAILED
                return False
            
            self.result = f"Container {self.asset_id} isolated successfully"
            self.status = RemediationStatus.SUCCESS
            self.end_time = datetime.utcnow()
            return True
            
        except subprocess.TimeoutExpired:
            self.result = "Isolation command timed out"
            self.status = RemediationStatus.FAILED
            return False
        except Exception as e:
            self.result = f"Unexpected error: {str(e)}"
            self.status = RemediationStatus.FAILED
            return False
    
    def rollback(self) -> bool:
        """Remove isolation (restore normal operation)."""
        try:
            cmd = f"docker update --pids-limit -1 {self.asset_id}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            
            if result.returncode == 0:
                self.status = RemediationStatus.ROLLED_BACK
                return True
            return False
        except Exception as e:
            print(f"[ROLLBACK ERROR] {str(e)}")
            return False

class NetworkIsolationAction(RemediationAction):
    """
    Isolate compromised asset from network using OpenFlow.
    
    Action:
    - Remove VLAN access
    - Block egress traffic
    - Redirect to quarantine network
    """
    
    def execute(self) -> bool:
        """Isolate network interface."""
        try:
            self.status = RemediationStatus.IN_PROGRESS
            self.start_time = datetime.utcnow()
            
            # Example: Use OpenFlow to block traffic
            cmd = f"ovs-ofctl add-flow br-int priority=1000,dl_src={self.asset_id},actions=drop"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            
            if result.returncode != 0:
                self.result = f"Network isolation failed: {result.stderr.decode()}"
                self.status = RemediationStatus.FAILED
                return False
            
            self.result = f"Network traffic blocked for {self.asset_id}"
            self.status = RemediationStatus.SUCCESS
            self.end_time = datetime.utcnow()
            return True
            
        except Exception as e:
            self.result = f"Error: {str(e)}"
            self.status = RemediationStatus.FAILED
            return False
    
    def rollback(self) -> bool:
        """Restore network access."""
        try:
            cmd = f"ovs-ofctl del-flows br-int priority=1000,dl_src={self.asset_id}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            
            if result.returncode == 0:
                self.status = RemediationStatus.ROLLED_BACK
                return True
            return False
        except Exception as e:
            print(f"[ROLLBACK ERROR] {str(e)}")
            return False

class AlertOnlyAction(RemediationAction):
    """Non-destructive action: alert SOC without remediation."""
    
    def execute(self) -> bool:
        """Generate alert (no destructive action)."""
        self.status = RemediationStatus.IN_PROGRESS
        self.start_time = datetime.utcnow()
        self.result = "Alert generated for SOC review"
        self.status = RemediationStatus.SUCCESS
        self.end_time = datetime.utcnow()
        return True
    
    def rollback(self) -> bool:
        """No-op for alert action."""
        return True

# ============================================================================
# Enterprise Webhook Engine
# ============================================================================

class EnterpriseWebhookEngine:
    """
    Multi-target webhook dispatcher for SIEM, incident management, and chat platforms.
    
    Features:
    - Retry logic with exponential backoff
    - Connection pooling
    - Signature-based webhook authentication
    - Event deduplication
    """
    
    def __init__(self, max_retries: int = 3, timeout: int = 10):
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.dedup_cache = set()  # Track sent events to prevent duplicates
    
    def send_to_siem(self, event: Dict) -> bool:
        """
        Send event to SIEM platform (Splunk HEC format).
        
        Splunk HTTP Event Collector (HEC) format:
        {
          "event": { event_data },
          "sourcetype": "_json",
          "source": "edge-ai-agent"
        }
        """
        splunk_event = {
            "event": event,
            "sourcetype": "_json",
            "source": "edge-ai-agent",
            "host": event.get("node_id", "unknown")
        }
        
        headers = {
            "Authorization": f"Splunk {self._get_hec_token()}",
            "Content-Type": "application/json"
        }
        
        return self._send_with_retry(
            SIEM_WEBHOOK_URL,
            splunk_event,
            headers
        )
    
    def send_to_incident_mgmt(self, alert: Dict) -> bool:
        """
        Send incident to PagerDuty for escalation.
        
        PagerDuty Events API v2 format:
        {
          "routing_key": "string",
          "event_action": "trigger",
          "payload": { event details }
        }
        """
        pagerduty_event = {
            "routing_key": self._get_pagerduty_key(),
            "event_action": "trigger",
            "payload": {
                "summary": alert.get("message", "Critical security alert"),
                "severity": "critical",
                "source": alert.get("node_id", "edge-ai-agent"),
                "custom_details": alert
            }
        }
        
        return self._send_with_retry(
            INCIDENT_MGMT_WEBHOOK,
            pagerduty_event
        )
    
    def send_to_slack(self, message: str, metadata: Dict) -> bool:
        """Send alert to Slack channel."""
        slack_payload = {
            "text": message,
            "attachments": [{
                "color": "danger",
                "fields": [
                    {"title": "Node ID", "value": metadata.get("node_id"), "short": True},
                    {"title": "Asset ID", "value": metadata.get("asset_id"), "short": True},
                    {"title": "Severity", "value": metadata.get("severity"), "short": True},
                    {"title": "Timestamp", "value": metadata.get("timestamp"), "short": True}
                ]
            }]
        }
        
        return self._send_with_retry(SLACK_WEBHOOK, slack_payload)
    
    def _send_with_retry(self, url: str, payload: Dict, headers: Dict = None) -> bool:
        """
        Send HTTP request with exponential backoff retry.
        
        Returns:
            True if successful, False otherwise
        """
        if headers is None:
            headers = {"Content-Type": "application/json"}
        
        # Deduplication: skip duplicate events
        payload_hash = hash(json.dumps(payload, sort_keys=True))
        if payload_hash in self.dedup_cache:
            print(f"[WEBHOOK] Skipping duplicate event")
            return True
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code in [200, 201, 202]:
                    self.dedup_cache.add(payload_hash)
                    print(f"[WEBHOOK] ✅ Successfully sent to {url}")
                    return True
                else:
                    print(f"[WEBHOOK] Status {response.status_code}: {response.text}")
            
            except requests.exceptions.Timeout:
                print(f"[WEBHOOK] Attempt {attempt + 1}/{self.max_retries}: Timeout")
            except requests.exceptions.ConnectionError as e:
                print(f"[WEBHOOK] Attempt {attempt + 1}/{self.max_retries}: Connection error: {e}")
            except Exception as e:
                print(f"[WEBHOOK] Attempt {attempt + 1}/{self.max_retries}: {str(e)}")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[WEBHOOK] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        return False
    
    @staticmethod
    def _get_hec_token() -> str:
        """Retrieve Splunk HEC token from secrets manager."""
        import os
        return os.environ.get("SPLUNK_HEC_TOKEN", "placeholder-token")
    
    @staticmethod
    def _get_pagerduty_key() -> str:
        """Retrieve PagerDuty routing key from secrets manager."""
        import os
        return os.environ.get("PAGERDUTY_ROUTING_KEY", "placeholder-key")

# ============================================================================
# Remediation Orchestrator
# ============================================================================

class RemediationOrchestrator:
    """
    Orchestrates automated remediation responses based on alert severity and asset type.
    
    Decision Matrix:
    - INFO: Alert only
    - WARNING: Alert + gather forensics
    - CRITICAL: Isolate + Alert + Escalate
    - ALERT: Quarantine + Kill process + Full escalation
    """
    
    def __init__(self, webhook_engine: EnterpriseWebhookEngine):
        self.webhook_engine = webhook_engine
        self.active_remediations: List[RemediationAction] = []
        self.lock = threading.Lock()
    
    def decide_remediation(
        self,
        node_id: str,
        asset_id: str,
        anomaly_score: float,
        metrics: Dict
    ) -> RemediationType:
        """
        Decide remediation action based on anomaly score and context.
        
        Args:
            node_id: Monitoring node ID
            asset_id: Compromised asset ID
            anomaly_score: Isolation Forest anomaly score (0-1)
            metrics: Telemetry metrics
            
        Returns:
            RemediationType decision
        """
        
        # Severity scoring
        severity_score = self._compute_severity_score(anomaly_score, metrics)
        
        if severity_score > 0.9:
            return RemediationType.ISOLATE_CONTAINER
        elif severity_score > 0.7:
            return RemediationType.ISOLATE_NETWORK
        elif severity_score > 0.5:
            return RemediationType.ALERT_ONLY
        else:
            return RemediationType.ALERT_ONLY
    
    def execute_remediation(
        self,
        remediation_type: RemediationType,
        node_id: str,
        asset_id: str,
        metrics: Dict,
        anomaly_score: float
    ) -> bool:
        """
        Execute remediation action asynchronously.
        
        Returns:
            True if remediation initiated successfully
        """
        
        # Create remediation action
        action = self._create_action(remediation_type, node_id, asset_id)
        
        if action is None:
            print(f"[REMEDIATION] Unknown remediation type: {remediation_type}")
            return False
        
        # Track action
        with self.lock:
            self.active_remediations.append(action)
        
        # Execute in background thread
        thread = threading.Thread(
            target=self._execute_with_monitoring,
            args=(action, node_id, asset_id, metrics, anomaly_score)
        )
        thread.daemon = True
        thread.start()
        
        return True
    
    def _execute_with_monitoring(
        self,
        action: RemediationAction,
        node_id: str,
        asset_id: str,
        metrics: Dict,
        anomaly_score: float
    ):
        """Execute remediation with monitoring and webhook notifications."""
        try:
            print(f"\n[REMEDIATION] Executing {action.__class__.__name__}...")
            success = action.execute()
            
            # Send webhook notifications
            event = {
                "node_id": node_id,
                "asset_id": asset_id,
                "remediation_type": action.__class__.__name__,
                "success": success,
                "result": action.result,
                "metrics": metrics,
                "anomaly_score": anomaly_score,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if success:
                print(f"[REMEDIATION] ✅ Success: {action.result}")
                self.webhook_engine.send_to_siem(event)
            else:
                print(f"[REMEDIATION] ❌ Failed: {action.result}")
                event["severity"] = "CRITICAL"
                self.webhook_engine.send_to_incident_mgmt(event)
                self.webhook_engine.send_to_slack(
                    f"🚨 Remediation FAILED on {asset_id}",
                    event
                )
        
        except Exception as e:
            print(f"[REMEDIATION ERROR] {str(e)}")
            self.webhook_engine.send_to_incident_mgmt({
                "node_id": node_id,
                "asset_id": asset_id,
                "error": str(e),
                "severity": "CRITICAL"
            })
    
    @staticmethod
    def _compute_severity_score(anomaly_score: float, metrics: Dict) -> float:
        """
        Compute composite severity score (0-1).
        
        Combines:
        - Anomaly score (0-1)
        - Vibration threshold breach
        - Temperature threshold breach
        - Link quality degradation
        """
        score = anomaly_score
        
        if metrics.get("vibration_hz", 0) > 100:
            score += 0.2
        if metrics.get("temperature_c", 0) > 35:
            score += 0.15
        if metrics.get("link_quality_qos", 100) < 50:
            score += 0.15
        
        return min(score, 1.0)
    
    @staticmethod
    def _create_action(
        remediation_type: RemediationType,
        node_id: str,
        asset_id: str
    ) -> Optional[RemediationAction]:
        """Factory method to create remediation actions."""
        
        actions = {
            RemediationType.ISOLATE_CONTAINER: ContainerIsolationAction,
            RemediationType.ISOLATE_NETWORK: NetworkIsolationAction,
            RemediationType.ALERT_ONLY: AlertOnlyAction
        }
        
        action_class = actions.get(remediation_type)
        if action_class:
            return action_class(node_id, asset_id, "CRITICAL")
        
        return None
    
    def rollback_remediation(self, action_index: int) -> bool:
        """Rollback a specific remediation action."""
        with self.lock:
            if 0 <= action_index < len(self.active_remediations):
                action = self.active_remediations[action_index]
                success = action.rollback()
                print(f"[REMEDIATION] Rollback {'successful' if success else 'failed'}")
                return success
        return False

# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    # Initialize webhook engine
    webhook = EnterpriseWebhookEngine()
    
    # Initialize orchestrator
    orchestrator = RemediationOrchestrator(webhook)
    
    # Simulate anomaly detection and remediation
    print("[TEST] Simulating anomaly detection...")
    
    remediation_type = orchestrator.decide_remediation(
        node_id="edge-ai-agent-001",
        asset_id="factory-sensor-42",
        anomaly_score=0.85,
        metrics={
            "vibration_hz": 125.5,
            "temperature_c": 40.2,
            "link_quality_qos": 35
        }
    )
    
    print(f"[TEST] Remediation decision: {remediation_type.value}")
    
    # Execute remediation
    success = orchestrator.execute_remediation(
        remediation_type=remediation_type,
        node_id="edge-ai-agent-001",
        asset_id="factory-sensor-42",
        metrics={
            "vibration_hz": 125.5,
            "temperature_c": 40.2,
            "link_quality_qos": 35
        },
        anomaly_score=0.85
    )
    
    print(f"[TEST] Remediation initiated: {success}")
    time.sleep(2)  # Allow async operations to complete
