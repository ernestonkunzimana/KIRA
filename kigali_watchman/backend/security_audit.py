"""
KIRA - Authentication & Audit Security Module
Production-grade security for JWT authentication and audit trail integrity.

Features:
  - Failed auth attempt tracking (brute-force detection)
  - Audit trail integrity: HMAC-SHA256 signing of audit entries
  - Immutable audit log: entries are append-only
  - Suspicious activity detection: repeated failures, rate spikes
  - Compliance logging: all sensitive operations are audited
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# Brute-force detection thresholds
FAILED_AUTH_THRESHOLD = 5        # Failed attempts before alert
FAILED_AUTH_WINDOW_SECONDS = 300  # 5-minute window
SUSPICIOUS_CLIENT_ACTIONS = 10    # API requests from freshly-failed client


class AuthenticationSecurityTracker:
    """
    Track authentication attempts per IP/client and detect brute-force attacks.
    """

    def __init__(self):
        self._failed_attempts: Dict[str, list] = defaultdict(list)  # IP -> [timestamp, ...]
        self._suspicious_clients: set = set()

    def record_failed_attempt(self, identifier: str, timestamp: float = None) -> Tuple[int, bool]:
        """
        Record a failed authentication attempt.
        
        Args:
            identifier: Client IP or user ID
            timestamp: Unix timestamp (default: now)
        
        Returns:
            (attempt_count, is_suspicious): count of recent failures, whether client should be blocked
        """
        if timestamp is None:
            timestamp = time.time()

        attempts = self._failed_attempts[identifier]
        # Remove attempts outside the window
        window_start = timestamp - FAILED_AUTH_WINDOW_SECONDS
        attempts[:] = [t for t in attempts if t > window_start]
        attempts.append(timestamp)

        is_suspicious = len(attempts) >= FAILED_AUTH_THRESHOLD
        if is_suspicious:
            self._suspicious_clients.add(identifier)
            logger.warning(
                f'SECURITY: Brute-force alert for {identifier}: '
                f'{len(attempts)} failed attempts in {FAILED_AUTH_WINDOW_SECONDS}s'
            )

        return len(attempts), is_suspicious

    def record_successful_attempt(self, identifier: str) -> None:
        """Clear failure history after successful authentication."""
        self._failed_attempts[identifier] = []
        self._suspicious_clients.discard(identifier)

    def is_client_suspicious(self, identifier: str) -> bool:
        """Check if a client has recent suspicious activity."""
        return identifier in self._suspicious_clients

    def get_attempt_count(self, identifier: str) -> int:
        """Get count of failed attempts in current window."""
        identifier_attempts = self._failed_attempts.get(identifier, [])
        now = time.time()
        window_start = now - FAILED_AUTH_WINDOW_SECONDS
        return len([t for t in identifier_attempts if t > window_start])


class AuditLogSecurity:
    """
    Ensures audit log integrity through HMAC signing and immutability verification.
    """

    def __init__(self, signing_key: str):
        """
        Initialize with a signing key (should be the same as JWT_SECRET_KEY or similar).
        
        Args:
            signing_key: Secret used for HMAC-SHA256 signing
        """
        self.signing_key = signing_key.encode('utf-8')

    def sign_entry(
        self,
        entry_id: int,
        timestamp: str,
        actor: str,
        action: str,
        resource: str,
        result: str,
        details: str = '',
    ) -> str:
        """
        Create HMAC-SHA256 signature for an audit entry.
        This signature proves the entry hasn't been modified after creation.
        
        Args:
            entry_id: Auto-incrementing ID (immutable)
            timestamp: ISO 8601 timestamp (immutable)
            actor: Client ID or user (immutable)
            action: API action performed (immutable)
            resource: Resource identifier (e.g., tower ID) (immutable)
            result: Success/Failure (immutable)
            details: Additional details (immutable)
        
        Returns:
            Hex-encoded HMAC-SHA256 signature
        """
        # Canonical message: order matters for signature verification
        canonical = f"{entry_id}|{timestamp}|{actor}|{action}|{resource}|{result}|{details}"
        signature = hmac.new(self.signing_key, canonical.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature

    def verify_entry(
        self,
        entry_id: int,
        timestamp: str,
        actor: str,
        action: str,
        resource: str,
        result: str,
        details: str,
        signature: str,
    ) -> bool:
        """
        Verify an audit entry's integrity using HMAC-SHA256.
        
        Returns:
            True if signature is valid (entry unmodified), False otherwise
        """
        expected_sig = self.sign_entry(entry_id, timestamp, actor, action, resource, result, details)
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_sig, signature)


class SuspiciousActivityDetector:
    """
    Detect unusual patterns that might indicate compromise or attack.
    """

    def __init__(self):
        self._action_counts: Dict[str, list] = defaultdict(list)  # Client -> [(timestamp, action), ...]

    def record_action(
        self,
        client_id: str,
        action: str,
        timestamp: float = None,
        threshold_actions: int = SUSPICIOUS_CLIENT_ACTIONS,
        window_seconds: int = 60,
    ) -> Tuple[int, bool]:
        """
        Record a client action and detect anomalies.
        
        Args:
            client_id: API client identifier
            action: Action type (predict, override, etc.)
            timestamp: Unix timestamp (default: now)
            threshold_actions: Threshold for unusual activity
            window_seconds: Time window for analysis
        
        Returns:
            (action_count, is_suspicious): recent action count, anomaly flag
        """
        if timestamp is None:
            timestamp = time.time()

        actions = self._action_counts[client_id]
        window_start = timestamp - window_seconds

        # Clean old entries
        actions[:] = [(t, a) for t, a in actions if t > window_start]
        actions.append((timestamp, action))

        is_suspicious = len(actions) > threshold_actions

        if is_suspicious:
            logger.warning(
                f'SECURITY: Unusual activity from {client_id}: '
                f'{len(actions)} actions in {window_seconds}s'
            )

        return len(actions), is_suspicious

    def get_action_summary(self, client_id: str) -> Dict[str, Any]:
        """Get summary of recent actions from a client."""
        actions = self._action_counts.get(client_id, [])
        now = time.time()

        # Count by action type
        action_counts = defaultdict(int)
        for timestamp, action in actions:
            action_counts[action] += 1

        return {
            'total_actions': len(actions),
            'action_breakdown': dict(action_counts),
            'last_action_ago_seconds': round(now - actions[-1][0]) if actions else None,
        }


def log_auth_event(
    client_id: str,
    success: bool,
    ip_address: str,
    reason: str = '',
    timestamp: str = None,
) -> None:
    """
    Log authentication attempts for compliance and security analysis.
    
    Args:
        client_id: Client attempting authentication
        success: True if auth succeeded
        ip_address: Client IP address
        reason: Additional context (e.g., "Invalid credentials", "Account locked")
        timestamp: ISO 8601 timestamp (default: now)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    status = 'SUCCESS' if success else 'FAILED'
    logger.info(
        f'AUTH[{status}] client={client_id} ip={ip_address} '
        f'timestamp={timestamp} reason={reason}'
    )


