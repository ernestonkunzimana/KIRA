"""
KIRA - EnsembleInferenceEngine
Service 2, Core Module

Loads and fuses the 3-component ensemble per domain:
  1. Autoencoder  → anomaly score (MSE reconstruction error)
  2. LSTM         → sequence-aware urgency prediction
  3. XGBoost      → root cause classification + calibrated confidence

Fusion logic:
  - If Autoencoder MSE > ae_threshold → flag as anomaly
  - LSTM provides temporal urgency (class index)
  - XGBoost provides root cause label + confidence (used as final confidence)
  - Final predicted_class = XGBoost output
  - Final confidence = XGBoost softmax max probability
  - anomaly_flag from Autoencoder is surfaced in the response for additional context

SHAP uses the real training-data background (background_{domain}.pkl)
instead of a zero-vector baseline, ensuring physically accurate attributions.
"""

import json
import logging
import numpy as np
import joblib

logger = logging.getLogger(__name__)


class EnsembleInferenceEngine:
    """
    Wraps the 3-component KIRA ensemble per domain.

    Load once at app startup:
        engine = EnsembleInferenceEngine('iot')  # domain: iot | grid | gen

    Call per request:
        result = engine.predict(sensor_dict)
    """

    def __init__(self, domain: str, model_dir: str = 'models'):
        """
        Args:
            domain:    'iot' | 'grid' | 'gen'
            model_dir: path to the directory containing trained model files
        """
        import tensorflow as tf
        import xgboost as xgb

        self.domain = domain
        self.model_dir = model_dir

        p = lambda fname: f'{model_dir}/{fname}'

        logger.info(f'[{domain}] Loading ensemble...')

        # Autoencoder
        self.autoencoder = tf.keras.models.load_model(p(f'autoencoder_{domain}.h5'))
        logger.info(f'[{domain}] Autoencoder loaded')

        # LSTM
        self.lstm = tf.keras.models.load_model(p(f'lstm_{domain}.h5'))
        logger.info(f'[{domain}] LSTM loaded')

        # XGBoost classifier
        self.xgb_model = xgb.XGBClassifier()
        self.xgb_model.load_model(p(f'xgb_{domain}.json'))
        logger.info(f'[{domain}] XGBoost loaded')

        # Scaler (shared by all 3)
        self.scaler = joblib.load(p(f'scaler_{domain}.pkl'))

        # SHAP background: real training data rows, NOT zeros
        self.shap_background = joblib.load(p(f'background_{domain}.pkl'))
        logger.info(f'[{domain}] SHAP background loaded ({len(self.shap_background)} rows)')

        # Metadata
        with open(p(f'metadata_{domain}.json')) as f:
            self.metadata = json.load(f)

        self.feature_cols = self.metadata['feature_cols']
        self.action_labels = {int(k): v for k, v in self.metadata['action_labels'].items()}
        self.ae_threshold = float(self.metadata.get('notes', '').split('ae_threshold=')[-1] or 0.01)

        # Optional label encoders (grid domain has categorical encoders)
        encoder_path = p(f'encoders_{domain}.pkl')
        try:
            self.encoders = joblib.load(encoder_path)
        except FileNotFoundError:
            self.encoders = None

        # SHAP explainer (built lazily on first call)
        self._shap_explainer = None

        logger.info(
            f'[{domain}] EnsembleInferenceEngine ready | '
            f'val_acc={self.metadata["val_accuracy"]:.4f} | '
            f'calibrated_threshold={self.metadata["calibrated_autonomous_threshold"]:.4f}'
        )

    def predict(self, sensor_data: dict, compute_shap: bool = True) -> dict:
        """
        Run ensemble inference on a single sensor reading.

        Args:
            sensor_data:   dict with keys matching self.feature_cols
            compute_shap:  whether to include SHAP attributions

        Returns:
            dict with predicted_class, action_name, confidence,
                      anomaly_flag, lstm_urgency, shap_explanation
        """
        # ---- Feature extraction ----
        try:
            features = [float(sensor_data[col]) for col in self.feature_cols]
        except KeyError as e:
            raise ValueError(f'[{self.domain}] Missing required feature: {e}. Required: {self.feature_cols}')
        except (TypeError, ValueError) as e:
            raise ValueError(f'[{self.domain}] Non-numeric sensor value: {e}')

        X = np.array([features], dtype=np.float32)
        X_scaled = self.scaler.transform(X)

        # ---- 1. Autoencoder anomaly score ----
        recon = self.autoencoder.predict(X_scaled, verbose=0)
        recon_mse = float(np.mean(np.square(X_scaled - recon)))
        anomaly_flag = recon_mse > self.ae_threshold

        # ---- 2. LSTM urgency prediction ----
        # We pad the single row into a window by repeating it (inference-time only)
        WINDOW = self.lstm.input_shape[1]
        X_window = np.repeat(X_scaled, WINDOW, axis=0)[np.newaxis, :, :]
        lstm_probs = self.lstm.predict(X_window, verbose=0)[0]
        lstm_urgency = int(np.argmax(lstm_probs))

        # ---- 3. XGBoost root cause classification ----
        xgb_probs = self.xgb_model.predict_proba(X_scaled)[0]
        predicted_class = int(np.argmax(xgb_probs))
        confidence = float(np.max(xgb_probs))
        action_name = self.action_labels.get(predicted_class, f'class_{predicted_class}')

        result = {
            'predicted_class': predicted_class,
            'action_name': action_name,
            'confidence': round(confidence, 6),
            'all_probabilities': {
                self.action_labels.get(i, f'class_{i}'): round(float(p), 6)
                for i, p in enumerate(xgb_probs)
            },
            'anomaly_flag': anomaly_flag,
            'anomaly_score': round(recon_mse, 6),
            'lstm_urgency_class': lstm_urgency,
            'shap_explanation': None,
        }

        # ---- 4. SHAP explanation (real background baseline) ----
        if compute_shap:
            try:
                result['shap_explanation'] = self._explain(X_scaled, predicted_class, sensor_data)
            except Exception as e:
                logger.warning(f'[{self.domain}] SHAP computation failed (non-fatal): {e}')
                result['shap_explanation'] = None

        return result

    def _explain(self, X_scaled: np.ndarray, predicted_class: int, raw_values: dict) -> dict:
        """
        Compute SHAP values using REAL training-data background rows.
        This produces physically accurate attributions, not misleading zero-baseline artifacts.
        """
        import shap

        if self._shap_explainer is None:
            # TreeExplainer is optimal for XGBoost — fast and exact
            self._shap_explainer = shap.TreeExplainer(
                self.xgb_model,
                data=self.shap_background,
                feature_perturbation='interventional',
            )

        shap_values = self._shap_explainer.shap_values(X_scaled)

        # For multi-class: shap_values is (n_samples, n_features, n_classes)
        # For binary: (n_samples, n_features)
        if isinstance(shap_values, list):
            class_shap = shap_values[predicted_class][0]
        elif shap_values.ndim == 3:
            class_shap = shap_values[0, :, predicted_class]
        else:
            class_shap = shap_values[0]

        feature_importance = {
            col: round(float(val), 5)
            for col, val in zip(self.feature_cols, class_shap)
        }

        sorted_feats = sorted(feature_importance.items(), key=lambda x: abs(x[1]), reverse=True)
        top_drivers = sorted_feats[:3]

        explanation_parts = []
        for feat, contribution in top_drivers:
            raw_val = raw_values.get(feat, 'N/A')
            direction = 'elevated' if contribution > 0 else 'reduced'
            explanation_parts.append(
                f'{feat}={raw_val:.3f} ({direction} risk by {abs(contribution):.4f})'
                if isinstance(raw_val, float) else f'{feat}={raw_val} ({direction} by {abs(contribution):.4f})'
            )

        human_explanation = (
            f'Action "{self.action_labels.get(predicted_class)}" driven by: '
            + ', '.join(explanation_parts) + '.'
        )

        return {
            'feature_importances': feature_importance,
            'top_drivers': top_drivers,
            'human_readable': human_explanation,
        }

    def get_model_info(self) -> dict:
        return {
            'domain': self.domain,
            'version': self.metadata.get('version'),
            'val_accuracy': self.metadata.get('val_accuracy'),
            'calibrated_autonomous_threshold': self.metadata.get('calibrated_autonomous_threshold'),
            'feature_cols': self.feature_cols,
            'action_labels': self.action_labels,
            'ensemble_components': self.metadata.get('ensemble', []),
        }


