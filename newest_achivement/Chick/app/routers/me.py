# app/routers/me.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from pydantic import BaseModel

from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.services.ledger import get_coins_balance
from app.schemas.economy import MeSummary
from app.models.economy import Checkin, CheckinStatus
from app.models.user import User
from app.services.chicken_status import (
    get_weekly_activity_count,
    calc_chicken_status,
    get_all_activity_dates,
    calc_current_streak,
)

router = APIRouter(prefix="/me", tags=["me"])

class ActivityDay(BaseModel):
    date: date
    active: bool

class ActivityCalendarOut(BaseModel):
    start_date: date
    end_date: date
    days: list[ActivityDay]
    
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

    # 5) 連續運動天數（streak）
    activity_dates = get_all_activity_dates(db, user_id)
    current_streak = calc_current_streak(activity_dates)

    # 6) 組出回傳
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
        current_streak=current_streak,
    )


@router.get("/activity_calendar", response_model=ActivityCalendarOut)
def get_activity_calendar(
    days: int = 60,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    給「火焰牆 / GitHub commit 牆」用的 API。

    - days: 要往回看幾天（預設 60，限制 1~365）
    - active = True 的日子，表示：
        - 有成功打卡（verified / awarded）
        - 或有成功跑步（awarded）
      這個邏輯由 get_all_activity_dates 幫你算好。
    """
    if days < 1 or days > 365:
        raise HTTPException(statuws_code=400, detail="days must be between 1 and 365")

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days - 1)

    # 這個會回傳「所有有運動的日期」，是個 set[date]
    activity_dates = get_all_activity_dates(db, user_id)

    day_list: list[ActivityDay] = []
    cur = start_date
    while cur <= today:
        day_list.append(ActivityDay(
            date=cur,
            active=(cur in activity_dates),
        ))
        cur = cur + timedelta(days=1)

    return ActivityCalendarOut(
        start_date=start_date,
        end_date=today,
        days=day_list,
    )
