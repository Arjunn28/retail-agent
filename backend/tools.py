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
# TOOL 2: Detect anomalies using z-score statistics
# Z-score measures how many standard deviations a value is from the mean.
# This is how real anomaly detection works — not just simple thresholds.
# ─────────────────────────────────────────────
def detect_anomalies(threshold: float = 2.0) -> str:
    """
    Uses z-score statistical analysis to detect anomalies.
    A z-score > 2.0 means the product is selling 2+ standard deviations
    above its 30-day mean — statistically unusual with ~95% confidence.
    A z-score < -2.0 means the opposite — a significant crash.
    """
    import math
    db = SessionLocal()

    # Get all daily sales for the last 30 days per product
    rows = db.execute(text("""
        SELECT
            product_id,
            product_name,
            category,
            date,
            units_sold
        FROM daily_sales
        WHERE date >= :cutoff
        ORDER BY product_id, date
    """), {"cutoff": str(date.today() - timedelta(days=30))}).fetchall()

    db.close()

    if not rows:
        return "No sales data found for anomaly detection."

    # Group daily sales by product
    from collections import defaultdict
    product_sales = defaultdict(list)
    product_info = {}

    for row in rows:
        product_sales[row.product_id].append(row.units_sold)
        product_info[row.product_id] = {
            "name": row.product_name,
            "category": row.category,
        }

    anomalies = []

    for product_id, daily_units in product_sales.items():
        if len(daily_units) < 7:
            continue  # need at least 7 days to compute meaningful stats

        # Compute mean and standard deviation over the 30-day window
        mean = sum(daily_units) / len(daily_units)
        variance = sum((x - mean) ** 2 for x in daily_units) / len(daily_units)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            continue  # no variance means no anomaly possible

        # Use the last 3 days as the "recent" window
        recent_days = daily_units[-3:]
        recent_avg = sum(recent_days) / len(recent_days)

        # Z-score: how many standard deviations is recent avg from the mean?
        z_score = (recent_avg - mean) / std_dev

        info = product_info[product_id]

        if z_score >= threshold:
            anomalies.append({
                "product": info["name"],
                "category": info["category"],
                "type": "SPIKE",
                "z_score": round(z_score, 2),
                "recent_avg_units": round(recent_avg, 1),
                "mean_units": round(mean, 1),
                "std_dev": round(std_dev, 2),
                "confidence": f"{min(99.9, round((1 - 2 * (1 - _normal_cdf(abs(z_score)))) * 100, 1))}%",
                "message": f"Selling {round(z_score, 1)} std devs above 30-day mean "
                           f"(recent: {round(recent_avg, 1)} units vs mean: {round(mean, 1)} ± {round(std_dev, 2)})"
            })
        elif z_score <= -threshold:
            anomalies.append({
                "product": info["name"],
                "category": info["category"],
                "type": "CRASH",
                "z_score": round(z_score, 2),
                "recent_avg_units": round(recent_avg, 1),
                "mean_units": round(mean, 1),
                "std_dev": round(std_dev, 2),
                "confidence": f"{min(99.9, round((1 - 2 * (1 - _normal_cdf(abs(z_score)))) * 100, 1))}%",
                "message": f"Selling {round(abs(z_score), 1)} std devs below 30-day mean "
                           f"(recent: {round(recent_avg, 1)} units vs mean: {round(mean, 1)} ± {round(std_dev, 2)})"
            })

    if not anomalies:
        return "No anomalies detected. All products within 2 standard deviations of their 30-day mean."

    return json.dumps(anomalies, indent=2)


