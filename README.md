# Retail Intelligence Agent

> An autonomous AI agent that monitors retail performance, detects anomalies, and 
> generates actionable business reports — on a schedule, without any human input.

**Live Demo:** [retail-agent-self.vercel.app](https://retail-agent-self.vercel.app)  
**Backend API:** [retail-agent-backend.onrender.com/docs](https://retail-agent-backend.onrender.com/docs)

---

## What this project is

Most AI projects are **reactive**: a user types a question, an LLM answers it.

This project is **autonomous**: the agent wakes up every hour, decides which tools 
to call, reasons over real retail data, and writes a structured intelligence report. 
Nobody triggers it. Nobody tells it what to do. It just runs.

This is the architectural shift from "AI chatbot" to "AI agent" — and it reflects 
how production AI systems are actually being built in 2026.

---

## The problem it solves

Retail operations teams are drowning in data but starved for insight. A store running 
10+ product lines across categories cannot realistically monitor:

- Which products are spiking or crashing in sales?
- Which SKUs are days away from a stockout?
- Which categories are underperforming vs. their baseline

A human analyst checking dashboards manually can do this once a day, maybe. An 
autonomous agent can do it every hour, surface only what matters, and write a 
plain-English report with specific recommendations.

**Target users:** Retail operations managers, inventory planners and e-commerce 
business owners who need continuous intelligence without building a data team.

---

## How it works — end to end

### 1. Data layer
A Python simulator generates 60 days of realistic retail sales history across 10 
products in 3 categories (Electronics, Apparel, Health). The simulator introduces:

- Day-to-day noise (±30% variance)
- Weekend sales boosts (1.3x multiplier)
- Random anomaly events (5% spike probability, 3% crash probability)
- Automatic restocking when inventory runs low

All data is stored in **SQLite** via **SQLAlchemy** — lightweight, zero infrastructure, 
runs anywhere.

### 2. The tools (what the agent can do)
The agent has 4 Python functions registered as callable tools:

| Tool | What it does |
|---|---|
| `query_sales_db` | Pulls last N days of sales, grouped by product, sorted by revenue |
| `detect_anomalies` | Compares 3-day rolling average to 30-day baseline — flags spikes (>2x) and crashes (<50%) |
| `get_inventory_status` | Returns stock levels per product with estimated days of stock remaining |
| `save_report` | Persists the agent's final JSON report to disk with a timestamp |

These tools are plain Python functions. The LLM decides which ones to call, in what 
order, and what to do with the results.

### 3. The agent brain
The agent uses **Llama 3.3 70B** (via **Groq API** — free tier) as its reasoning engine.

The agent loop works in two stages:

**Stage 1: Tool execution (Python-orchestrated)**  
Python calls all 4 tools in sequence and collects their outputs. This is reliable, 
fast and fully debuggable — no framework magic.

**Stage 2: LLM reasoning**  
All tool outputs are passed to the LLM in a single prompt. The LLM reasons over 
the data and produces a structured JSON report with:
- A natural language summary with real numbers
- A list of detected anomalies with ratios
- Inventory alerts with days of stock remaining
- 3 specific, data-grounded recommendations

This two-stage design separates concerns cleanly — Python handles tool execution 
reliability, the LLM handles reasoning quality.

### 4. The scheduler
**APScheduler** runs the full agent loop every hour as a background job inside the 
FastAPI server. On startup, the server seeds the database and starts the scheduler 
automatically. No cron jobs. No external orchestration. Just a Python process.

- Server Starts
- Seed database (if empty) 
- Start background scheduler 
- Every hour
- add today's data
- run agent 
- save report

### 5. The API
**FastAPI** exposes the agent and its data through 5 REST endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Server status + scheduler state |
| POST | `/run-agent` | Trigger the agent manually |
| GET | `/reports/latest` | Most recent agent report |
| GET | `/reports` | Full report history |
| GET | `/sales-data?days=N` | Raw sales data for charting |

Full interactive API documentation auto-generated at `/docs`.

### 6. The dashboard
A **React + Vite** frontend visualizes everything in real time:

- 4 stat cards: 7-day revenue, units sold, out-of-stock count, anomaly count
- Bar chart of revenue by product (Recharts)
- LLM-generated summary in plain English
- Anomaly alerts with spike/crash ratios
- Inventory alerts with days of stock remaining
- Actionable recommendations from the agent
- "Run Agent Now" button: triggers the backend and updates the dashboard live

---

## Tech stack

| Layer | Technology | Role |
|---|---|---|
| LLM | Llama 3.3 70B (Groq) | Reasoning engine — free, fast |
| Backend | FastAPI | REST API + agent orchestration |
| Scheduler | APScheduler | Hourly autonomous agent runs |
| Database | SQLite + SQLAlchemy | Persistent data store |
| Data generation | Python + Faker | Realistic synthetic retail data |
| Frontend | React + Vite | Live dashboard |
| Charts | Recharts | Revenue visualization |
| HTTP client | Axios | Frontend ↔ backend communication |
| Backend hosting | Render (free tier) | Always-on API server |
| Frontend hosting | Vercel (free tier) | Global CDN deployment |

**Total infrastructure cost: $0**

---

## Running locally

**Prerequisites:** Python 3.11+, Node.js 18+

```bash
# 1. Clone the repo
git clone https://github.com/Arjunn28/retail-agent.git
cd retail-agent

# 2. Set up Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Add your Groq API key (free at console.groq.com)
echo "GROQ_API_KEY=your_key_here" > .env

# 4. Seed the database with 60 days of retail data
python -m backend.simulator

# 5. Start the backend
uvicorn backend.main:app --reload --port 8000

# 6. Start the frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — the dashboard loads with live data.  
Open `http://localhost:8000/docs` — interactive API documentation.

---

## Real-world applications

This architecture directly maps to production use cases being built right now:

- **E-commerce ops:** Automated hourly inventory risk reports sent to Slack
- **Retail chains:** Anomaly detection across hundreds of SKUs without analyst overhead  
- **Supply chain:** Proactive stockout warnings before they impact revenue
- **Category management:** LLM-generated reorder recommendations grounded in real sales velocity

The same agent pattern — scheduled tool-calling loop + LLM reasoning over results — 
is used in production systems at companies building AI-native operations tooling.

---

## What makes this AI engineering, not just AI

| Typical AI project | This project |
|---|---|
| User asks → LLM answers | Agent runs on schedule, no user needed |
| Single LLM call | Multi-tool orchestration loop |
| Hardcoded logic | LLM decides which tools to call |
| Static output | Live dashboard updates on every run |
| Local script | Deployed, publicly accessible system |
| No memory | Persistent report history over time |

---

## Author

**Arjun A N**  
[GitHub](https://github.com/Arjunn28) · [Live Demo](https://retail-agent-self.vercel.app)


> ⚠️ **Note on hosting:** Backend runs on Render's free tier, which spins down after 
> 15 minutes of inactivity. First request after sleep takes ~60 seconds to wake up. 
> This is a hosting limitation, not an application one — in production this would run 
> on a dedicated instance.

---