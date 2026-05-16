"""
KIRA - System of Systems Training Pipeline
============================================
Trains a TRUE ENSEMBLE for each of the 3 infrastructure domains:

  1. Autoencoder  — Anomaly detection (reconstruction error threshold)
  2. LSTM         — Time-To-Failure regression on sliding windows
  3. XGBoost      — Root cause / fault classification

Fusion strategy:
  - Autoencoder flags anomaly (binary) → gates the pipeline
  - LSTM predicts urgency in hours → prioritizes alert severity
  - XGBoost classifies root cause → drives technician dispatch

Outputs per domain (iot / grid / gen):
  - models/autoencoder_{domain}.h5
  - models/lstm_{domain}.h5
  - models/xgb_{domain}.json
  - models/scaler_{domain}.pkl
  - models/background_{domain}.pkl   ← SHAP baseline (100 training rows)
  - models/metadata_{domain}.json    ← val accuracy + calibrated threshold

Run from backend/:
  python train_system_of_systems.py
"""

import json
import joblib
import logging
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.utils.class_weight import compute_class_weight
import xgboost as xgb
import mlflow
import mlflow.sklearn
import mlflow.xgboost

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger('kira.train')

os.makedirs('models', exist_ok=True)
# Path resolution: make paths relative to THIS script, not the CWD
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(SCRIPT_DIR, '..', 'dataset')

# ---- MLflow experiment ----
mlflow.set_experiment('KIRA-System-of-Systems')


# ============================================================
# Shared utilities
# ============================================================

def calibrate_threshold(model, X_val_scaled, y_val, percentile=99):
    """
    After training, compute the Nth percentile of confidence for
    CORRECT predictions on the validation set.
    This is the empirical value to use for AUTONOMOUS_THRESHOLD.
    """
    try:
        probs = model.predict_proba(X_val_scaled)
        correct_mask = probs.argmax(axis=1) == y_val
        correct_confidences = probs[correct_mask].max(axis=1)
        if len(correct_confidences) == 0:
            return 0.88
        threshold = float(np.percentile(correct_confidences, percentile))
        logger.info(f'  ✓ Calibrated AUTONOMOUS_THRESHOLD ({percentile}th pct of correct preds): {threshold:.4f}')
        return threshold
    except Exception as e:
        logger.warning(f'  Threshold calibration failed: {e}. Using default 0.88.')
        return 0.88


