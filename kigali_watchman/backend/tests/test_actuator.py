import sys
import os
import pytest

# Ensure the backend directory is in the path for local testing
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.actuator import Actuator

def test_actuator_audit_logging():
    # Setup a temp audit db
    test_db = "test_audit.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    actuator = Actuator(audit_db_path=test_db, simulation_mode=True)
    
    # Execute an action
    result = actuator.execute(
        action_class=2,
        action_name="Reboot_Gateway",
        tower_id="Test-Tower-01",
        district="Nyarugenge",
        confidence=0.99,
        shap_explanation={"driver": "CPU_Usage"},
        triggered_by="TEST_RUNNER"
    )
    
    assert result['status'] == 'executed'
    assert result['action_name'] == 'Reboot_Gateway'
    
    # Verify audit log
    logs = actuator.get_audit_log(limit=1)
    assert len(logs) == 1
    assert logs[0]['tower_id'] == "Test-Tower-01"
    assert logs[0]['action_name'] == "Reboot_Gateway"
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)

def test_actuator_alert_dispatch():
    test_db = "test_alert.db"
    if os.path.exists(test_db):
        os.remove(test_db)
        
    actuator = Actuator(audit_db_path=test_db, simulation_mode=True)
    
    result = actuator.dispatch_alert(
        message="Critical Overload Detected",
        tower_id="Test-Tower-02",
        district="Kicukiro",
        confidence=0.95,
        shap_explanation=None,
        triggered_by="TEST_RUNNER"
    )
    
    assert result['audit_id'] is not None
    assert 'Critical' in result['message']

    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
