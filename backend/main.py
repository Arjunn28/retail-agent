# main.py
# This is the FastAPI server — it exposes the agent as an API.
# Think of it as the "front door" to our agent. Anyone (or any frontend) can call it.

import os
import json
import glob
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from backend.agent import run_agent
from backend.simulator import add_todays_data, seed_database

# ─────────────────────────────────────────────
# Scheduler setup
# This runs the agent automatically every hour.
# We set it up before the server starts.
# ─────────────────────────────────────────────
scheduler = BackgroundScheduler()

def scheduled_job():
    """This function runs every hour automatically."""
    print(f"\n[Scheduler] Running agent at {datetime.now().strftime('%H:%M:%S')}")
    add_todays_data()   # add fresh data for today
    run_agent()         # run the agent on the new data

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on server startup and shutdown."""
    # Startup
    print(">> Seeding database if needed...")
    seed_database()

    print(">> Starting scheduler (agent runs every hour)...")
    scheduler.add_job(scheduled_job, "interval", hours=1, id="retail_agent")
    scheduler.start()
    print(">> Scheduler started.")

    yield  # server is now running

    # Shutdown
    print(">> Shutting down scheduler...")
    scheduler.shutdown()

# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(
    title="Retail Intelligence Agent API",
    description="Autonomous agent that monitors retail KPIs and generates reports",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allows the React frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production you'd lock this to your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@app.get("/health")
def health_check():
    """
    Simple check to confirm the server is running.
    The frontend will ping this to show a green/red status indicator.
    """
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "scheduler_running": scheduler.running,
    }

@app.post("/run-agent")
def trigger_agent():
    """
    Manually trigger the agent to run right now.
    The frontend's 'Run Agent Now' button will call this.
    """
    try:
        print("\n[API] Manual agent trigger received.")
        add_todays_data()
        report = run_agent()
        return {
            "status": "success",
            "message": "Agent completed successfully",
            "report": json.loads(report),
        }
    except json.JSONDecodeError:
        # Sometimes the LLM wraps the JSON in extra text — handle gracefully
        return {
            "status": "success",
            "message": "Agent completed successfully",
            "report": report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports")
def get_all_reports():
    """
    Returns a list of all saved reports, newest first.
    The frontend uses this to show report history.
    """
    report_files = sorted(
        glob.glob("reports/report_*.json"),
        reverse=True  # newest first
    )

    reports = []
    for filepath in report_files:
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
                reports.append(data)
            except json.JSONDecodeError:
                continue  # skip any malformed files

    return {"count": len(reports), "reports": reports}

@app.get("/reports/latest")
def get_latest_report():
    """
    Returns only the most recent report.
    The frontend dashboard shows this on load.
    """
    report_files = sorted(glob.glob("reports/report_*.json"), reverse=True)

    if not report_files:
        raise HTTPException(status_code=404, detail="No reports found yet.")

    with open(report_files[0], "r") as f:
        data = json.load(f)

    return data

@app.get("/sales-data")
def get_sales_data(days: int = 7):
    """
    Returns raw sales data for the last N days.
    The frontend chart uses this to plot the sales graph.
    """
    from backend.tools import query_sales_db
    import json
    data = query_sales_db(days=days)
    return {"data": json.loads(data)}