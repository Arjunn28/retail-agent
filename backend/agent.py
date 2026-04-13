# agent.py
# The agent brain — now with a full reasoning trace so every decision is visible.
# The trace shows exactly what the agent observed, flagged, and concluded at each step.

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
    send_alert_email,  # add this
)

load_dotenv()

def run_agent():
    """
    Runs the full agent loop with a reasoning trace.
    The trace captures every step — what data was seen, what was flagged, why.
    """
    print("\n" + "="*50)
    print("SENTINEL AI STARTING...")
    print("="*50 + "\n")

    trace = []  # this is the agent's reasoning log — every step recorded here

    # ── Step 1: Query sales data ──
    print(">> [Step 1] Querying sales database...")
    sales_raw = query_sales_db(days=7)
    sales_data = json.loads(sales_raw)

    total_revenue = sum(p["revenue"] for p in sales_data)
    total_units = sum(p["units_sold"] for p in sales_data)
    top_product = sales_data[0] if sales_data else {}

    trace.append({
        "step": 1,
        "action": "Query sales database",
        "tool": "query_sales_db",
        "observation": f"Retrieved 7-day sales for {len(sales_data)} products. "
                       f"Total revenue: ${total_revenue:,.2f}. "
                       f"Total units sold: {total_units:,}. "
                       f"Top product: {top_product.get('product')} "
                       f"(${top_product.get('revenue', 0):,.2f}).",
        "reasoning": "Establishing baseline performance before looking for anomalies. "
                     "Revenue and unit totals give context for what normal looks like."
    })

    # Store the exact sales snapshot the agent used — chart will read from this
    sales_snapshot = sales_data


    # Pre-compute all key metrics in Python — no room for LLM hallucination
    from collections import defaultdict
    total_revenue = sum(p["revenue"] for p in sales_data)
    total_units = sum(p["units_sold"] for p in sales_data)
    top_by_revenue = max(sales_data, key=lambda x: x["revenue"])
    top_by_units = max(sales_data, key=lambda x: x["units_sold"])
    category_revenue = defaultdict(float)
    for p in sales_data:
        category_revenue[p["category"]] += p["revenue"]
    top_category = max(category_revenue, key=category_revenue.get)

    # ── Step 2: Detect anomalies ──
    print(">> [Step 2] Running anomaly detection...")
    anomaly_raw = detect_anomalies()
    is_no_anomaly = anomaly_raw.startswith("No anomalies")
    anomaly_data = [] if is_no_anomaly else json.loads(anomaly_raw)

    if anomaly_data:
        # flagged = [f"{a['product']} ({a['type']}, {a['ratio']}x ratio)" for a in anomaly_data]
        flagged = [f"{a['product']} ({a['type']}, z={a['z_score']}, {a.get('confidence', 'N/A')} confidence)" for a in anomaly_data]

        obs = f"Detected {len(anomaly_data)} anomalies: {', '.join(flagged)}."
        reasoning = ("Z-score analysis detected statistically significant deviations from "
                    "the 30-day baseline. A z-score above 2.0 means the product is selling "
                    "more than 2 standard deviations above its mean — less than 5% chance "
                    "this is normal variation.")
    else:
        obs = "No anomalies detected. All products selling within normal range of their 30-day average."
        reasoning = ("Z-score computed for all 10 products against their 30-day mean and "
             "standard deviation. No product exceeded the ±2.0 standard deviation "
             "threshold — all sales within expected statistical range.")

    trace.append({
        "step": 2,
        "action": "Detect sales anomalies",
        "tool": "detect_anomalies",
        "observation": obs,
        "reasoning": reasoning
    })

    # ── Step 3: Check inventory ──
    print(">> [Step 3] Checking inventory status...")
    inventory_raw = get_inventory_status()
    inventory_data = json.loads(inventory_raw)
    low_stock = [p for p in inventory_data if p["status"] == "LOW STOCK"]
    out_of_stock = [p for p in inventory_data if p["units_in_stock"] == 0]

    if low_stock:
        flagged_inv = [f"{p['product']} ({p['units_in_stock']} units, "
                       f"{p['estimated_days_of_stock']} days left)" for p in low_stock]
        obs_inv = f"{len(low_stock)} products below threshold: {', '.join(flagged_inv)}."
        reasoning_inv = ("Products with less than 50 units are at risk of stockout. "
                         f"{len(out_of_stock)} products already at zero — "
                         "immediate restock needed to avoid lost sales.")
    else:
        obs_inv = "All products have healthy inventory levels above the 50-unit threshold."
        reasoning_inv = "No immediate inventory risk detected. Monitor weekly."

    trace.append({
        "step": 3,
        "action": "Check inventory levels",
        "tool": "get_inventory_status",
        "observation": obs_inv,
        "reasoning": reasoning_inv
    })


    # ── Step 3.5: Send alert email if critical issues found ──
    print(">> [Step 3.5] Checking if alert email needed...")
    inventory_data_parsed = json.loads(inventory_raw)
    email_result = send_alert_email(
        anomalies=anomaly_data if anomaly_data else [],
        inventory_alerts=inventory_data_parsed,
        summary=f"Agent run on {date.today().isoformat()}. "
                f"Total revenue: ${total_revenue:,.2f}. "
                f"Top product: {top_by_revenue['product']}."
                if 'total_revenue' in dir() else "See dashboard for details."
    )
    print(f">> {email_result}")

    trace.append({
        "step": "3.5",
        "action": "Send alert email",
        "tool": "send_alert_email (Gmail SMTP)",
        "observation": email_result,
        "reasoning": "Agent sends proactive alerts only when anomalies or critical "
                     "stockouts are detected — not on every run. This is the action "
                     "layer that makes the system autonomous, not just analytical."
    })

   # ── Step 4: LLM reasoning ──
    print(">> [Step 4] Sending to LLM for analysis...")
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""
You are an autonomous retail intelligence agent writing a retail performance report.
Use ONLY the pre-computed metrics below — do not recalculate or invent any numbers.

