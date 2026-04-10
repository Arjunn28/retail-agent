# simulator.py
# Generates realistic fake retail data and seeds the database.
# We generate 60 days of history so the agent has trends to detect.

import random
import os
from datetime import date, timedelta
from faker import Faker
from sqlalchemy.orm import Session
from backend.database import SessionLocal, DailySales, init_db

fake = Faker()
random.seed(42)  # makes results reproducible

# Our product catalogue — 10 products across 3 categories
PRODUCTS = [
    {"id": "P001", "name": "Wireless Headphones",  "category": "Electronics",  "base_sales": 30, "price": 59.99,  "stock": 200},
    {"id": "P002", "name": "Running Shoes",         "category": "Apparel",      "base_sales": 45, "price": 89.99,  "stock": 300},
    {"id": "P003", "name": "Protein Powder",        "category": "Health",       "base_sales": 25, "price": 39.99,  "stock": 150},
    {"id": "P004", "name": "Yoga Mat",              "category": "Health",       "base_sales": 20, "price": 29.99,  "stock": 180},
    {"id": "P005", "name": "Smart Watch",           "category": "Electronics",  "base_sales": 15, "price": 199.99, "stock": 100},
    {"id": "P006", "name": "Water Bottle",          "category": "Health",       "base_sales": 60, "price": 19.99,  "stock": 400},
    {"id": "P007", "name": "Denim Jacket",          "category": "Apparel",      "base_sales": 18, "price": 79.99,  "stock": 120},
    {"id": "P008", "name": "Bluetooth Speaker",     "category": "Electronics",  "base_sales": 22, "price": 49.99,  "stock": 160},
    {"id": "P009", "name": "Resistance Bands",      "category": "Health",       "base_sales": 35, "price": 14.99,  "stock": 250},
    {"id": "P010", "name": "Casual Sneakers",       "category": "Apparel",      "base_sales": 40, "price": 69.99,  "stock": 220},
]

def generate_sales_for_day(product: dict, sale_date: date, inventory: int) -> DailySales:
    """Generate one row of sales data for a product on a given date."""

    # Auto-restock if inventory runs low — keeps data realistic over long periods
    if inventory < 20:
        inventory = product["stock"]

    # Add realistic noise: sales vary ±30% day to day
    noise = random.uniform(0.7, 1.3)

    # Weekend boost: people shop more on weekends
    weekend_boost = 1.3 if sale_date.weekday() >= 5 else 1.0

    # Occasionally inject an anomaly (spike or crash) — the agent needs to detect these
    anomaly = 1.0
    if random.random() < 0.05:   # 5% chance of a spike
        anomaly = random.uniform(2.5, 4.0)
    elif random.random() < 0.03: # 3% chance of a crash
        anomaly = random.uniform(0.1, 0.3)

    units = max(1, int(product["base_sales"] * noise * weekend_boost * anomaly))
    units = min(units, inventory)  # can't sell more than you have
    revenue = round(units * product["price"], 2)
    new_inventory = max(0, inventory - units)

    return DailySales(
        date=sale_date,
        product_id=product["id"],
        product_name=product["name"],
        category=product["category"],
        units_sold=units,
        revenue=revenue,
        inventory=new_inventory,
    )

def seed_database(days_of_history: int = 60):
    """Seed the database with 60 days of historical data."""
    init_db()
    db: Session = SessionLocal()

    # Check if data already exists — don't re-seed if it does
    existing = db.query(DailySales).count()
    if existing > 0:
        print(f"Database already has {existing} rows. Skipping seed.")
        db.close()
        return

    print(f"Seeding {days_of_history} days of data for {len(PRODUCTS)} products...")

    start_date = date.today() - timedelta(days=days_of_history)
    inventory_tracker = {p["id"]: p["stock"] for p in PRODUCTS}

    for day_offset in range(days_of_history):
        current_date = start_date + timedelta(days=day_offset)
        for product in PRODUCTS:
            row = generate_sales_for_day(product, current_date, inventory_tracker[product["id"]])
            inventory_tracker[product["id"]] = row.inventory
            db.add(row)

    db.commit()
    db.close()
    total = days_of_history * len(PRODUCTS)
    print(f"Done! Inserted {total} rows into the database.")

def add_todays_data():
    """Add today's sales — called by the scheduler in Phase 4."""
    db: Session = SessionLocal()
    today = date.today()

    # Don't add duplicate data for today
    existing = db.query(DailySales).filter(DailySales.date == today).first()
    if existing:
        print("Today's data already exists.")
        db.close()
        return

    inventory_tracker = {}
    for product in PRODUCTS:
        latest = (
            db.query(DailySales)
            .filter(DailySales.product_id == product["id"])
            .order_by(DailySales.date.desc())
            .first()
        )
        inventory_tracker[product["id"]] = latest.inventory if latest else product["stock"]

    for product in PRODUCTS:
        row = generate_sales_for_day(product, today, inventory_tracker[product["id"]])
        db.add(row)

    db.commit()
    db.close()
    print(f"Added today's data ({today}) for {len(PRODUCTS)} products.")

if __name__ == "__main__":
    seed_database()