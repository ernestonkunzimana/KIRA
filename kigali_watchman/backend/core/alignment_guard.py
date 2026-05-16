"""
KIRA - AlignmentGuard
Service 2, Core Module

The AlignmentGuard is a PURE PYTHON SAFETY CLASS.
No machine learning model has input here.

The neural network proposes an action and a confidence score.
The AlignmentGuard independently decides whether that action may execute.

This is the AI alignment layer: the model's output is a proposal,
not an instruction. The guard enforces operational safety rules
that no fine-tuning or adversarial input can override.

Rules are constants reviewed and approved by the SRE/Cybersecurity team.
Any change here requires a PR, a code review, and a deployment.

LOCKOUT BACKEND: Redis is used so that all Gunicorn workers share the
same lockout state. Without Redis, each worker process has its own
independent in-memory dict, allowing the same tower to be actioned
once per worker in a single lockout window — a critical safety flaw.
"""

import os
import time
import logging
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# Actions that the system is permitted to execute autonomously without human confirmation.
# Dispatch technician always requires human confirmation regardless of confidence.
AUTONOMOUS_PERMITTED_CLASSES = {0, 1, 2}

Decision = Literal[
    'APPROVED_AUTONOMOUS',
    'APPROVED_ALERT_HUMAN',
    'BLOCKED_LOCKOUT',
    'BLOCKED_BELOW_THRESHOLD',
    'BLOCKED_NOT_PERMITTED_AUTONOMOUS',
    'BLOCKED_INVALID_INPUT',
]


@dataclass
class GuardVerdict:
    decision: Decision
    action_class: int
    action_name: str
    confidence: float
    tower_id: str
    reasoning: str
    requires_human: bool
    should_execute: bool

    def to_dict(self) -> dict:
        return {
            'decision': self.decision,
            'action_class': self.action_class,
            'action_name': self.action_name,
            'confidence': round(self.confidence, 6),
            'tower_id': self.tower_id,
            'reasoning': self.reasoning,
            'requires_human': self.requires_human,
            'should_execute': self.should_execute,
        }