class FallbackInferenceEngine:
    """
    SRE FAIL-SAFE: Rule-based engine used when ML models fail to load.
    Ensures KIRA can still detect critical failures using hard thresholds.
    """
    def __init__(self, domain: str):
        self.domain = domain
        self.feature_cols = []
        self.action_labels = {0: 'Normal', 1: 'Critical_Alert'}
        logger.warning(f'[{domain}] !!! INITIALIZING FALLBACK RULE-BASED ENGINE !!!')
        
        if domain == 'iot':
            self.feature_cols = ["CPU_Usage (%)", "Memory_Usage (%)", "Battery_Level (%)", "Network_Latency (ms)"]
        elif domain == 'grid':
            self.feature_cols = ["Voltage (V)", "Current (A)", "Power Load (MW)"]
        else: # gen
            self.feature_cols = ["vibration", "temperature", "current"]

    def predict(self, sensor_data: dict, compute_shap: bool = True) -> dict:
        # Simple threshold logic for fail-safe mode
        is_critical = False
        reason = "All sensors within safety bounds."
        
        try:
            if self.domain == 'iot':
                if float(sensor_data.get('CPU_Usage (%)', 0)) > 95:
                    is_critical, reason = True, "CPU saturation (>95%)"
                elif float(sensor_data.get('Network_Latency (ms)', 0)) > 500:
                    is_critical, reason = True, "Network timeout (>500ms)"
            elif self.domain == 'grid':
                if float(sensor_data.get('Voltage (V)', 0)) > 260 or float(sensor_data.get('Voltage (V)', 0)) < 180:
                    is_critical, reason = True, "Voltage out of bounds (180V-260V)"
            elif self.domain == 'gen':
                if float(sensor_data.get('temperature', 0)) > 110:
                    is_critical, reason = True, "Generator overheating (>110C)"
        except Exception as e:
            logger.error(f'Fallback logic error: {e}')

        predicted_class = 1 if is_critical else 0
        confidence = 0.99 if is_critical else 1.0 # High confidence for rule-based
        
        return {
            'predicted_class': predicted_class,
            'action_name': self.action_labels[predicted_class],
            'confidence': confidence,
            'anomaly_flag': is_critical,
            'anomaly_score': 1.0 if is_critical else 0.0,
            'lstm_urgency_class': 2 if is_critical else 0,
            'shap_explanation': {
                'human_readable': f'FAIL-SAFE MODE ACTIVE: {reason}'
            },
            'fail_safe_active': True
        }

    def get_model_info(self) -> dict:
        return {
            'domain': self.domain,
            'version': 'FALLBACK_V1',
            'status': 'DEGRADED_FAIL_SAFE',
            'feature_cols': self.feature_cols,
            'action_labels': self.action_labels
        }
