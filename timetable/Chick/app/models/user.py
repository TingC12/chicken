# path: app/models/user.py
from datetime import datetime
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

def utcnow_naive() -> datetime:
    # 存「UTC 無時區」的 datetime
    return datetime.utcnow()

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), default="guest", index=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ★ 重點：和 MySQL DATETIME 對齊，不要 timezone=True
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow_naive)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