class AlignmentGuard:
    """
    Evaluates whether an AI-proposed action is safe to execute autonomously.

    Lockout state is stored in Redis so ALL Gunicorn workers share it.
    Falls back to in-memory dict if Redis is unavailable (development mode).

    Usage:
        guard = AlignmentGuard(autonomous_threshold=0.88, alert_threshold=0.65)
        verdict = guard.evaluate(predicted_class=2, action_name='start_generator',
                                 confidence=0.91, tower_id='Kacyiru-A')
        if verdict.should_execute:
            actuator.execute(verdict.action_class, ...)
    """

    # Calibrated defaults — should be overridden by the 99th percentile value
    # printed by the training script after training on real data.
    AUTONOMOUS_THRESHOLD: float = 0.88
    ALERT_THRESHOLD: float = 0.65
    LOCKOUT_SECONDS: int = 600      # 10 minutes: prevents action thrashing on same tower

    def __init__(
        self,
        autonomous_threshold: float = None,
        alert_threshold: float = None,
        lockout_seconds: int = None,
        redis_url: str = None,
    ):
        self.autonomous_threshold = autonomous_threshold or self.AUTONOMOUS_THRESHOLD
        self.alert_threshold = alert_threshold or self.ALERT_THRESHOLD
        self.lockout_seconds = lockout_seconds or self.LOCKOUT_SECONDS

        # Try to connect to Redis for cross-worker shared lockout state
        self._redis: Optional[object] = None
        self._fallback_history: dict[str, list[float]] = {}

        redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        # remember redis url for lazy reconnect attempts
        self._redis_url = redis_url
        try:
            import redis
            self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
            self._redis.ping()
            logger.info(f'AlignmentGuard connected to Redis at {redis_url} — lockout is cross-worker safe.')
        except Exception as e:
            logger.warning(
                f'AlignmentGuard: Redis unavailable ({e}). '
                f'Falling back to in-memory lockout. '
                f'DO NOT use this in multi-worker production.'
            )
            self._redis = None

    def evaluate(
        self,
        predicted_class: int,
        action_name: str,
        confidence: float,
        tower_id: str,
    ) -> GuardVerdict:
        """
        Main evaluation entry point.
        Returns a GuardVerdict with a decision and reasoning.
        """
        # 1. Input sanity check
        if not isinstance(predicted_class, int):
            return GuardVerdict(
                decision='BLOCKED_INVALID_INPUT',
                action_class=-1,
                action_name=action_name,
                confidence=confidence,
                tower_id=tower_id,
                reasoning=f'Action class must be an integer, got: {type(predicted_class).__name__}',
                requires_human=True,
                should_execute=False,
            )

        if not (0.0 <= confidence <= 1.0):
            return GuardVerdict(
                decision='BLOCKED_INVALID_INPUT',
                action_class=predicted_class,
                action_name=action_name,
                confidence=confidence,
                tower_id=tower_id,
                reasoning=f'Confidence score {confidence} is outside [0.0, 1.0]. Sensor fault or adversarial input.',
                requires_human=True,
                should_execute=False,
            )

        # 2. Lockout check: has this tower been actioned in the last LOCKOUT_SECONDS?
        if self._is_locked_out(tower_id):
            return GuardVerdict(
                decision='BLOCKED_LOCKOUT',
                action_class=predicted_class,
                action_name=action_name,
                confidence=confidence,
                tower_id=tower_id,
                reasoning=(
                    f'Tower {tower_id} received an autonomous action within the last '
                    f'{self.lockout_seconds // 60} minutes. Lockout active to prevent thrashing. '
                    f'Lockout is enforced globally across all API workers via Redis.'
                ),
                requires_human=True,
                should_execute=False,
            )

        # 3. Below alert threshold: insufficient confidence, do not act, do not alert
        if confidence < self.alert_threshold:
            return GuardVerdict(
                decision='BLOCKED_BELOW_THRESHOLD',
                action_class=predicted_class,
                action_name=action_name,
                confidence=confidence,
                tower_id=tower_id,
                reasoning=(
                    f'Confidence {confidence:.4f} is below alert threshold {self.alert_threshold}. '
                    f'Insufficient certainty. No action taken, no alert sent.'
                ),
                requires_human=False,
                should_execute=False,
            )

        # 4. Alert threshold met but autonomous threshold not met: human must confirm
        if confidence < self.autonomous_threshold:
            return GuardVerdict(
                decision='APPROVED_ALERT_HUMAN',
                action_class=predicted_class,
                action_name=action_name,
                confidence=confidence,
                tower_id=tower_id,
                reasoning=(
                    f'Confidence {confidence:.4f} exceeds alert threshold {self.alert_threshold} '
                    f'but is below autonomous threshold {self.autonomous_threshold}. '
                    f'SMS alert dispatched. Human confirmation required before action.'
                ),
                requires_human=True,
                should_execute=False,
            )

        # 5. Above autonomous threshold: check if this action class is permitted autonomously
        if 'dispatch' in action_name.lower() or predicted_class not in AUTONOMOUS_PERMITTED_CLASSES:
            return GuardVerdict(
                decision='BLOCKED_NOT_PERMITTED_AUTONOMOUS',
                action_class=predicted_class,
                action_name=action_name,
                confidence=confidence,
                tower_id=tower_id,
                reasoning=(
                    f'Action "{action_name}" requires explicit human approval regardless of confidence. '
                    f'Dispatch actions are never executed autonomously.'
                ),
                requires_human=True,
                should_execute=False,
            )

        # 6. All checks passed: approve autonomous execution & record lockout
        self._record_action(tower_id)
        return GuardVerdict(
            decision='APPROVED_AUTONOMOUS',
            action_class=predicted_class,
            action_name=action_name,
            confidence=confidence,
            tower_id=tower_id,
            reasoning=(
                f'Confidence {confidence:.6f} exceeds autonomous threshold {self.autonomous_threshold}. '
                f'Action "{action_name}" is in the autonomous permit list. '
                f'Lockout clear. Executing immediately.'
            ),
            requires_human=False,
            should_execute=True,
        )

    # ---- Redis-backed lockout helpers ----

    def _lockout_key(self, tower_id: str) -> str:
        return f'kira:lockout:{tower_id}'

    def _is_locked_out(self, tower_id: str) -> bool:
        if self._redis:
            return self._redis.exists(self._lockout_key(tower_id)) == 1
        # Fallback: in-memory
        history = self._fallback_history.get(tower_id, [])
        now = time.time()
        recent = [t for t in history if now - t < self.lockout_seconds]
        self._fallback_history[tower_id] = recent
        return len(recent) > 0

    def _record_action(self, tower_id: str) -> None:
        if self._redis:
            key = self._lockout_key(tower_id)
            self._redis.setex(key, self.lockout_seconds, '1')
            logger.info(f'AlignmentGuard [Redis]: lockout set for tower {tower_id} ({self.lockout_seconds}s)')
        else:
            if tower_id not in self._fallback_history:
                self._fallback_history[tower_id] = []
            self._fallback_history[tower_id].append(time.time())
            logger.info(f'AlignmentGuard [memory]: lockout set for tower {tower_id}')

    def get_tower_lockout_status(self, tower_id: str) -> dict:
        if self._redis:
            ttl = self._redis.ttl(self._lockout_key(tower_id))
            locked = ttl > 0
            return {
                'tower_id': tower_id,
                'locked': locked,
                'seconds_remaining': ttl if locked else 0,
                'backend': 'redis',
            }
        # Fallback: in-memory
        history = self._fallback_history.get(tower_id, [])
        now = time.time()
        recent = [t for t in history if now - t < self.lockout_seconds]
        locked = len(recent) > 0
        seconds_remaining = 0
        if locked:
            oldest = min(recent)
            seconds_remaining = max(0, self.lockout_seconds - (now - oldest))
        return {
            'tower_id': tower_id,
            'locked': locked,
            'seconds_remaining': round(seconds_remaining),
            'backend': 'memory (redis unavailable)',
        }

    def check_redis(self) -> bool:
        """Verify Redis connectivity."""
        # If we don't have a redis client, attempt a lazy reconnect
        if not self._redis:
            try:
                import redis
                self._redis = redis.from_url(self._redis_url, socket_connect_timeout=2)
                self._redis.ping()
                logger.info(f'AlignmentGuard: Reconnected to Redis at {self._redis_url}')
                return True
            except Exception as e:
                logger.warning(f'AlignmentGuard: Redis reconnect failed: {e}')
                self._redis = None
                return False

        try:
            self._redis.ping()
            return True
        except Exception as e:
            logger.error(f'Health Check: Redis failure: {e}')
            return False
