from sqlalchemy import create_engine, Column, Integer, String, Float, Date, text
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# This tells SQLAlchemy where the database file lives
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/retail.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# This is our sales table — one row = one product's sales on one day
class DailySales(Base):
    __tablename__ = "daily_sales"

    id          = Column(Integer, primary_key=True, index=True)
    date        = Column(Date, nullable=False)
    product_id  = Column(String, nullable=False)
    product_name= Column(String, nullable=False)
    category    = Column(String, nullable=False)
    units_sold  = Column(Integer, nullable=False)
    revenue     = Column(Float, nullable=False)
    inventory   = Column(Integer, nullable=False)  # units remaining in stock

class AgentReport(Base):
    __tablename__ = "agent_reports"

    id           = Column(Integer, primary_key=True, index=True)
    generated_at = Column(Date, nullable=False)
    report       = Column(String, nullable=False)  # JSON string

# This creates the actual table in the database file
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print("Database initialised at:", DB_PATH)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()