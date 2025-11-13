# path: app/models/economy.py
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Enum, DECIMAL, Index
from sqlalchemy.orm import Mapped, mapped_column
import enum
from datetime import datetime
from app.core.db import Base
from app.models.user import utcnow_naive  # 直接重用

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
    source = Column(String(32), nullable=False)
    ref_id = Column(BigInteger, nullable=True)
    idempotency_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("idx_coins_user_created", "user_id", "created_at"),)

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
    # 👇 新增：細緻計算用
    accum_minutes = Column(Integer, nullable=False, default=0)  # 已累積的運動分鐘
    last_tick_at = Column(DateTime, nullable=True)              # 上次累計的時間
    
    status = Column(Enum(CheckinStatus), nullable=False, default=CheckinStatus.started)
    reason = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    __table_args__ = (Index("idx_checkins_user_created", "user_id", "created_at"),)

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
    __table_args__ = (Index("idx_runs_user_created", "user_id", "created_at"),)

class TrainingLog(Base):
    __tablename__ = "training_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    exercise_name: Mapped[str] = mapped_column(String(64), nullable=False)
    weight_kg: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=utcnow_naive, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=utcnow_naive
    )