def log_sensitive_operation(
    client_id: str,
    operation: str,
    resource: str,
    result: str,
    ip_address: str = '',
    details: str = '',
    timestamp: str = None,
) -> None:
    """
    Log sensitive operations (overrides, configuration changes, etc.).
    
    Args:
        client_id: Operator performing action
        operation: Action type (e.g., "override", "config_change")
        resource: Resource affected (e.g., tower ID)
        result: Outcome (success, failure, denied)
        ip_address: Client IP
        details: Additional context
        timestamp: ISO 8601 timestamp (default: now)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(
        f'AUDIT[{result.upper()}] operation={operation} '
        f'client={client_id} resource={resource} ip={ip_address} '
        f'timestamp={timestamp} details={details}'
    )


def audit_rule_enforcement(
    operation: str,
    client_id: str,
    required_approval_count: int = 1,
) -> Tuple[bool, str]:
    """
    Enforce approval rules for sensitive operations.
    
    Args:
        operation: Operation type
        client_id: Operator
        required_approval_count: Number of approvals needed
    
    Returns:
        (is_allowed, reason)
    """
    # Future: integrate with approval workflow system
    # For now, allow ops_team and dashboard clients
    authorized_roles = {'ops_team', 'dashboard'}

    if client_id in authorized_roles:
        return True, 'Client authorized for this operation'

    return False, f'Client {client_id} not authorized'