--- PRE-COMPUTED METRICS (use these exactly) ---
Total revenue (last 7 days): ${total_revenue:,.2f}
Total units sold: {total_units:,}
Top product by revenue: {top_by_revenue['product']} (${top_by_revenue['revenue']:,.2f})
Top product by units: {top_by_units['product']} ({top_by_units['units_sold']} units)
Top category by revenue: {top_category} (${category_revenue[top_category]:,.2f})

--- ANOMALY DETECTION ---
{anomaly_raw}

--- INVENTORY STATUS ---
{inventory_raw}

--- YOUR TASK ---
Write a JSON report using EXACTLY the numbers above. Do not add, recalculate or invent:
{{{{
  "date": "{date.today().isoformat()}",
  "summary": "2-3 sentences using the exact pre-computed numbers provided above",
  "anomalies": ["list each anomaly found, or write No anomalies detected if none"],
  "inventory_alerts": ["list each LOW STOCK product with units remaining and days of stock left"],
  "recommendations": ["3 specific actionable recommendations based on the data"]
}}}}

Return only valid JSON, no extra text.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    report_text = response.choices[0].message.content.strip()
    if report_text.startswith("```"):
        report_text = report_text.split("```")[1]
        if report_text.startswith("json"):
            report_text = report_text[4:]
    report_text = report_text.strip()

    trace.append({
        "step": 4,
        "action": "LLM reasoning and report generation",
        "tool": "llama-3.3-70b-versatile (Groq)",
        "observation": "LLM received all tool outputs and generated structured report.",
        "reasoning": "Synthesizing sales performance, anomaly signals, and inventory "
                     "risk into a unified report with prioritized recommendations."
    })

    print(">> [Step 4] LLM analysis complete.")

    # ── Step 5: Save report with trace ──
    print(">> [Step 5] Saving report...")
    try:
        report_json = json.loads(report_text)
    except json.JSONDecodeError:
        report_json = {"raw": report_text}

    report_json["agent_trace"] = trace
    report_json["date"] = date.today().isoformat()
    report_json["sales_snapshot"] = sales_snapshot  # exact data the agent analyzed

    save_report(json.dumps(report_json))

    trace.append({
        "step": 5,
        "action": "Save report to disk",
        "tool": "save_report",
        "observation": f"Report saved to reports/report_{date.today().isoformat()}.json",
        "reasoning": "Persisting report for dashboard retrieval and historical comparison."
    })

    print("\n" + "="*50)
    print("AGENT FINISHED")
    print("="*50 + "\n")

    return json.dumps(report_json)

if __name__ == "__main__":
    run_agent()