"""
Database configuration.
Uses SQLite for zero-config local storage (swap SQLALCHEMY_DATABASE_URL
for Postgres/MySQL in production).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = os.path.join(os.path.dirname(__file__), "resume_screener.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
