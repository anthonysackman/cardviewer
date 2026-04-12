"""PostgreSQL engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from config import SanicConfig

engine = create_engine(
    SanicConfig.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    class_=Session,
    autocommit=False,
    autoflush=False,
    bind=engine,
)
