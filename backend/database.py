import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load environment variables (e.g., from .env)
load_dotenv()

# Supabase PostgreSQL URI
# Example: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/crm_db")

# Create SQLAlchemy engine with pool_pre_ping to prevent cloud connection drops
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

# Dependency for FastAPI to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
