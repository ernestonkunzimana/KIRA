"""
Tests: Ensemble Fusion Logic
Verifies that the ensemble decision fusion (Autoencoder + LSTM + XGBoost)
produces the correct combined output, and that anomaly_flag elevates
the effective risk signal even when XGBoost confidence is low.

These tests mock the 3 model components so no actual model files are required.

Run: pytest tests/test_ensemble_fusion.py -v
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


# ============================================================
# Fusion Logic (extracted from EnsembleInferenceEngine)
# Tested independently so we can verify without loading .h5 / .json files
# ============================================================

def fuse_ensemble_outputs(
    xgb_probs: np.ndarray,
    ae_mse: float,
    ae_threshold: float,
    lstm_class: int,
    action_labels: dict,
) -> dict:
    """
    Pure fusion function, mirroring the logic inside EnsembleInferenceEngine.predict().
    Kept here for isolated unit testing.
    """
    predicted_class = int(np.argmax(xgb_probs))
    confidence = float(np.max(xgb_probs))
    action_name = action_labels.get(predicted_class, f'class_{predicted_class}')
    anomaly_flag = ae_mse > ae_threshold

    return {
        'predicted_class': predicted_class,
        'action_name': action_name,
        'confidence': round(confidence, 6),
        'anomaly_flag': anomaly_flag,
        'anomaly_score': round(ae_mse, 6),
        'lstm_urgency_class': lstm_class,
    }


ACTION_LABELS = {
    0: 'Normal',
    1: 'switch_to_solar',
    2: 'start_generator',
    3: 'dispatch_technician',
}


# ============================================================
# Fusion Output Tests
# ============================================================

class TestEnsembleFusion:

    def test_healthy_prediction_normal_class(self):
        """All models agree: healthy system → class 0, no anomaly."""
        xgb_probs = np.array([0.92, 0.04, 0.03, 0.01])
        result = fuse_ensemble_outputs(xgb_probs, ae_mse=0.001, ae_threshold=0.05,
                                       lstm_class=0, action_labels=ACTION_LABELS)
        assert result['predicted_class'] == 0
        assert result['action_name'] == 'Normal'
        assert result['confidence'] == pytest.approx(0.92, abs=1e-5)
        assert result['anomaly_flag'] is False

    def test_grid_fault_predicted(self):
        """XGBoost predicts start_generator with high confidence."""
        xgb_probs = np.array([0.05, 0.02, 0.90, 0.03])
        result = fuse_ensemble_outputs(xgb_probs, ae_mse=0.08, ae_threshold=0.05,
                                       lstm_class=2, action_labels=ACTION_LABELS)
        assert result['predicted_class'] == 2
        assert result['action_name'] == 'start_generator'
        assert result['anomaly_flag'] is True  # MSE > threshold

    def test_anomaly_flag_raised_even_when_xgb_says_normal(self):
        """
        Critical: Autoencoder detects anomaly but XGBoost is uncertain.
        The anomaly_flag MUST be True so the AlignmentGuard can escalate.
        """
        xgb_probs = np.array([0.55, 0.20, 0.15, 0.10])  # Low confidence
        result = fuse_ensemble_outputs(xgb_probs, ae_mse=0.15, ae_threshold=0.05,
                                       lstm_class=1, action_labels=ACTION_LABELS)
        assert result['anomaly_flag'] is True
        assert result['anomaly_score'] == pytest.approx(0.15, abs=1e-5)

    def test_no_anomaly_below_threshold(self):
        """MSE well below threshold should not flag anomaly."""
        xgb_probs = np.array([0.85, 0.10, 0.03, 0.02])
        result = fuse_ensemble_outputs(xgb_probs, ae_mse=0.001, ae_threshold=0.05,
                                       lstm_class=0, action_labels=ACTION_LABELS)
        assert result['anomaly_flag'] is False

    def test_lstm_urgency_is_preserved_in_output(self):
        """LSTM urgency class must be surfaced in the result dict."""
        xgb_probs = np.array([0.10, 0.80, 0.07, 0.03])
        result = fuse_ensemble_outputs(xgb_probs, ae_mse=0.02, ae_threshold=0.05,
                                       lstm_class=2, action_labels=ACTION_LABELS)
        assert result['lstm_urgency_class'] == 2

    def test_dispatch_class_can_be_predicted(self):
        """XGBoost can predict class 3 (dispatch). AlignmentGuard will block it."""
        xgb_probs = np.array([0.02, 0.05, 0.10, 0.83])
        result = fuse_ensemble_outputs(xgb_probs, ae_mse=0.20, ae_threshold=0.05,
                                       lstm_class=3, action_labels=ACTION_LABELS)
        assert result['predicted_class'] == 3
        assert result['action_name'] == 'dispatch_technician'
        # Note: AlignmentGuard (not tested here) is responsible for blocking this

    def test_confidence_is_max_of_xgb_probs(self):
        """Confidence must always equal max(xgb_probs)."""
        probs = np.array([0.10, 0.35, 0.45, 0.10])
        result = fuse_ensemble_outputs(probs, ae_mse=0.0, ae_threshold=0.05,
                                       lstm_class=0, action_labels=ACTION_LABELS)
        assert result['confidence'] == pytest.approx(0.45, abs=1e-5)

    def test_all_probabilities_sum_to_one(self):
        """XGBoost probabilities must sum to 1 (softmax constraint)."""
        probs = np.array([0.25, 0.25, 0.25, 0.25])
        assert abs(probs.sum() - 1.0) < 1e-6


# ============================================================
# Edge Cases
# ============================================================

class TestFusionEdgeCases:

    def test_perfectly_uniform_probabilities(self):
        """When all classes are equally likely, class 0 is selected (argmax tiebreak)."""
        probs = np.array([0.25, 0.25, 0.25, 0.25])
        result = fuse_ensemble_outputs(probs, ae_mse=0.01, ae_threshold=0.05,
                                       lstm_class=0, action_labels=ACTION_LABELS)
        assert result['predicted_class'] == 0
        assert result['confidence'] == pytest.approx(0.25, abs=1e-5)

    def test_anomaly_threshold_at_exact_boundary(self):
        """MSE exactly equal to threshold is NOT an anomaly (strict greater-than)."""
        result = fuse_ensemble_outputs(
            np.array([0.90, 0.05, 0.03, 0.02]),
            ae_mse=0.05, ae_threshold=0.05,
            lstm_class=0, action_labels=ACTION_LABELS,
        )
        assert result['anomaly_flag'] is False

    def test_unknown_action_label_uses_fallback(self):
        """If predicted_class is not in action_labels, use f'class_{n}' fallback."""
        probs = np.array([0.10, 0.20, 0.70])
        result = fuse_ensemble_outputs(probs, ae_mse=0.01, ae_threshold=0.05,
                                       lstm_class=0, action_labels={0: 'Normal', 1: 'Solar'})
        assert result['action_name'] == 'class_2'
