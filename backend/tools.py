# tools.py
# These are the "superpowers" we give the agent.
# Each function does one specific job. The LLM will decide which ones to call and when.

import json
import os
from datetime import date, timedelta
from sqlalchemy import text
from backend.database import SessionLocal

# ─────────────────────────────────────────────
# TOOL 1: Query the sales database
# The agent calls this to get raw sales numbers.
# ─────────────────────────────────────────────
def query_sales_db(days: int = 7) -> str:
    """
    Returns a summary of sales for the last N days.
    The agent uses this to understand what's been happening recently.
    """
    db = SessionLocal()
    cutoff = date.today() - timedelta(days=days)

    rows = db.execute(text("""
        SELECT
            product_name,
            category,
            SUM(units_sold)  AS total_units,
            ROUND(SUM(revenue), 2) AS total_revenue,
            MIN(inventory)   AS current_inventory
        FROM daily_sales
        WHERE date >= :cutoff
        GROUP BY product_id, product_name, category
        ORDER BY total_revenue DESC
    """), {"cutoff": str(cutoff)}).fetchall()

    db.close()

    if not rows:
        return "No sales data found for this period."

    result = []
    for row in rows:
        result.append({
            "product": row.product_name,
            "category": row.category,
            "units_sold": row.total_units,
            "revenue": row.total_revenue,
            "current_inventory": row.current_inventory,
        })

    return json.dumps(result, indent=2)


# ─────────────────────────────────────────────
# TOOL 2: Detect anomalies
# The agent calls this to find unusual spikes or crashes in sales.
# ─────────────────────────────────────────────
def detect_anomalies(threshold: float = 2.0) -> str:
    """
    Compares each product's last 3 days of sales against its 30-day average.
    If sales are 2x higher or 50% lower than normal, it's flagged as an anomaly.
    The threshold parameter controls how sensitive the detection is.
    """
    db = SessionLocal()

    # Get 30-day average sales per product
    rows = db.execute(text("""
        SELECT
            product_id,
            product_name,
            category,
            AVG(units_sold) AS avg_units,
            MAX(date)       AS latest_date
        FROM daily_sales
        WHERE date >= :cutoff
        GROUP BY product_id, product_name, category
    """), {"cutoff": str(date.today() - timedelta(days=30))}).fetchall()

    anomalies = []

    for row in rows:
        # Get the last 3 days for this product
        recent = db.execute(text("""
            SELECT AVG(units_sold) AS recent_avg
            FROM daily_sales
            WHERE product_id = :pid
              AND date >= :cutoff
        """), {
            "pid": row.product_id,
            "cutoff": str(date.today() - timedelta(days=3))
        }).fetchone()

        if not recent or recent.recent_avg is None:
            continue

        ratio = recent.recent_avg / row.avg_units if row.avg_units > 0 else 1.0

        if ratio >= threshold:
            anomalies.append({
                "product": row.product_name,
                "category": row.category,
                "type": "SPIKE",
                "recent_avg_units": round(recent.recent_avg, 1),
                "normal_avg_units": round(row.avg_units, 1),
                "ratio": round(ratio, 2),
                "message": f"Selling {round(ratio, 1)}x faster than normal"
            })
        elif ratio <= 0.5:
            anomalies.append({
                "product": row.product_name,
                "category": row.category,
                "type": "CRASH",
                "recent_avg_units": round(recent.recent_avg, 1),
                "normal_avg_units": round(row.avg_units, 1),
                "ratio": round(ratio, 2),
                "message": f"Selling {round(1 - ratio, 1)*100:.0f}% below normal"
            })

    db.close()

    if not anomalies:
        return "No anomalies detected. Sales are within normal range for all products."

    return json.dumps(anomalies, indent=2)


# ─────────────────────────────────────────────
# TOOL 3: Check inventory status
# The agent calls this to find products that are running low on stock.
# ─────────────────────────────────────────────
def get_inventory_status(low_stock_threshold: int = 50) -> str:
    """
    Returns inventory levels for all products.
    Products below the threshold are flagged as low stock.
    This helps the agent warn about potential stockouts.
    """
    db = SessionLocal()

    rows = db.execute(text("""
        SELECT
            product_name,
            category,
            inventory,
            units_sold
        FROM daily_sales
        WHERE date = (SELECT MAX(date) FROM daily_sales)
        ORDER BY inventory ASC
    """)).fetchall()

    db.close()

    if not rows:
        return "No inventory data available."

    inventory_report = []
    for row in rows:
        days_left = round(row.inventory / row.units_sold, 1) if row.units_sold > 0 else 999
        status = "LOW STOCK" if row.inventory < low_stock_threshold else "OK"

        inventory_report.append({
            "product": row.product_name,
            "category": row.category,
            "units_in_stock": row.inventory,
            "status": status,
            "estimated_days_of_stock": days_left,
        })

    return json.dumps(inventory_report, indent=2)


# ─────────────────────────────────────────────
# TOOL 4: Save the agent's report
# After the agent finishes reasoning, it calls this to save its findings.
# ─────────────────────────────────────────────
def save_report(report_content: str) -> str:
    """
    Saves the agent's final report as a JSON file in the /reports folder.
    Each report is timestamped so we can see history over time.
    """
    os.makedirs("reports", exist_ok=True)
    timestamp = date.today().isoformat()
    filename = f"reports/report_{timestamp}.json"

    report = {
        "generated_at": timestamp,
        "report": report_content,
    }

    with open(filename, "w") as f:
        json.dump(report, f, indent=2)

    return f"Report saved successfully to {filename}"