"""
Tests: Security & Audit Module
Verifies brute-force detection, audit integrity, and suspicious activity detection.

Run: pytest tests/test_security_audit.py -v
"""

import pytest
import time
import hmac
import hashlib

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from security_audit import (
    AuthenticationSecurityTracker,
    AuditLogSecurity,
    SuspiciousActivityDetector,
    FAILED_AUTH_THRESHOLD,
    FAILED_AUTH_WINDOW_SECONDS,
)


class TestAuthenticationSecurityTracker:

    def test_record_single_failed_attempt(self):
        """Recording a failed attempt should increment count."""
        tracker = AuthenticationSecurityTracker()
        count, is_suspicious = tracker.record_failed_attempt('192.168.1.1')
        
        assert count == 1
        assert is_suspicious is False

    def test_repeated_failures_trigger_alert(self):
        """Multiple failures within time window should trigger alert."""
        tracker = AuthenticationSecurityTracker()
        
        for i in range(FAILED_AUTH_THRESHOLD - 1):
            count, is_suspicious = tracker.record_failed_attempt('192.168.1.1')
            assert is_suspicious is False
        
        # One more failure should trigger alert
        count, is_suspicious = tracker.record_failed_attempt('192.168.1.1')
        assert count >= FAILED_AUTH_THRESHOLD
        assert is_suspicious is True

    def test_failures_outside_window_ignored(self):
        """Failed attempts outside the time window should not count."""
        tracker = AuthenticationSecurityTracker()
        
        # Record failures in the past (outside window)
        past_time = time.time() - FAILED_AUTH_WINDOW_SECONDS - 100
        for _ in range(10):
            tracker.record_failed_attempt('192.168.1.1', timestamp=past_time)
        
        # Current failures should start fresh
        count, is_suspicious = tracker.record_failed_attempt('192.168.1.1')
        assert count == 1
        assert is_suspicious is False

    def test_successful_attempt_clears_history(self):
        """Successful auth should clear failure history."""
        tracker = AuthenticationSecurityTracker()
        
        # Record some failures
        for _ in range(3):
            tracker.record_failed_attempt('192.168.1.1')
        
        # Successful auth clears history
        tracker.record_successful_attempt('192.168.1.1')
        assert tracker.is_client_suspicious('192.168.1.1') is False
        assert tracker.get_attempt_count('192.168.1.1') == 0

    def test_different_ips_tracked_independently(self):
        """Different IPs should have independent failure tracking."""
        tracker = AuthenticationSecurityTracker()
        
        # IP 1: record failures
        for _ in range(FAILED_AUTH_THRESHOLD):
            tracker.record_failed_attempt('192.168.1.1')
        
        # IP 2: should not be affected
        count, is_suspicious = tracker.record_failed_attempt('192.168.1.2')
        assert count == 1
        assert is_suspicious is False

    def test_is_client_suspicious_flag(self):
        """is_client_suspicious should reflect brute-force alert status."""
        tracker = AuthenticationSecurityTracker()
        
        assert tracker.is_client_suspicious('192.168.1.1') is False
        
        # Record enough failures to trigger alert
        for _ in range(FAILED_AUTH_THRESHOLD):
            tracker.record_failed_attempt('192.168.1.1')
        
        assert tracker.is_client_suspicious('192.168.1.1') is True


