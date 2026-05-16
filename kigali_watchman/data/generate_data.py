import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_kigali_infrastructure_data(num_samples=5000):
    np.random.seed(42)
    districts = ['Gasabo', 'Nyarugenge', 'Kicukiro']
    data = []

    start_time = datetime.now()

    for i in range(num_samples):
        timestamp = start_time + timedelta(minutes=5*i)
        district = np.random.choice(districts)
        
        # --- POWER GRID (REG) FEATURES ---
        grid_voltage = np.random.normal(230, 10)  # Normal is 230V
        grid_status = 1 if grid_voltage > 180 else 0 # Outage below 180V
        
        # --- TOWER (IOT) FEATURES ---
        # Battery drops if grid is down
        battery_level = 100 if grid_status == 1 else max(0, 100 - (np.random.randint(1, 5) * (i % 20)))
        temp = np.random.normal(25, 5) + (20 if grid_status == 0 else 0) # Overheating on backup
        
        # --- TELECOM KPIs ---
        # Signal drops as battery dies or during power switching
        signal_strength = np.random.normal(-70, 5) if battery_level > 20 else -110
        throughput = np.random.uniform(50, 100) if grid_status == 1 else np.random.uniform(10, 40)

        # --- THE "GROUND TRUTH" (99.99% TARGET) ---
        # 0: Healthy, 1: Switch to Solar, 2: Start Generator, 3: Dispatch Technician
        if grid_status == 1:
            action = 0
        elif grid_status == 0 and battery_level > 50:
            action = 1 # Solar/Battery sufficient
        elif grid_status == 0 and battery_level <= 50 and battery_level > 10:
            action = 2 # Start Gen
        else:
            action = 3 # Failure Imminent - Technician needed

        data.append([timestamp, district, grid_voltage, grid_status, battery_level, temp, signal_strength, throughput, action])

    columns = ['timestamp', 'district', 'voltage', 'grid_status', 'battery_level', 'cpu_temp', 'rssi', 'throughput', 'label_action']
    return pd.DataFrame(data, columns=columns)

if __name__ == "__main__":
    # Ensure directory exists if run directly
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kigali_infra_data.csv')
    df = generate_kigali_infrastructure_data()
    df.to_csv(output_path, index=False)
    print(f"Team: Foundation Dataset '{output_path}' created.")
