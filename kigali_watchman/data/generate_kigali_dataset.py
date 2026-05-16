"""
KIRA - Kigali Intelligent Resilience Agent
Module 5: Digital Twin Data Generator

Fix over original: battery drain is tracked per-district with continuous
outage duration, not a global i%20 counter that resets regardless of grid state.
Ground truth labels are deterministic from physical conditions, not probabilistic.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

DISTRICTS = {
    'Gasabo': {
        'towers': ['Kacyiru-A', 'Kacyiru-B', 'Kimironko', 'Remera', 'Gisozi'],
        'lat_range': (-1.93, -1.87),
        'lng_range': (30.07, 30.14),
        'outage_probability': 0.06,  # Higher: industrial area, more load
    },
    'Nyarugenge': {
        'towers': ['Nyabugogo', 'Muhima', 'Rwezamenyo', 'Gitega', 'Nyamirambo'],
        'lat_range': (-1.97, -1.93),
        'lng_range': (30.03, 30.08),
        'outage_probability': 0.05,
    },
    'Kicukiro': {
        'towers': ['Kagarama', 'Niboye', 'Gahanga', 'Masaka', 'Kanombe'],
        'lat_range': (-2.01, -1.95),
        'lng_range': (30.07, 30.13),
        'outage_probability': 0.04,
    },
}

BACKUP_TYPES = ['solar', 'generator', 'none']
SAMPLE_INTERVAL_MIN = 5  # 5-minute sensor polling


def _assign_ground_truth(grid_status: int, battery_pct: float, outage_min: float) -> int:
    """
    Deterministic label assignment.
    0 = healthy / no action
    1 = switch to solar (battery adequate, grid down)
    2 = start generator (battery marginal, grid down)
    3 = dispatch technician (battery critical or prolonged outage)
    """
    if grid_status == 1:
        return 0
    if battery_pct > 50 and outage_min < 30:
        return 1
    if 10 < battery_pct <= 50 or outage_min >= 30:
        return 2
    return 3  # battery <= 10% or outage > 60 min


def _compute_time_to_failure(battery_pct: float, discharge_rate_per_min: float) -> float:
    """Regression target: estimated minutes until battery hits 0."""
    if discharge_rate_per_min <= 0:
        return 999.0
    return round(battery_pct / discharge_rate_per_min, 2)


def generate_kigali_infrastructure_data(num_days: int = 7) -> pd.DataFrame:
    """
    Generate num_days of 5-minute interval sensor data for all Kigali towers.
    Returns a DataFrame with all features and ground truth labels.
    """
    np.random.seed(42)
    samples_per_day = (24 * 60) // SAMPLE_INTERVAL_MIN  # 288 per day
    total_samples = num_days * samples_per_day
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    records = []

    for district, meta in DISTRICTS.items():
        for tower_id in meta['towers']:
            # Per-tower state tracked across time
            battery_pct = 100.0
            outage_duration_min = 0.0
            backup_type = np.random.choice(BACKUP_TYPES, p=[0.4, 0.4, 0.2])

            # Rwanda-realistic: 3 outages per day on average, each 20-90 min
            outage_schedule = _build_outage_schedule(total_samples, meta['outage_probability'])

            lat = np.random.uniform(*meta['lat_range'])
            lng = np.random.uniform(*meta['lng_range'])

            for step in range(total_samples):
                ts = start_time + timedelta(minutes=SAMPLE_INTERVAL_MIN * step)
                grid_status = outage_schedule[step]

                # --- Power features ---
                if grid_status == 1:
                    grid_voltage = np.random.normal(230, 8)
                    outage_duration_min = 0.0
                    discharge_rate = 0.0
                    battery_pct = min(100.0, battery_pct + 0.5)  # slow recharge
                else:
                    grid_voltage = np.random.normal(145, 20)
                    outage_duration_min += SAMPLE_INTERVAL_MIN
                    # Discharge rate varies by backup type
                    if backup_type == 'solar':
                        discharge_rate = np.random.normal(1.8, 0.4)
                    elif backup_type == 'generator':
                        discharge_rate = np.random.normal(0.5, 0.15)  # gen keeps battery
                    else:
                        discharge_rate = np.random.normal(4.2, 0.8)
                    battery_pct = max(0.0, battery_pct - discharge_rate * SAMPLE_INTERVAL_MIN)

                grid_voltage = max(0, grid_voltage)

                # --- Thermal features ---
                base_temp = np.random.normal(27, 4)
                thermal_load = (100 - battery_pct) * 0.12 if grid_status == 0 else 0
                cpu_temp = base_temp + thermal_load + np.random.normal(0, 1.5)

                # --- Telecom KPIs ---
                if battery_pct > 20:
                    rssi = np.random.normal(-68, 4)
                    latency_ms = np.random.normal(28, 6)
                    cssr_pct = np.random.normal(98.5, 0.8)
                    dcr_pct = np.random.normal(0.3, 0.1)
                    throughput_mbps = np.random.uniform(60, 100)
                elif battery_pct > 5:
                    rssi = np.random.normal(-88, 6)
                    latency_ms = np.random.normal(80, 20)
                    cssr_pct = np.random.normal(85, 4)
                    dcr_pct = np.random.normal(4.5, 1.2)
                    throughput_mbps = np.random.uniform(10, 35)
                else:
                    rssi = np.random.normal(-105, 3)
                    latency_ms = np.random.normal(250, 50)
                    cssr_pct = np.random.normal(45, 10)
                    dcr_pct = np.random.normal(18, 4)
                    throughput_mbps = np.random.uniform(0, 8)

                # Clamp to physical bounds
                rssi = max(-120, min(-40, rssi))
                cssr_pct = max(0, min(100, cssr_pct))
                dcr_pct = max(0, min(100, dcr_pct))
                throughput_mbps = max(0, throughput_mbps)

                # --- Ground truth ---
                label_action = _assign_ground_truth(grid_status, battery_pct, outage_duration_min)
                ttf_minutes = _compute_time_to_failure(battery_pct, discharge_rate)

                records.append({
                    'timestamp': ts.isoformat(),
                    'district': district,
                    'tower_id': tower_id,
                    'lat': round(lat, 6),
                    'lng': round(lng, 6),
                    'backup_type': backup_type,
                    'grid_voltage': round(grid_voltage, 2),
                    'grid_status': int(grid_status),
                    'outage_duration_min': round(outage_duration_min, 1),
                    'battery_level': round(battery_pct, 2),
                    'discharge_rate_per_min': round(discharge_rate, 3),
                    'cpu_temp': round(cpu_temp, 2),
                    'rssi': round(rssi, 2),
                    'latency_ms': round(latency_ms, 2),
                    'cssr_pct': round(cssr_pct, 3),
                    'dcr_pct': round(dcr_pct, 3),
                    'throughput_mbps': round(throughput_mbps, 2),
                    'time_to_failure_min': ttf_minutes,
                    'label_action': label_action,
                })

    df = pd.DataFrame(records)
    print(f"Dataset generated: {len(df):,} rows, {df['tower_id'].nunique()} towers, "
          f"{df['district'].nunique()} districts")
    print(f"Label distribution:\n{df['label_action'].value_counts().sort_index()}")
    print(f"Outage rate: {(1 - df['grid_status'].mean()) * 100:.1f}%")
    return df


def _build_outage_schedule(total_samples: int, outage_prob: float) -> np.ndarray:
    """
    Build a realistic outage schedule with run-length clustering.
    A single call to np.random.choice per sample gives unrealistic rapid switching.
    This creates blocks of outage (20-90 min) separated by normal operation.
    """
    schedule = np.ones(total_samples, dtype=int)
    i = 0
    while i < total_samples:
        if np.random.random() < outage_prob:
            duration = np.random.randint(4, 18)  # 4-18 samples = 20-90 min
            end = min(i + duration, total_samples)
            schedule[i:end] = 0
            i = end
        else:
            i += 1
    return schedule


if __name__ == '__main__':
    df = generate_kigali_infrastructure_data(num_days=30)
    df.to_csv('kigali_infra_data.csv', index=False)
    print("\nSaved: kigali_infra_data.csv")
