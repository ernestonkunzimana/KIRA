"""
Tests: AlignmentGuard
Verifies all decision branches, Redis lockout (with mock), and threshold logic.

Run: pytest tests/test_alignment_guard.py -v
"""

import time
import pytest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.alignment_guard import AlignmentGuard, AUTONOMOUS_PERMITTED_CLASSES


# ---- Fixtures ----

@pytest.fixture
def guard_no_redis():
    """AlignmentGuard with in-memory fallback (no Redis required for unit tests)."""
    with patch('core.alignment_guard.os.environ.get', return_value=None):
        g = AlignmentGuard(autonomous_threshold=0.88, alert_threshold=0.65, lockout_seconds=60)
        g._redis = None  # Force in-memory fallback
        return g


@pytest.fixture
def guard_with_mock_redis():
    """AlignmentGuard with a mocked Redis client."""
    g = AlignmentGuard.__new__(AlignmentGuard)
    g.autonomous_threshold = 0.88
    g.alert_threshold = 0.65
    g.lockout_seconds = 60
    g._fallback_history = {}
    g._redis = MagicMock()
    g._redis.exists.return_value = 0   # Not locked by default
    g._redis.setex.return_value = True
    return g


# ============================================================
# Basic Decision Path Tests
# ============================================================

class TestDecisionPaths:

    def test_below_alert_threshold_is_blocked(self, guard_no_redis):
        """Confidence below alert threshold must never produce an action."""
        verdict = guard_no_redis.evaluate(
            predicted_class=2, action_name='start_generator',
            confidence=0.40, tower_id='Gasabo-A'
        )
        assert verdict.decision == 'BLOCKED_BELOW_THRESHOLD'
        assert verdict.should_execute is False
        assert verdict.requires_human is False

    def test_above_alert_below_autonomous_requires_human(self, guard_no_redis):
        """Confidence in alert zone must trigger APPROVED_ALERT_HUMAN."""
        verdict = guard_no_redis.evaluate(
            predicted_class=1, action_name='switch_to_solar',
            confidence=0.75, tower_id='Gasabo-B'
        )
        assert verdict.decision == 'APPROVED_ALERT_HUMAN'
        assert verdict.should_execute is False
        assert verdict.requires_human is True

    def test_above_autonomous_threshold_executes(self, guard_no_redis):
        """Confidence above autonomous threshold on a permitted class must execute."""
        verdict = guard_no_redis.evaluate(
            predicted_class=1, action_name='switch_to_solar',
            confidence=0.95, tower_id='Kicukiro-A'
        )
        assert verdict.decision == 'APPROVED_AUTONOMOUS'
        assert verdict.should_execute is True
        assert verdict.requires_human is False

    def test_dispatch_action_never_autonomous(self, guard_no_redis):
        """Dispatch actions must always require human regardless of confidence."""
        verdict = guard_no_redis.evaluate(
            predicted_class=3, action_name='dispatch_technician',
            confidence=0.999, tower_id='Nyarugenge-A'
        )
        assert verdict.decision == 'BLOCKED_NOT_PERMITTED_AUTONOMOUS'
        assert verdict.should_execute is False
        assert verdict.requires_human is True

    def test_invalid_confidence_above_one_blocked(self, guard_no_redis):
        """Confidence > 1.0 is physically impossible — must be rejected."""
        verdict = guard_no_redis.evaluate(
            predicted_class=0, action_name='healthy_no_action',
            confidence=1.5, tower_id='Gasabo-A'
        )
        assert verdict.decision == 'BLOCKED_INVALID_INPUT'
        assert verdict.should_execute is False

    def test_invalid_confidence_negative_blocked(self, guard_no_redis):
        verdict = guard_no_redis.evaluate(
            predicted_class=0, action_name='healthy_no_action',
            confidence=-0.1, tower_id='Gasabo-A'
        )
        assert verdict.decision == 'BLOCKED_INVALID_INPUT'

    def test_non_integer_class_blocked(self, guard_no_redis):
        verdict = guard_no_redis.evaluate(
            predicted_class='solar',  # type: ignore
            action_name='switch_to_solar',
            confidence=0.95, tower_id='Gasabo-A'
        )
        assert verdict.decision == 'BLOCKED_INVALID_INPUT'


# ============================================================
# Lockout Tests
# ============================================================

class TestLockoutInMemory:

    def test_lockout_triggered_after_first_action(self, guard_no_redis):
        """After an autonomous action, the same tower must be locked out."""
        tower = 'Gasabo-Test'
        # First action should succeed
        v1 = guard_no_redis.evaluate(
            predicted_class=1, action_name='switch_to_solar',
            confidence=0.95, tower_id=tower
        )
        assert v1.decision == 'APPROVED_AUTONOMOUS'

        # Immediate second action should be blocked
        v2 = guard_no_redis.evaluate(
            predicted_class=1, action_name='switch_to_solar',
            confidence=0.99, tower_id=tower
        )
        assert v2.decision == 'BLOCKED_LOCKOUT'
        assert v2.should_execute is False

    def test_lockout_does_not_affect_different_tower(self, guard_no_redis):
        """Lockout on Tower A must not block Tower B."""
        guard_no_redis.evaluate(
            predicted_class=2, action_name='start_generator',
            confidence=0.95, tower_id='Tower-A'
        )
        v = guard_no_redis.evaluate(
            predicted_class=2, action_name='start_generator',
            confidence=0.95, tower_id='Tower-B'
        )
        assert v.decision == 'APPROVED_AUTONOMOUS'


class TestLockoutRedis:

    def test_redis_lockout_prevents_second_action(self, guard_with_mock_redis):
        """With Redis, the lockout key lookup must gate autonomous actions."""
        tower = 'Kicukiro-Redis'

        # First call: Redis says NOT locked → should succeed
        guard_with_mock_redis._redis.exists.return_value = 0
        v1 = guard_with_mock_redis.evaluate(
            predicted_class=1, action_name='switch_to_solar',
            confidence=0.95, tower_id=tower
        )
        assert v1.decision == 'APPROVED_AUTONOMOUS'
        # Verify setex was called to SET the lockout
        guard_with_mock_redis._redis.setex.assert_called_once()

        # Second call: Redis now says IS locked
        guard_with_mock_redis._redis.exists.return_value = 1
        v2 = guard_with_mock_redis.evaluate(
            predicted_class=1, action_name='switch_to_solar',
            confidence=0.95, tower_id=tower
        )
        assert v2.decision == 'BLOCKED_LOCKOUT'

    def test_redis_key_format(self, guard_with_mock_redis):
        """Redis key must include the tower_id so locks are per-tower."""
        key = guard_with_mock_redis._lockout_key('Nyarugenge-A')
        assert 'Nyarugenge-A' in key
        assert 'kira' in key.lower() or 'lockout' in key.lower()


# ============================================================
# Status reporting
# ============================================================

class TestStatusReporting:

    def test_lockout_status_returns_correct_structure(self, guard_with_mock_redis):
        guard_with_mock_redis._redis.ttl.return_value = 350
        status = guard_with_mock_redis.get_tower_lockout_status('Gasabo-X')
        assert 'tower_id' in status
        assert 'locked' in status
        assert 'seconds_remaining' in status
        assert status['locked'] is True
        assert status['seconds_remaining'] == 350

    def test_unlocked_tower_shows_zero_remaining(self, guard_with_mock_redis):
        guard_with_mock_redis._redis.ttl.return_value = -2  # Redis returns -2 for non-existent key
        status = guard_with_mock_redis.get_tower_lockout_status('Fresh-Tower')
        assert status['locked'] is False
