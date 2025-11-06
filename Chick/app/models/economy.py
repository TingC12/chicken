# ============================
# path: app/models/economy.py
# ============================
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Enum, DECIMAL, Index
from sqlalchemy.orm import declarative_base
import enum
from datetime import datetime
from app.core.db import Base  # 你的 Base

class CheckinStatus(str, enum.Enum):
    started = "started"
    ended = "ended"
    verified = "verified"
    rejected = "rejected"
    awarded = "awarded"

class RunStatus(str, enum.Enum):
    submitted = "submitted"
    rejected = "rejected"
    awarded = "awarded"

class CoinsLedger(Base):
    __tablename__ = "coins_ledger"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    delta = Column(Integer, nullable=False)
    source = Column(String(32), nullable=False)         # 'checkin' | 'run' | 'purchase' | ...
    ref_id = Column(BigInteger, nullable=True)          # 對應 checkins.id / runs.id / purchases.id
    idempotency_key = Column(String(64), nullable=True) # 防重入
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_coins_user_created", "user_id", "created_at"),
    )

class Checkin(Base):
    __tablename__ = "checkins"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    start_lat = Column(DECIMAL(9,6), nullable=True)
    start_lng = Column(DECIMAL(9,6), nullable=True)
    end_lat = Column(DECIMAL(9,6), nullable=True)
    end_lng = Column(DECIMAL(9,6), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    dwell_minutes = Column(Integer, nullable=True)
    coins_awarded = Column(Integer, nullable=False, default=0)
    status = Column(Enum(CheckinStatus), nullable=False, default=CheckinStatus.started)
    reason = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_checkins_user_created", "user_id", "created_at"),
    )

class Run(Base):
    __tablename__ = "runs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    distance_km = Column(DECIMAL(6,3), nullable=False)
    duration_sec = Column(Integer, nullable=False)
    max_speed_kmh = Column(DECIMAL(5,2), nullable=False)
    coins_awarded = Column(Integer, nullable=False, default=0)
    status = Column(Enum(RunStatus), nullable=False, default=RunStatus.submitted)
    reason = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_runs_user_created", "user_id", "created_at"),
    )
