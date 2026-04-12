import { useState, useEffect } from "react";
import axios from "axios";

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  timeout: 90000,
});

import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";

// const API = "http://localhost:8000";
const API = "https://retail-agent-backend.onrender.com";

// Helper — safely parse the report whether it's a string or already an object
function parseReport(raw) {
  if (!raw) return null;
  if (typeof raw.report === "object") return raw.report;
  try {
    return JSON.parse(raw.report);
  } catch {
    return null;
  }
}

// Reasoning trace panel — shows the agent's step-by-step thinking
function AgentTrace({ trace }) {
  if (!trace || trace.length === 0) return null;

  const toolColors = {
    "query_sales_db": "#e8f0fe",
    "detect_anomalies": "#fff8e1",
    "get_inventory_status": "#fdecea",
    "save_report": "#e8f5e9",
    "llama-3.3-70b-versatile (Groq)": "#f3e8fd",
  };

  const toolLabels = {
    "query_sales_db": "Sales DB",
    "detect_anomalies": "Anomaly Engine",
    "get_inventory_status": "Inventory Check",
    "save_report": "Report Saved",
    "llama-3.3-70b-versatile (Groq)": "LLM Reasoning",
  };

  return (
    <div className="section">
      <h2>Agent reasoning trace</h2>
      <p style={{ fontSize: "0.8rem", color: "#888", marginBottom: "1rem" }}>
        Step-by-step log of what the agent observed and why it made each decision.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {trace.map((step, i) => (
          <div key={i} style={{
            background: toolColors[step.tool] || "#f9f9f9",
            borderRadius: "8px",
            padding: "12px 14px",
            borderLeft: "3px solid #ccc",
          }}>
            <div style={{
              display: "flex", alignItems: "center",
              gap: "8px", marginBottom: "6px"
            }}>
              <span style={{
                fontSize: "11px", fontWeight: 600,
                background: "rgba(0,0,0,0.08)",
                padding: "2px 8px", borderRadius: "20px"
              }}>
                Step {step.step}
              </span>
              <span style={{ fontSize: "12px", fontWeight: 600, color: "#333" }}>
                {step.action}
              </span>
              <span style={{
                fontSize: "10px", color: "#666",
                marginLeft: "auto",
                background: "rgba(0,0,0,0.06)",
                padding: "2px 6px", borderRadius: "4px"
              }}>
                {toolLabels[step.tool] || step.tool}
              </span>
            </div>
            <p style={{ fontSize: "12px", color: "#444", marginBottom: "4px", lineHeight: 1.5 }}>
              <strong>Observed:</strong> {step.observation}
            </p>
            <p style={{ fontSize: "12px", color: "#666", lineHeight: 1.5 }}>
              <strong>Reasoning:</strong> {step.reasoning}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [health, setHealth]       = useState(null);
  const [report, setReport]       = useState(null);
  const [salesData, setSalesData] = useState([]);
  const [running, setRunning]     = useState(false);
  const [error, setError]         = useState(null);
  const [lastRun, setLastRun]     = useState(null);

  // Load health + latest report + sales data on page load
  useEffect(() => {
    fetchHealth();
    fetchLatestReport();
  }, []);

  async function fetchHealth() {
    try {
      const res = await axiosInstance.get(`/health`);
      setHealth(res.data);
    } catch {
      setHealth({ status: "offline" });
    }
  }

  // async function fetchLatestReport() {
  //   try {
  //     const res = await axiosInstance.get(`/reports/latest`);
  //     const parsed = parseReport(res.data);
  //     setReport(parsed);
  //     setLastRun(res.data.generated_at);
  //   } catch {
  //     setReport(null);
  //   }
  // }

  async function fetchLatestReport() {
  try {
    const res = await axiosInstance.get(`/reports/latest`);
    const parsed = parseReport(res.data);
    setReport(parsed);
    setLastRun(res.data.generated_at);
    // Use sales data from the same report — ensures chart matches summary
    if (res.data.sales_data) {
      setSalesData(res.data.sales_data);
    }
  } catch {
    setReport(null);
  }
}

//   async function fetchSalesData() {
//   try {
//     const res = await axiosInstance.get(`/sales-data?days=7`);
//     setSalesData(res.data.data);
//   } catch {
//     setSalesData([]);
//   }
// }

async function fetchSalesData() {
  // Sales data now comes from the report itself — guaranteed to match
}

  async function handleRunAgent() {
    setRunning(true);
    setError(null);
    try {
      const res = await axiosInstance.post(`/run-agent`);
      const parsed = typeof res.data.report === "object"
        ? res.data.report
        : JSON.parse(res.data.report);
      setReport(parsed);
      setLastRun(new Date().toISOString().split("T")[0]);
      // Pull sales data from the agent run response directly
      if (res.data.sales_data) {
        setSalesData(res.data.sales_data);
      } else {
        await fetchLatestReport();
      }
    } catch (e) {
      setError("Agent is waking up,this can take 60 seconds on first run. Please try again.");
    } finally {
      setRunning(false);
    }
  }

  // Stat cards at the top
  const totalRevenue = salesData
    .reduce((sum, p) => sum + p.revenue, 0)
    .toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

  const totalUnits = salesData
    .reduce((sum, p) => sum + p.units_sold, 0)
    .toLocaleString();

  const outOfStock = salesData
    .filter(p => p.current_inventory === 0).length;

  const anomalyCount = report?.anomalies
    ?.filter(a => !a.toLowerCase().includes("no anomal")).length ?? 0;

  return (
    <div className="app">

      {/* Header */}
      <header>
        <h1>Retail Intelligence Agent</h1>
        <div className="status-badge">
          <div className={`status-dot ${health?.status === "online" ? "" : "offline"}`} />
          {health?.status === "online" ? "Agent online" : "Agent offline"}
        </div>
      </header>

      {/* Error */}
      {error && <div className="error-banner">{error}</div>}

      {/* Stat cards */}
      <div className="grid">
        <div className="card">
          <h2>7-day revenue</h2>
          <div className="value">{totalRevenue}</div>
          <div className="sub">Last 7 days</div>
        </div>
        <div className="card">
          <h2>Units sold</h2>
          <div className="value">{totalUnits}</div>
          <div className="sub">Last 7 days</div>
        </div>
        <div className="card">
          <h2>Out of stock</h2>
          <div className="value" style={{ color: outOfStock > 0 ? "#ea4335" : "#34a853" }}>
            {outOfStock}
          </div>
          <div className="sub">Products</div>
        </div>
        <div className="card">
          <h2>Anomalies</h2>
          <div className="value" style={{ color: anomalyCount > 0 ? "#f9a825" : "#34a853" }}>
            {anomalyCount}
          </div>
          <div className="sub">Detected</div>
        </div>
      </div>

      {/* Run agent button */}
      <button
        className={`run-btn ${running ? "running" : ""}`}
        onClick={handleRunAgent}
        disabled={running}
      >
        {running ? "Agent is running..." : "Run Agent Now"}
      </button>

      {/* Sales chart */}
      <div className="section">
        <h2>Revenue by product (last 7 days)</h2>
        {salesData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={salesData} margin={{ top: 4, right: 16, left: 0, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="product"
                tick={{ fontSize: 11 }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={v => `$${(v/1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={v => [`$${v.toLocaleString()}`, "Revenue"]}
              />
              <Bar dataKey="revenue" fill="#1a1a2e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="no-data">No sales data available.</p>
        )}
      </div>

      {/* Agent report */}
      {report ? (
        <>
          {lastRun && (
            <p className="report-date">Last agent run: {lastRun}</p>
          )}

          {/* Summary */}
          <div className="section">
            <h2>Summary</h2>
            <p className="summary-text">{report.summary}</p>
          </div>

          {/* Two column layout for alerts */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>

            {/* Anomalies */}
            <div className="section" style={{ margin: 0 }}>
              <h2>Anomalies</h2>
              {report.anomalies?.length > 0 ? (
                <ul className="alert-list">
                  {report.anomalies.map((a, i) => (
                    <li key={i} className="alert-item anomaly">
                      <span className="alert-icon">⚡</span>
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="no-data">No anomalies detected.</p>
              )}
            </div>

            {/* Inventory alerts */}
            <div className="section" style={{ margin: 0 }}>
              <h2>Inventory alerts</h2>
              {report.inventory_alerts?.length > 0 ? (
                <ul className="alert-list">
                  {report.inventory_alerts.map((a, i) => (
                    <li key={i} className="alert-item inventory">
                      <span className="alert-icon">📦</span>
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="no-data">All products well stocked.</p>
              )}
            </div>
          </div>

          {/* Recommendations */}
          <div className="section">
            <h2>Recommendations</h2>
            {report.recommendations?.length > 0 ? (
              <ul className="alert-list">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="alert-item recommendation">
                    <span className="alert-icon">✓</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="no-data">No recommendations available.</p>
            )}
          </div>
        </>
      ) : (
        <div className="section">
          <p className="no-data">No report yet. Click "Run Agent Now" to generate one.</p>
        </div>
      )}
    {/* Agent reasoning trace */}
    {report?.agent_trace && <AgentTrace trace={report.agent_trace} />}
    </div>
  );
}