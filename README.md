# Retail Intelligence Agent

An autonomous AI agent that monitors retail KPIs, detects anomalies, and generates 
actionable insights — without any human triggering it.

## What makes this different from a chatbot

Most AI projects are **reactive** — a user asks a question, the LLM answers.

This project is **autonomous** — the agent wakes up on a schedule, decides which 
tools to call, reasons over the results, and writes a structured report. No human 
input required.

## Architecture
Scheduler (every hour)
↓
Agent Brain (Llama 3.3 via Groq)
↓
┌─────┬──────┬─────────┐
│     │      │         │
Sales  Anomaly Inventory Save
Query  Detect  Check    Report
│     │      │         │
└─────┴──────┴─────────┘
↓
FastAPI Backend
↓
React Dashboard

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| LLM | Llama 3.3 via Groq API | Free, fast, supports tool-calling |
| Agent framework | Custom Python loop | Clean, debuggable, no framework overhead |
| Backend | FastAPI + APScheduler | REST API + hourly autonomous runs |
| Database | SQLite + SQLAlchemy | Lightweight, zero config |
| Frontend | React + Vite + Recharts | Fast, modern, live data visualization |
| Deployment | Render + Vercel | Both free tier |

## Features

- Autonomous hourly runs — no human trigger needed
- Anomaly detection — flags products selling 2x above or 50% below normal
- Inventory alerts — estimates days of stock remaining per product
- LLM-generated recommendations — specific, data-grounded action items
- Live dashboard — revenue chart, stat cards, alert panels
- REST API — 5 endpoints, fully documented at `/docs`

## Running locally

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m backend.simulator      # seed the database
uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Add a `.env` file with:
GROQ_API_KEY = your_groq_api_key_here

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Server + scheduler status |
| POST | `/run-agent` | Trigger agent manually |
| GET | `/reports/latest` | Most recent agent report |
| GET | `/reports` | All historical reports |
| GET | `/sales-data` | Raw sales data for charts |

## Author

Arjun A N — [GitHub](https://github.com/Arjunn28)