def _normal_cdf(z: float) -> float:
    """
    Approximation of the normal CDF — used to compute statistical confidence.
    Tells us the probability that a z-score this extreme occurred by chance.
    """
    import math
    return (1.0 + math.erf(z / math.sqrt(2))) / 2


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
    Saves the agent's final report to the database AND to disk as backup.
    Using the database means reports persist on Render's free tier.
    """
    from backend.database import SessionLocal, AgentReport
    import os

    today = date.today()
    db = SessionLocal()

    # Check if a report already exists for today — update it if so
    existing = db.query(AgentReport).filter(
        AgentReport.generated_at == today
    ).first()

    if existing:
        existing.report = report_content
    else:
        db.add(AgentReport(
            generated_at=today,
            report=report_content,
        ))

    db.commit()
    db.close()

    # Also save to disk as backup (works locally)
    os.makedirs("reports", exist_ok=True)
    filename = f"reports/report_{today.isoformat()}.json"
    with open(filename, "w") as f:
        json.dump({"generated_at": today.isoformat(), "report": report_content}, f, indent=2)

    return f"Report saved successfully to database and {filename}"


def get_latest_report_from_db():
    """Fetches the most recent report from the database."""
    from backend.database import SessionLocal, AgentReport
    db = SessionLocal()
    report = db.query(AgentReport).order_by(
        AgentReport.generated_at.desc()
    ).first()
    db.close()
    if not report:
        return None
    return {"generated_at": report.generated_at.isoformat(), "report": report.report}


def get_all_reports_from_db() -> list:
    """Fetches all reports from the database, newest first."""
    from backend.database import SessionLocal, AgentReport
    db = SessionLocal()
    reports = db.query(AgentReport).order_by(
        AgentReport.generated_at.desc()
    ).all()
    db.close()
    return [
        {"generated_at": r.generated_at.isoformat(), "report": r.report}
        for r in reports
    ]


# ─────────────────────────────────────────────
# TOOL 5: Send alert email
# The agent calls this when it finds anomalies or critical stockouts.
# This is the "action layer" — the agent doesn't just report, it acts.
# ─────────────────────────────────────────────
def send_alert_email(anomalies: list, inventory_alerts: list, summary: str) -> str:
    """
    Sends a real email alert when the agent detects critical issues.
    Only sends if there are anomalies OR products with less than 2 days of stock.
    Uses Gmail SMTP — free, no third-party service needed.
    """
    import smtplib
    import os
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from dotenv import load_dotenv

    load_dotenv()

    sender = os.getenv("ALERT_EMAIL_SENDER")
    password = os.getenv("ALERT_EMAIL_PASSWORD")
    receiver = os.getenv("ALERT_EMAIL_RECEIVER")

    if not all([sender, password, receiver]):
        return "Email not configured — skipping alert."

    # Only alert on real anomalies or critical stockouts (< 2 days)
    real_anomalies = [a for a in anomalies if isinstance(a, dict)]
    critical_stock = [
        i for i in inventory_alerts
        if isinstance(i, dict) and i.get("estimated_days_of_stock", 999) < 2
    ]

    if not real_anomalies and not critical_stock:
        return "No critical issues found — email alert not sent."

    # Build the email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 Retail Agent Alert: {len(real_anomalies)} anomalies, {len(critical_stock)} critical stockouts ({date.today().isoformat()})"
    msg["From"] = sender
    msg["To"] = receiver

    # Plain text version
    text_parts = [
        f"RETAIL INTELLIGENCE AGENT — ALERT REPORT",
        f"Date: {date.today().isoformat()}",
        f"",
        f"SUMMARY",
        f"{summary}",
        f"",
    ]

    if real_anomalies:
        text_parts.append("ANOMALIES DETECTED")
        for a in real_anomalies:
            text_parts.append(
                f"• {a['product']} ({a['type']}) — "
                f"Z-score: {a['z_score']} | Confidence: {a.get('confidence', 'N/A')} | "
                f"{a['message']}"
            )
        text_parts.append("")

    if critical_stock:
        text_parts.append("CRITICAL STOCKOUTS (< 2 days remaining)")
        for i in critical_stock:
            text_parts.append(
                f"• {i['product']} — {i['units_in_stock']} units, "
                f"{i['estimated_days_of_stock']} days left"
            )
        text_parts.append("")

    text_parts.append(f"View full dashboard: https://retail-agent-self.vercel.app")
    text_body = "\n".join(text_parts)

    # HTML version — looks much better in email clients
    anomaly_rows = ""
    for a in real_anomalies:
        anomaly_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{a['product']}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:#f9a825">{a['type']}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{a['z_score']}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{a.get('confidence','N/A')}</td>
        </tr>"""

    stock_rows = ""
    for i in critical_stock:
        stock_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{i['product']}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:#ea4335">{i['units_in_stock']} units</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:#ea4335">{i['estimated_days_of_stock']} days</td>
        </tr>"""

    html_body = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
        <div style="background:#1a1a2e;color:white;padding:20px;border-radius:8px;margin-bottom:20px">
            <h2 style="margin:0">🚨 Retail Intelligence Agent</h2>
            <p style="margin:4px 0;opacity:0.7">Autonomous alert — {date.today().isoformat()}</p>
        </div>

        <div style="background:#f9f9f9;padding:16px;border-radius:8px;margin-bottom:16px">
            <h3 style="margin:0 0 8px">Summary</h3>
            <p style="margin:0;color:#444">{summary}</p>
        </div>

        {"<h3>⚡ Anomalies detected</h3><table width='100%' style='border-collapse:collapse'><tr style='background:#f5f5f5'><th style='padding:8px;text-align:left'>Product</th><th style='padding:8px;text-align:left'>Type</th><th style='padding:8px;text-align:left'>Z-Score</th><th style='padding:8px;text-align:left'>Confidence</th></tr>" + anomaly_rows + "</table>" if anomaly_rows else ""}

        {"<h3>📦 Critical stockouts</h3><table width='100%' style='border-collapse:collapse'><tr style='background:#f5f5f5'><th style='padding:8px;text-align:left'>Product</th><th style='padding:8px;text-align:left'>Units left</th><th style='padding:8px;text-align:left'>Days left</th></tr>" + stock_rows + "</table>" if stock_rows else ""}

        <div style="margin-top:24px;padding:16px;background:#e8f5e9;border-radius:8px">
            <a href="https://retail-agent-self.vercel.app"
               style="color:#2d7a3a;font-weight:500;text-decoration:none">
               View full dashboard →
            </a>
        </div>
    </body></html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        return f"Alert email sent successfully to {receiver}"
    except Exception as e:
        return f"Email failed: {str(e)}"