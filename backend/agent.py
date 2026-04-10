# agent.py
# Cleaner agent implementation — we handle the tool orchestration in Python,
# and only ask the LLM to do what it's best at: writing intelligent summaries.

import os
import json
from datetime import date
from dotenv import load_dotenv
from groq import Groq
from backend.tools import (
    query_sales_db,
    detect_anomalies,
    get_inventory_status,
    save_report,
)

load_dotenv()

def run_agent():
    """
    Runs the full agent loop:
    1. Collect data from all tools
    2. Send everything to the LLM for analysis
    3. Save the final report
    """
    print("\n" + "="*50)
    print("RETAIL AGENT STARTING...")
    print("="*50 + "\n")

    # ── Step 1: Run all tools and collect results ──
    print(">> Calling tool: query_sales_db")
    sales_data = query_sales_db(days=7)

    print(">> Calling tool: detect_anomalies")
    anomaly_data = detect_anomalies()

    print(">> Calling tool: get_inventory_status")
    inventory_data = get_inventory_status()

    print("\n>> All tools finished. Sending to LLM for analysis...\n")

    # ── Step 2: Ask the LLM to reason over the collected data ──
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""
You are an autonomous retail intelligence agent. Analyze the following retail data 
and produce a structured JSON report. Use ONLY the data provided — do not invent numbers.

--- SALES DATA (last 7 days) ---
{sales_data}

--- ANOMALY DETECTION ---
{anomaly_data}

--- INVENTORY STATUS ---
{inventory_data}

--- YOUR TASK ---
Write a JSON report with exactly this structure (no extra text, just the JSON):
{{
  "date": "{date.today().isoformat()}",
  "summary": "2-3 sentences on overall performance using real numbers from the data",
  "anomalies": ["list each anomaly found, or write No anomalies detected if none"],
  "inventory_alerts": ["list each LOW STOCK product with units remaining and days of stock left"],
  "recommendations": ["3 specific actionable recommendations based on the data"]
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    report_text = response.choices[0].message.content.strip()

    # Clean up in case the LLM wraps it in markdown code fences
    if report_text.startswith("```"):
        report_text = report_text.split("```")[1]
        if report_text.startswith("json"):
            report_text = report_text[4:]
    report_text = report_text.strip()

    print(">> LLM analysis complete.")
    print("\nAgent report:\n")
    print(report_text)

    # ── Step 3: Save the report ──
    result = save_report(report_text)
    print("\n>> " + result)

    print("\n" + "="*50)
    print("AGENT FINISHED")
    print("="*50 + "\n")

    return report_text

if __name__ == "__main__":
    run_agent()