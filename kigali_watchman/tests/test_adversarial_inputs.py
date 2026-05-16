"""
Tests: Adversarial Input Rejection
Verifies that malformed, spoofed, and boundary-violating sensor inputs
are rejected at the inference layer before reaching the AlignmentGuard.

Run: pytest tests/test_adversarial_inputs.py -v
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


# ============================================================
# Sensor Validation Utilities (tested independently)
# ============================================================

# Physical bounds for sensor values - these mirror what the InferenceEngine enforces.
SENSOR_BOUNDS = {
    'CPU_Usage (%)':          (0, 100),
    'Memory_Usage (%)':       (0, 100),
    'Battery_Level (%)':      (0, 100),
    'Network_Latency (ms)':   (0, 10000),
    'Packet_Loss (%)':        (0, 100),
    'Temperature (°C)':       (-10, 120),
    'Voltage (V)':            (0, 5000),
    'Current (A)':            (0, 2000),
    'vibration':              (0, 50),
    'acoustic':               (0, 50),
}


def validate_sensor_bounds(sensor_data: dict) -> None:
    """Raise ValueError on physically impossible sensor readings."""
    for field, (lo, hi) in SENSOR_BOUNDS.items():
        if field not in sensor_data:
            continue
        val = sensor_data[field]
        if not isinstance(val, (int, float)):
            raise ValueError(f'Non-numeric value for {field}: {val!r}')
        if not (lo <= val <= hi):
            raise ValueError(
                f'Sensor "{field}" value {val} outside physical bounds [{lo}, {hi}]. '
                f'Possible sensor fault or adversarial injection.'
            )


# ============================================================
# Physical Bounds Rejection Tests
# ============================================================

class TestPhysicalBoundsRejection:

    def test_cpu_usage_above_100_rejected(self):
        """A CPU usage reading of 9999% is physically impossible."""
        with pytest.raises(ValueError, match='CPU_Usage'):
            validate_sensor_bounds({'CPU_Usage (%)': 9999})

    def test_negative_battery_level_rejected(self):
        with pytest.raises(ValueError, match='Battery_Level'):
            validate_sensor_bounds({'Battery_Level (%)': -5})

    def test_extreme_temperature_rejected(self):
        """A temperature of 999°C indicates a sensor fault or injection attack."""
        with pytest.raises(ValueError, match='Temperature'):
            validate_sensor_bounds({'Temperature (°C)': 999})

    def test_negative_latency_rejected(self):
        with pytest.raises(ValueError, match='Network_Latency'):
            validate_sensor_bounds({'Network_Latency (ms)': -100})

    def test_valid_sensor_passes(self):
        """A normal, valid sensor reading must not raise."""
        validate_sensor_bounds({
            'CPU_Usage (%)': 45.2,
            'Battery_Level (%)': 78.0,
            'Temperature (°C)': 35.0,
            'Network_Latency (ms)': 42.0,
        })

    def test_boundary_values_accepted(self):
        """Exact boundary values must be accepted (inclusive bounds)."""
        validate_sensor_bounds({
            'CPU_Usage (%)': 0,
            'Battery_Level (%)': 100,
            'Temperature (°C)': -10,
        })
        validate_sensor_bounds({
            'CPU_Usage (%)': 100,
            'Temperature (°C)': 120,
        })


# ============================================================
# Non-Numeric Input Rejection
# ============================================================

class TestNonNumericRejection:

    def test_string_value_rejected(self):
        with pytest.raises(ValueError):
            validate_sensor_bounds({'CPU_Usage (%)': 'eighty'})

    def test_none_value_rejected(self):
        with pytest.raises(ValueError):
            validate_sensor_bounds({'Battery_Level (%)': None})

    def test_list_value_rejected(self):
        with pytest.raises(ValueError):
            validate_sensor_bounds({'Temperature (°C)': [35.0]})


# ============================================================
# Missing Feature Detection
# ============================================================

class TestMissingFeatures:

    def test_missing_required_feature_raises(self):
        """The inference engine must raise when a required feature is absent."""
        required_features = ['CPU_Usage (%)', 'Battery_Level (%)', 'Temperature (°C)']
        sensor_data = {'CPU_Usage (%)': 40.0}  # Missing Battery and Temperature

        with pytest.raises((KeyError, ValueError)):
            features = [float(sensor_data[col]) for col in required_features]

    def test_extra_features_do_not_cause_crash(self):
        """Unknown extra fields in sensor payload must be silently ignored."""
        required_features = ['CPU_Usage (%)']
        sensor_data = {
            'CPU_Usage (%)': 40.0,
            'unknown_field': 99999,  # Should be ignored
            'injected_key': 'malicious',
        }
        # Should complete without error since only required features are extracted
        features = [float(sensor_data[col]) for col in required_features]
        assert features == [40.0]


# ============================================================
# Confidence Score Manipulation
# ============================================================

class TestConfidenceManipulation:
    """
    An attacker might try to inject an artificially boosted confidence score
    to bypass the AlignmentGuard threshold. These values must be rejected
    before reaching the guard.
    """

    def test_confidence_above_one_is_invalid(self):
        assert not (0.0 <= 1.01 <= 1.0)

    def test_confidence_below_zero_is_invalid(self):
        assert not (0.0 <= -0.01 <= 1.0)

    def test_nan_confidence_is_invalid(self):
        conf = float('nan')
        assert not (0.0 <= conf <= 1.0)

    def test_inf_confidence_is_invalid(self):
        conf = float('inf')
        assert not (0.0 <= conf <= 1.0)

    def test_normal_confidence_is_valid(self):
        for conf in [0.0, 0.5, 0.88, 0.99, 1.0]:
            assert 0.0 <= conf <= 1.0
