const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000";

export async function fetchSummary() {
  const res = await fetch(`${API_BASE_URL}/api/v1/metrics/summary`);
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function fetchAlerts(limit = 20) {
  const res = await fetch(`${API_BASE_URL}/api/v1/alerts?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch alerts");
  return res.json();
}

export function openDashboardSocket(onMessage) {
  const ws = new WebSocket(`${WS_BASE_URL}/ws/dashboard`);
  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      // Ignore invalid payloads.
    }
  };
  return ws;
}
