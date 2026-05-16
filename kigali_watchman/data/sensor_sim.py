import requests
import time
import random
import json

API_URL = "http://localhost:5000/api/v1/predict"
CLIENT_ID = "admin"
CLIENT_SECRET = "adminpass"

def get_token():
    try:
        r = requests.post("http://localhost:5000/auth/token", 
                         json={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
        return r.json().get('access_token')
    except:
        return None

def simulate_sensors():
    token = get_token()
    if not token:
        print("Could not connect to KIRA API. Ensure backend is running.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    domains = ['iot', 'grid', 'gen']
    
    print("🚀 KIRA Sensor Simulator Active. Press Ctrl+C to stop.")
    
    while True:
        domain = random.choice(domains)
        
        # Create a "normal" or "anomalous" packet
        is_anomaly = random.random() > 0.8
        
        if domain == 'iot':
            payload = {
                "domain": "iot",
                "tower_id": "Tower-Kacyiru-A",
                "features": {
                    "CPU_Usage (%)": 10 + (80 if is_anomaly else random.uniform(0, 10)),
                    "Memory_Usage (%)": 20 + random.uniform(0, 10),
                    "Battery_Level (%)": 80 - random.uniform(0, 5),
                    "Network_Latency (ms)": 5 + (100 if is_anomaly else random.uniform(0, 10)),
                    "Packet_Loss (%)": random.uniform(0, 1),
                    "Temperature (°C)": 25 + (30 if is_anomaly else random.uniform(0, 5)),
                    "Uptime (hrs)": 120,
                    "Workload_Intensity": 0.5,
                    "Error_Count": 5 if is_anomaly else 0
                }
            }
        elif domain == 'grid':
            payload = {
                "domain": "grid",
                "tower_id": "Substation-Remera-1",
                "features": {
                    "Voltage (V)": 220 + (50 if is_anomaly else random.uniform(-5, 5)),
                    "Current (A)": 10 + random.uniform(0, 2),
                    "Power Load (MW)": 50 + (100 if is_anomaly else random.uniform(0, 10)),
                    "Temperature (°C)": 40 + (40 if is_anomaly else random.uniform(0, 10)),
                    "Wind Speed (km/h)": 10,
                    "Weather Condition": "Sunny",
                    "Maintenance Status": "Good",
                    "Component Health": "Healthy"
                }
            }
        else: # gen
            payload = {
                "domain": "gen",
                "tower_id": "Gen-Nyarutarama-Back",
                "features": {
                    "vibration": 0.1 + (0.5 if is_anomaly else random.uniform(0, 0.1)),
                    "acoustic": 0.2,
                    "temperature": 60 + (30 if is_anomaly else random.uniform(0, 10)),
                    "current": 15,
                    "IMF_1": 0.01,
                    "IMF_2": 0.01,
                    "IMF_3": 0.01
                }
            }

        try:
            resp = requests.post(API_URL, json=payload, headers=headers)
            result = resp.json()
            status = "⚠️ ALERT" if result.get('action_required') else "✅ NORMAL"
            print(f"[{domain.upper()}] {payload['tower_id']} -> {status} (Conf: {result.get('confidence', 0):.2f})")
        except Exception as e:
            print(f"Error sending data: {e}")

        time.sleep(2)

if __name__ == "__main__":
    simulate_sensors()