class TestAuditLogSecurity:

    def test_audit_entry_signing(self):
        """Audit entries should be properly signed with HMAC-SHA256."""
        security = AuditLogSecurity('test-secret-key')
        
        signature = security.sign_entry(
            entry_id=1,
            timestamp='2026-05-11T12:00:00Z',
            actor='operator1',
            action='override',
            resource='Gasabo-A',
            result='success',
            details='Manual intervention'
        )
        
        # Signature should be a hex string (64 chars for SHA256)
        assert len(signature) == 64
        assert all(c in '0123456789abcdef' for c in signature)

    def test_audit_entry_verification_valid(self):
        """Valid signatures should pass verification."""
        security = AuditLogSecurity('test-secret-key')
        
        signature = security.sign_entry(
            entry_id=1,
            timestamp='2026-05-11T12:00:00Z',
            actor='operator1',
            action='override',
            resource='Gasabo-A',
            result='success',
            details='Manual intervention'
        )
        
        # Verification should succeed
        is_valid = security.verify_entry(
            entry_id=1,
            timestamp='2026-05-11T12:00:00Z',
            actor='operator1',
            action='override',
            resource='Gasabo-A',
            result='success',
            details='Manual intervention',
            signature=signature
        )
        assert is_valid is True

    def test_audit_entry_verification_invalid_data(self):
        """Modified audit data should fail signature verification."""
        security = AuditLogSecurity('test-secret-key')
        
        signature = security.sign_entry(
            entry_id=1,
            timestamp='2026-05-11T12:00:00Z',
            actor='operator1',
            action='override',
            resource='Gasabo-A',
            result='success',
            details='Manual intervention'
        )
        
        # Try to verify with different resource (tampering)
        is_valid = security.verify_entry(
            entry_id=1,
            timestamp='2026-05-11T12:00:00Z',
            actor='operator1',
            action='override',
            resource='Nyarugenge-A',  # CHANGED
            result='success',
            details='Manual intervention',
            signature=signature
        )
        assert is_valid is False

    def test_audit_entry_verification_invalid_signature(self):
        """Invalid signature should fail verification."""
        security = AuditLogSecurity('test-secret-key')
        
        # Fake signature
        fake_signature = 'aaaa' * 16  # 64 hex chars but wrong value
        
        is_valid = security.verify_entry(
            entry_id=1,
            timestamp='2026-05-11T12:00:00Z',
            actor='operator1',
            action='override',
            resource='Gasabo-A',
            result='success',
            details='Manual intervention',
            signature=fake_signature
        )
        assert is_valid is False

    def test_different_secrets_produce_different_signatures(self):
        """Same data with different secrets should produce different signatures."""
        security1 = AuditLogSecurity('secret1')
        security2 = AuditLogSecurity('secret2')
        
        sig1 = security1.sign_entry(1, '2026-05-11T12:00:00Z', 'op1', 'override', 'tower', 'success', '')
        sig2 = security2.sign_entry(1, '2026-05-11T12:00:00Z', 'op1', 'override', 'tower', 'success', '')
        
        assert sig1 != sig2


class TestSuspiciousActivityDetector:

    def test_record_action_normal_rate(self):
        """Normal action rate should not be flagged as suspicious."""
        detector = SuspiciousActivityDetector()
        
        for _ in range(5):
            count, is_suspicious = detector.record_action('client1', 'predict')
            assert is_suspicious is False
        
        assert count == 5

    def test_record_action_high_rate_flag(self):
        """High action rate should be flagged as suspicious."""
        detector = SuspiciousActivityDetector()
        
        # Record 11 actions (threshold is 10)
        for i in range(11):
            count, is_suspicious = detector.record_action('client1', 'predict', threshold_actions=10)
        
        assert count == 11
        assert is_suspicious is True

    def test_action_summary(self):
        """get_action_summary should provide breakdown of actions."""
        detector = SuspiciousActivityDetector()
        
        detector.record_action('client1', 'predict')
        detector.record_action('client1', 'predict')
        detector.record_action('client1', 'override')
        
        summary = detector.get_action_summary('client1')
        assert summary['total_actions'] == 3
        assert summary['action_breakdown']['predict'] == 2
        assert summary['action_breakdown']['override'] == 1

    def test_different_clients_tracked_independently(self):
        """Actions from different clients should be tracked independently."""
        detector = SuspiciousActivityDetector()
        
        # Client 1: many actions
        for _ in range(12):
            detector.record_action('client1', 'predict', threshold_actions=10)
        
        # Client 2: few actions
        count, is_suspicious = detector.record_action('client2', 'predict', threshold_actions=10)
        assert count == 1
        assert is_suspicious is False
