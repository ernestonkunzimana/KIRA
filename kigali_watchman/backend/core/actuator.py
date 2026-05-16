"""
KIRA - Actuator
Service 2, Core Module

Executes approved actions from the AlignmentGuard.
In production this triggers real hardware commands via MQTT or vendor APIs.
In simulation mode (default) it logs the action and returns a success response.

The audit trail is written here for every action, regardless of mode.
"""

import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---- Action handlers ----
# In production: replace simulation_mode=True with actual MQTT publish / REST call
# to the hardware controller. The interface does not change.


class Actuator:
    """
    Dispatches approved actions to infrastructure.

    Action handlers are intentionally separate methods so each can be
    replaced with a real hardware call in production without touching the
    AlignmentGuard or the API layer.
    """

    def __init__(self, audit_db_path: str, simulation_mode: bool = True,
                 twilio_config: dict = None):
        self.simulation_mode = simulation_mode
        self.audit_db_path = audit_db_path
        self.twilio_config = twilio_config or {}
        self._init_db()
        mode = 'SIMULATION' if simulation_mode else 'PRODUCTION'
        logger.info(f'Actuator initialized in {mode} mode')

    def execute(
        self,
        action_class: int,
        action_name: str,
        tower_id: str,
        district: str,
        confidence: float,
        shap_explanation: Optional[dict],
        triggered_by: str = 'AUTONOMOUS',
    ) -> dict:
        """
        Execute an approved action and write to audit log.

        Args:
            action_class:     0-3 from the classifier
            action_name:      human-readable action string
            tower_id:         e.g. 'Kacyiru-A'
            district:         'Gasabo' | 'Nyarugenge' | 'Kicukiro'
            confidence:       model confidence at time of action
            shap_explanation: SHAP human-readable explanation dict
            triggered_by:     'AUTONOMOUS' | 'HUMAN_OVERRIDE' | 'MANUAL_TEST'

        Returns:
            dict with action result and audit_id
        """
        handler_map = {
            0: self._no_action,
            1: self._switch_solar,
            2: self._start_generator,
            3: self._dispatch_technician,
        }

        handler = handler_map.get(action_class)
        if handler is None:
            raise ValueError(f'Unknown action class: {action_class}')

        start_ts = datetime.now(timezone.utc)
        hw_result = handler(tower_id=tower_id, district=district)

        execution_ms = int((time.time() - start_ts.timestamp()) * 1000)

        shap_text = (
            shap_explanation.get('human_readable', '')
            if shap_explanation else 'SHAP not available'
        )

        audit_id = self._write_audit(
            timestamp=start_ts.isoformat(),
            tower_id=tower_id,
            district=district,
            action_class=action_class,
            action_name=action_name,
            confidence=confidence,
            triggered_by=triggered_by,
            hw_result=hw_result,
            execution_ms=execution_ms,
            shap_explanation=shap_text,
        )

        result = {
            'audit_id': audit_id,
            'status': 'executed',
            'action_name': action_name,
            'tower_id': tower_id,
            'district': district,
            'triggered_by': triggered_by,
            'confidence': round(confidence, 6),
            'execution_ms': execution_ms,
            'hardware_result': hw_result,
            'explanation': shap_text,
            'timestamp': start_ts.isoformat(),
        }

        logger.info(
            f'ACTUATOR [{triggered_by}] | {action_name} | tower={tower_id} '
            f'| conf={confidence:.4f} | audit_id={audit_id}'
        )

        return result

    # ---- Action Handlers ----

    def _no_action(self, tower_id: str, district: str) -> dict:
        return {'command': 'none', 'status': 'ok', 'message': 'Tower healthy, no action required.'}

    def _switch_solar(self, tower_id: str, district: str) -> dict:
        if self.simulation_mode:
            logger.info(f'[SIM] SOLAR SWITCH: Tower {tower_id} ({district}) -> solar backup engaged')
            return {
                'command': 'switch_to_solar',
                'status': 'ok',
                'message': f'Tower {tower_id} switched to solar backup. Grid down.',
            }
        # PRODUCTION: replace with actual MQTT publish to tower controller
        # mqtt_client.publish(f'kira/tower/{tower_id}/command', json.dumps({'action': 'solar_on'}))
        raise NotImplementedError('Production hardware command not yet configured')

    def _start_generator(self, tower_id: str, district: str) -> dict:
        if self.simulation_mode:
            logger.info(f'[SIM] GENERATOR START: Tower {tower_id} ({district}) -> generator engaged')
            return {
                'command': 'start_generator',
                'status': 'ok',
                'message': f'Tower {tower_id} generator started. Battery critical.',
            }
        raise NotImplementedError('Production hardware command not yet configured')

    def _dispatch_technician(self, tower_id: str, district: str) -> dict:
        """
        Dispatch technician is always a human-confirmed action.
        This method should only be called after human approval.
        It sends an SMS via Twilio and logs the dispatch.
        """
        msg = (
            f'[KIRA ALERT] Tower {tower_id} in {district} requires immediate attention. '
            f'Battery critical or prolonged outage detected. Dispatch technician.'
        )
        sms_sent = self._send_sms(msg)
        return {
            'command': 'dispatch_technician',
            'status': 'ok',
            'message': msg,
            'sms_sent': sms_sent,
        }

    def dispatch_alert(
        self,
        message: str,
        tower_id: str,
        district: str,
        confidence: float,
        shap_explanation: Optional[dict] = None,
        triggered_by: str = 'ALERT_ONLY',
    ) -> dict:
        """
        Public interface for sending an SMS alert AND logging it to the audit trail.
        Use this instead of calling _send_sms() directly from app.py.
        """
        sms_sent = self._send_sms(message)
        shap_text = (
            shap_explanation.get('human_readable', '')
            if shap_explanation else 'SMS alert, no SHAP'
        )
        audit_id = self._write_audit(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tower_id=tower_id,
            district=district,
            action_class=-1,
            action_name='sms_alert_dispatched',
            confidence=confidence,
            triggered_by=triggered_by,
            hw_result={'status': 'sms_sent' if sms_sent else 'sms_failed', 'message': message},
            execution_ms=0,
            shap_explanation=shap_text,
        )
        return {'audit_id': audit_id, 'sms_sent': sms_sent, 'message': message}

    def _send_sms(self, message: str) -> bool:
        if not self.twilio_config.get('enabled'):
            logger.info(f'[SIM] SMS (Twilio disabled): {message}')
            return False
        try:
            from twilio.rest import Client
            client = Client(
                self.twilio_config['sid'],
                self.twilio_config['token'],
            )
            client.messages.create(
                body=message,
                from_=self.twilio_config['from'],
                to=self.twilio_config['to'],
            )
            logger.info(f'SMS sent to {self.twilio_config["to"]}')
            return True
        except Exception as e:
            logger.error(f'SMS send failed: {e}')
            return False

    # ---- Audit Database ----

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.audit_db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                tower_id    TEXT NOT NULL,
                district    TEXT NOT NULL,
                action_class INTEGER NOT NULL,
                action_name TEXT NOT NULL,
                confidence  REAL NOT NULL,
                triggered_by TEXT NOT NULL,
                hw_status   TEXT,
                hw_message  TEXT,
                execution_ms INTEGER,
                shap_explanation TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _write_audit(
        self, timestamp, tower_id, district, action_class, action_name,
        confidence, triggered_by, hw_result, execution_ms, shap_explanation
    ) -> int:
        conn = sqlite3.connect(self.audit_db_path)
        cursor = conn.execute('''
            INSERT INTO audit_log (
                timestamp, tower_id, district, action_class, action_name,
                confidence, triggered_by, hw_status, hw_message, execution_ms,
                shap_explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, tower_id, district, action_class, action_name,
            confidence, triggered_by,
            hw_result.get('status', 'unknown'),
            hw_result.get('message', ''),
            execution_ms, shap_explanation,
        ))
        audit_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return audit_id

    def get_audit_log(
        self, limit: int = 100, tower_id: str = None, district: str = None
    ) -> list[dict]:
        conn = sqlite3.connect(self.audit_db_path)
        conn.row_factory = sqlite3.Row

        query = 'SELECT * FROM audit_log'
        params = []
        filters = []

        if tower_id:
            filters.append('tower_id = ?')
            params.append(tower_id)
        if district:
            filters.append('district = ?')
            params.append(district)

        if filters:
            query += ' WHERE ' + ' AND '.join(filters)

        query += ' ORDER BY id DESC LIMIT ?'
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_audit_stats(self) -> dict:
        conn = sqlite3.connect(self.audit_db_path)
        stats = {}
        stats['total_actions'] = conn.execute(
            'SELECT COUNT(*) FROM audit_log').fetchone()[0]
        stats['autonomous_actions'] = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE triggered_by='AUTONOMOUS'").fetchone()[0]
        stats['by_action'] = dict(conn.execute(
            'SELECT action_name, COUNT(*) FROM audit_log GROUP BY action_name').fetchall())
        stats['by_district'] = dict(conn.execute(
            'SELECT district, COUNT(*) FROM audit_log GROUP BY district').fetchall())
        conn.close()
        return stats

    def check_db(self) -> bool:
        """Verify database connectivity."""
        try:
            conn = sqlite3.connect(self.audit_db_path)
            conn.execute('SELECT 1')
            conn.close()
            return True
        except Exception as e:
            logger.error(f'Health Check: DB failure: {e}')
            return False