def build_autoencoder(input_dim: int):
    """Undercomplete Autoencoder for anomaly detection."""
    import tensorflow as tf
    encoding_dim = max(4, input_dim // 4)
    inp = tf.keras.Input(shape=(input_dim,))
    encoded = tf.keras.layers.Dense(encoding_dim * 2, activation='relu')(inp)
    encoded = tf.keras.layers.Dense(encoding_dim, activation='relu')(encoded)
    decoded = tf.keras.layers.Dense(encoding_dim * 2, activation='relu')(encoded)
    decoded = tf.keras.layers.Dense(input_dim, activation='linear')(decoded)
    ae = tf.keras.Model(inputs=inp, outputs=decoded)
    ae.compile(optimizer='adam', loss='mse')
    return ae


def build_lstm(window_size: int, n_features: int, n_classes: int):
    """LSTM for time-series sequence classification (TTF urgency proxy)."""
    import tensorflow as tf
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(64, input_shape=(window_size, n_features), return_sequences=True),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(32),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(n_classes, activation='softmax'),
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    return model


def make_windows(X: np.ndarray, y: np.ndarray, window_size: int = 10):
    """Slide a window over rows to create LSTM sequences."""
    Xs, ys = [], []
    for i in range(len(X) - window_size):
        Xs.append(X[i: i + window_size])
        ys.append(y[i + window_size])
    return np.array(Xs), np.array(ys)


def save_metadata(domain: str, val_acc: float, calibrated_threshold: float,
                  feature_cols: list, action_labels: dict, notes: str = ''):
    meta = {
        'version': f'{domain}_ensemble_v1',
        'val_accuracy': round(val_acc, 4),
        'calibrated_autonomous_threshold': round(calibrated_threshold, 4),
        'feature_cols': feature_cols,
        'action_labels': action_labels,
        'ensemble': ['autoencoder', 'lstm', 'xgboost'],
        'notes': notes,
    }
    path = f'models/metadata_{domain}.json'
    with open(path, 'w') as f:
        json.dump(meta, f, indent=2)
    logger.info(f'  Saved {path}')


# ============================================================
# Domain 1: Telecom IoT
# ============================================================

def train_iot():
    logger.info('=' * 60)
    logger.info('DOMAIN 1: Telecom IoT Failure Prediction')
    logger.info('=' * 60)

    df = pd.read_csv(f'{DATASET_DIR}/IoT_Failure_Prediction_Dataset.csv')
    logger.info(f'  Loaded {len(df):,} rows. Columns: {list(df.columns)}')

    # Drop non-numeric IDs
    df = df.drop(columns=[c for c in ['Device_ID'] if c in df.columns])

    target_col = 'Failure_Type'
    X = df.drop(columns=[target_col])
    y = df[target_col].values
    feature_cols = list(X.columns)

    # Encode string target if needed
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    action_labels = {str(i): str(cls) for i, cls in enumerate(le.classes_)}

    # Chronological split (no shuffle to avoid temporal leakage)
    split = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split].values, X.iloc[split:].values
    y_train, y_val = y_enc[:split], y_enc[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    joblib.dump(scaler, 'models/scaler_iot.pkl')

    # SHAP baseline: random 100 rows from training data
    bg_idx = np.random.choice(len(X_train_s), min(100, len(X_train_s)), replace=False)
    joblib.dump(X_train_s[bg_idx], 'models/background_iot.pkl')
    logger.info(f'  Saved SHAP background baseline (100 training rows)')

    num_classes = len(np.unique(y_enc))
    class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    cw_dict = dict(enumerate(class_weights))

    with mlflow.start_run(run_name='iot_ensemble'):
        mlflow.log_param('domain', 'iot')
        mlflow.log_param('n_samples', len(X_train))
        mlflow.log_param('n_features', len(feature_cols))

        # --- 1. Autoencoder (train on normal class only) ---
        logger.info('  Training Autoencoder...')
        normal_mask = y_train == 0
        X_normal = X_train_s[normal_mask] if normal_mask.sum() > 20 else X_train_s
        ae = build_autoencoder(len(feature_cols))
        ae.fit(X_normal, X_normal, epochs=50, batch_size=32,
               validation_split=0.1, verbose=0)
        ae.save('models/autoencoder_iot.h5')
        # Anomaly threshold: 99th pct of reconstruction error on training data
        recon = ae.predict(X_train_s, verbose=0)
        ae_threshold = float(np.percentile(np.mean(np.square(X_train_s - recon), axis=1), 99))
        logger.info(f'  Autoencoder anomaly threshold (99th pct MSE): {ae_threshold:.6f}')
        mlflow.log_metric('ae_anomaly_threshold', ae_threshold)

        # --- 2. LSTM ---
        logger.info('  Training LSTM...')
        WINDOW = 10
        X_w, y_w = make_windows(X_train_s, y_train, WINDOW)
        X_w_val, y_w_val = make_windows(X_val_s, y_val, WINDOW)
        lstm = build_lstm(WINDOW, len(feature_cols), num_classes)
        lstm.fit(X_w, y_w, epochs=30, batch_size=32, validation_data=(X_w_val, y_w_val),
                 class_weight=cw_dict, verbose=0)
        lstm.save('models/lstm_iot.h5')
        _, lstm_acc = lstm.evaluate(X_w_val, y_w_val, verbose=0)
        logger.info(f'  LSTM val accuracy: {lstm_acc*100:.2f}%')

        # --- 3. XGBoost (root cause classifier) ---
        logger.info('  Training XGBoost root cause classifier...')
        xgb_model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            use_label_encoder=False, eval_metric='mlogloss',
            scale_pos_weight=1, random_state=42,
        )
        xgb_model.fit(X_train_s, y_train,
                      eval_set=[(X_val_s, y_val)],
                      verbose=False)
        xgb_model.get_booster().save_model('models/xgb_iot.json')
        xgb_acc = float(np.mean(xgb_model.predict(X_val_s) == y_val))
        logger.info(f'  XGBoost val accuracy: {xgb_acc*100:.2f}%')
        mlflow.log_metric('xgb_val_accuracy', xgb_acc)
        mlflow.xgboost.log_model(xgb_model.get_booster(), 'xgb_iot')

        # Calibrate threshold from XGBoost (most reliable confidence)
        threshold = calibrate_threshold(xgb_model, X_val_s, y_val)
        save_metadata('iot', xgb_acc, threshold, feature_cols, action_labels,
                      notes=f'ae_threshold={ae_threshold:.6f}')
        mlflow.log_metric('calibrated_autonomous_threshold', threshold)

    logger.info('  ✅ IoT domain complete.\n')


