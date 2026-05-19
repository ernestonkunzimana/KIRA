import { useEffect, useMemo, useState } from "react";
import { fetchAlerts, fetchSummary, openDashboardSocket } from "./api";

function StatCard({ label, value, tone = "neutral" }) {
  return (
    <article className={`stat-card stat-${tone}`}>
      <p className="stat-label">{label}</p>
      <h3>{value}</h3>
    </article>
  );
}

function formatTs(value) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function App() {
  const [summary, setSummary] = useState({ total_events: 0, anomalies: 0, healthy: 0, anomaly_rate: 0 });
  const [alerts, setAlerts] = useState([]);
  const [streamEvents, setStreamEvents] = useState([]);
  const [status, setStatus] = useState("Connecting");

  useEffect(() => {
    let alive = true;

    async function loadData() {
      const [summaryData, alertData] = await Promise.all([fetchSummary(), fetchAlerts(25)]);
      if (!alive) return;
      setSummary(summaryData);
      setAlerts(alertData);
    }

    loadData().catch(() => setStatus("Backend unavailable"));

    const ws = openDashboardSocket((msg) => {
      setStatus("Live");
      setStreamEvents((prev) => [msg, ...prev].slice(0, 10));
      if (msg.type === "detection_event") {
        setAlerts((prev) => [
          {
            id: msg.payload.id,
            event_time: msg.payload.event_time,
            node_id: msg.payload.node_id,
            ai_prediction: msg.payload.decision === "ALARM" ? -1 : 1,
            anomaly_score: msg.payload.anomaly_score,
            decision: msg.payload.decision,
            severity: msg.payload.severity,
            vibration_hz: 0,
            temperature_c: 0,
            link_quality_qos: 0,
          },
          ...prev,
        ].slice(0, 25));
      }
    });

    ws.onopen = () => setStatus("Live");
    ws.onclose = () => setStatus("Disconnected");
    ws.onerror = () => setStatus("Socket error");

    const poll = setInterval(() => {
      loadData().catch(() => setStatus("Backend unavailable"));
    }, 8000);

    return () => {
      alive = false;
      clearInterval(poll);
      ws.close();
    };
  }, []);

  const anomalyPercent = useMemo(
    () => `${(summary.anomaly_rate * 100).toFixed(2)}%`,
    [summary.anomaly_rate]
  );

  return (
    <div className="dashboard-root">
      <header className="hero">
        <h1>KIRA Enterprise Security Dashboard</h1>
        <p>Operational visibility for IT Ops, Security, and Executive Leadership.</p>
        <span className="live-pill">Stream: {status}</span>
      </header>

      <section className="stats-grid">
        <StatCard label="Total Events" value={summary.total_events} />
        <StatCard label="Anomalies" value={summary.anomalies} tone="danger" />
        <StatCard label="Healthy Events" value={summary.healthy} tone="safe" />
        <StatCard label="Anomaly Rate" value={anomalyPercent} tone="accent" />
      </section>

      <section className="panel-grid">
        <article className="panel">
          <h2>Recent Detection Events</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Node</th>
                  <th>Decision</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((item) => (
                  <tr key={item.id}>
                    <td>{formatTs(item.event_time)}</td>
                    <td>{item.node_id}</td>
                    <td>
                      <span className={`badge ${item.decision === "ALARM" ? "badge-danger" : "badge-safe"}`}>
                        {item.decision}
                      </span>
                    </td>
                    <td>{item.anomaly_score?.toFixed?.(4) ?? "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <h2>Live Event Feed</h2>
          <ul className="stream-list">
            {streamEvents.map((entry, idx) => (
              <li key={`${entry.type}-${idx}`}>
                <strong>{entry.type}</strong>
                <span>{formatTs(entry.payload?.event_time || entry.payload?.timestamp || new Date().toISOString())}</span>
              </li>
            ))}
            {streamEvents.length === 0 && <li>No live events yet.</li>}
          </ul>
        </article>
      </section>
    </div>
  );
}
