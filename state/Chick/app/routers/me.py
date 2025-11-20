# path: app/routers/me.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.services.ledger import get_coins_balance
from app.schemas.economy import MeSummary
from app.models.economy import Checkin, CheckinStatus
from app.models.user import User
from app.services.chicken_status import (
    get_weekly_activity_count,
    calc_chicken_status,
)

router = APIRouter(prefix="/me", tags=["me"])


def get_today_checkin_status(db: Session, user_id: int) -> str:
    """
    檢查今天是否有打卡，以及狀態為何（started/verified/awarded）
    """
    today = datetime.utcnow().date()
    latest = (
        db.query(Checkin)
        .filter(Checkin.user_id == user_id)
        .order_by(Checkin.id.desc())
        .first()
    )

    if (
        latest
        and latest.started_at
        and latest.started_at.date() == today
        and latest.status in (
            CheckinStatus.started,
            CheckinStatus.verified,
            CheckinStatus.awarded,
        )
    ):
        return latest.status.name

    return "none"


@router.get("", response_model=MeSummary)
def read_me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # 1) 撈 user 看 exp / level / status / last_login_at
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # 2) 金幣餘額
    coins = get_coins_balance(db, user_id)

    # 3) 今天打卡狀態
    today_status = get_today_checkin_status(db, user_id)

    # 4) 本週運動次數 & 小雞狀態
    weekly_count = get_weekly_activity_count(db, user_id)
    chicken_status = calc_chicken_status(weekly_count)

    # 5) 組出回傳
    return MeSummary(
        user_id=user_id,
        status=user.status if user.status in ("guest", "user", "admin") else "guest",
        coins=coins,
        today_checkin_status=today_status,
        last_login_at=user.last_login_at,
        exp=user.exp or 0,
        level=user.level or 1,
        chicken_status=chicken_status,
        weekly_activity_count=weekly_count,
    )