# ============================================================
# Domain 2: REG Power Grid
# ============================================================

def train_grid():
    logger.info('=' * 60)
    logger.info('DOMAIN 2: REG Power Grid Fault Prediction')
    logger.info('=' * 60)

    df = pd.read_csv(f'{DATASET_DIR}/fault_data.csv')
    logger.info(f'  Loaded {len(df):,} rows. Columns: {list(df.columns)}')

    # Drop non-ML columns
    drop_cols = [c for c in ['Fault ID', 'Fault Location (Latitude, Longitude)'] if c in df.columns]
    df = df.drop(columns=drop_cols)

    target_col = 'Fault Type'
    cat_cols = [c for c in ['Weather Condition', 'Maintenance Status', 'Component Health']
                if c in df.columns]

    encoders = {}
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    le_target = LabelEncoder()
    y_enc = le_target.fit_transform(df[target_col].astype(str))
    encoders['target'] = le_target
    action_labels = {str(i): str(cls) for i, cls in enumerate(le_target.classes_)}
    joblib.dump(encoders, 'models/encoders_grid.pkl')

    X = df.drop(columns=[target_col]).values
    feature_cols = list(df.drop(columns=[target_col]).columns)

    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y_enc[:split], y_enc[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    joblib.dump(scaler, 'models/scaler_grid.pkl')

    bg_idx = np.random.choice(len(X_train_s), min(100, len(X_train_s)), replace=False)
    joblib.dump(X_train_s[bg_idx], 'models/background_grid.pkl')

    num_classes = len(np.unique(y_enc))
    class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    cw_dict = dict(enumerate(class_weights))

    with mlflow.start_run(run_name='grid_ensemble'):
        mlflow.log_param('domain', 'grid')
        mlflow.log_param('n_samples', len(X_train))

        logger.info('  Training Autoencoder...')
        ae = build_autoencoder(len(feature_cols))
        ae.fit(X_train_s, X_train_s, epochs=50, batch_size=32, validation_split=0.1, verbose=0)
        ae.save('models/autoencoder_grid.h5')
        recon = ae.predict(X_train_s, verbose=0)
        ae_threshold = float(np.percentile(np.mean(np.square(X_train_s - recon), axis=1), 99))
        logger.info(f'  Autoencoder threshold: {ae_threshold:.6f}')

        logger.info('  Training LSTM...')
        WINDOW = 10
        X_w, y_w = make_windows(X_train_s, y_train, WINDOW)
        X_w_val, y_w_val = make_windows(X_val_s, y_val, WINDOW)
        lstm = build_lstm(WINDOW, len(feature_cols), num_classes)
        lstm.fit(X_w, y_w, epochs=30, batch_size=32, validation_data=(X_w_val, y_w_val),
                 class_weight=cw_dict, verbose=0)
        lstm.save('models/lstm_grid.h5')
        _, lstm_acc = lstm.evaluate(X_w_val, y_w_val, verbose=0)
        logger.info(f'  LSTM val accuracy: {lstm_acc*100:.2f}%')

        logger.info('  Training XGBoost...')
        xgb_model = xgb.XGBClassifier(
            n_estimators=300, max_depth=8, learning_rate=0.03,
            use_label_encoder=False, eval_metric='mlogloss', random_state=42,
        )
        xgb_model.fit(X_train_s, y_train, eval_set=[(X_val_s, y_val)], verbose=False)
        xgb_model.get_booster().save_model('models/xgb_grid.json')
        xgb_acc = float(np.mean(xgb_model.predict(X_val_s) == y_val))
        logger.info(f'  XGBoost val accuracy: {xgb_acc*100:.2f}%')
        mlflow.log_metric('xgb_val_accuracy', xgb_acc)
        mlflow.xgboost.log_model(xgb_model.get_booster(), 'xgb_grid')

        threshold = calibrate_threshold(xgb_model, X_val_s, y_val)
        save_metadata('grid', xgb_acc, threshold, feature_cols, action_labels,
                      notes=f'ae_threshold={ae_threshold:.6f}')

    logger.info('  ✅ Grid domain complete.\n')


# ============================================================
# Domain 3: Backup Generator Predictive Maintenance
# ============================================================

def train_generator():
    logger.info('=' * 60)
    logger.info('DOMAIN 3: Backup Generator Predictive Maintenance')
    logger.info('=' * 60)

    df = pd.read_csv(f'{DATASET_DIR}/predictive_maintenance_dataset.csv')
    logger.info(f'  Loaded {len(df):,} rows. Columns: {list(df.columns)}')

    drop_cols = [c for c in ['timestamp', 'machine_id'] if c in df.columns]
    df = df.drop(columns=drop_cols)

    target_col = 'label'
    X = df.drop(columns=[target_col]).values
    y = df[target_col].values
    feature_cols = list(df.drop(columns=[target_col]).columns)
    action_labels = {'0': 'Normal', '1': 'Failure_Imminent'}

    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    joblib.dump(scaler, 'models/scaler_gen.pkl')

    bg_idx = np.random.choice(len(X_train_s), min(100, len(X_train_s)), replace=False)
    joblib.dump(X_train_s[bg_idx], 'models/background_gen.pkl')

    num_classes = len(np.unique(y))
    class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    cw_dict = dict(enumerate(class_weights))

    with mlflow.start_run(run_name='gen_ensemble'):
        mlflow.log_param('domain', 'generator')
        mlflow.log_param('n_samples', len(X_train))

        logger.info('  Training Autoencoder...')
        normal_mask = y_train == 0
        X_normal = X_train_s[normal_mask] if normal_mask.sum() > 20 else X_train_s
        ae = build_autoencoder(len(feature_cols))
        ae.fit(X_normal, X_normal, epochs=50, batch_size=32, validation_split=0.1, verbose=0)
        ae.save('models/autoencoder_gen.h5')
        recon = ae.predict(X_train_s, verbose=0)
        ae_threshold = float(np.percentile(np.mean(np.square(X_train_s - recon), axis=1), 99))
        logger.info(f'  Autoencoder threshold: {ae_threshold:.6f}')

        logger.info('  Training LSTM...')
        WINDOW = 10
        X_w, y_w = make_windows(X_train_s, y_train, WINDOW)
        X_w_val, y_w_val = make_windows(X_val_s, y_val, WINDOW)
        lstm = build_lstm(WINDOW, len(feature_cols), num_classes)
        lstm.fit(X_w, y_w, epochs=30, batch_size=32, validation_data=(X_w_val, y_w_val),
                 class_weight=cw_dict, verbose=0)
        lstm.save('models/lstm_gen.h5')
        _, lstm_acc = lstm.evaluate(X_w_val, y_w_val, verbose=0)
        logger.info(f'  LSTM val accuracy: {lstm_acc*100:.2f}%')

        logger.info('  Training XGBoost...')
        xgb_model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            use_label_encoder=False, eval_metric='logloss', random_state=42,
        )
        xgb_model.fit(X_train_s, y_train, eval_set=[(X_val_s, y_val)], verbose=False)
        xgb_model.get_booster().save_model('models/xgb_gen.json')
        xgb_acc = float(np.mean(xgb_model.predict(X_val_s) == y_val))
        logger.info(f'  XGBoost val accuracy: {xgb_acc*100:.2f}%')
        mlflow.log_metric('xgb_val_accuracy', xgb_acc)
        mlflow.xgboost.log_model(xgb_model.get_booster(), 'xgb_gen')

        threshold = calibrate_threshold(xgb_model, X_val_s, y_val)
        save_metadata('gen', xgb_acc, threshold, feature_cols, action_labels,
                      notes=f'ae_threshold={ae_threshold:.6f}')

    logger.info('  ✅ Generator domain complete.\n')


# ============================================================
# Entry point
# ============================================================

if __name__ == '__main__':
    logger.info('🚀 KIRA System of Systems — True Ensemble Training Pipeline')
    logger.info('   3 domains × 3 models (Autoencoder + LSTM + XGBoost)')
    logger.info(f'   Dataset dir: {os.path.abspath(DATASET_DIR)}')
    print()

    train_iot()
    train_grid()
    train_generator()

    logger.info('=' * 60)
    logger.info('✅ All 9 ensemble models trained and exported.')
    logger.info('   Set .env AUTONOMOUS_THRESHOLD to the calibrated value printed above.')
    logger.info('   Run: docker-compose up --build')
    logger.info('=' * 60)
