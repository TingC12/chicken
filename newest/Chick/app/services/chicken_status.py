# app/services/chicken_status.py
from __future__ import annotations
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from app.models.economy import Checkin, CheckinStatus, Run, RunStatus


def get_week_range_utc() -> tuple[datetime, datetime]:
    """
    回傳本週區間 [週一 00:00, 下週一 00:00)，使用 UTC。
    """
    today = datetime.utcnow().date()
    # Monday=0 ... Sunday=6
    monday = today - timedelta(days=today.weekday())
    week_start = datetime(monday.year, monday.month, monday.day)
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


def get_weekly_activity_count(db: Session, user_id: int) -> int:
    """
    計算本週運動次數：
    - 有效打卡（status in [verified, awarded]）
    - 有效跑步（status = awarded）
    """
    week_start, week_end = get_week_range_utc()

    # 打卡次數
    checkin_count = (
        db.query(Checkin)
        .filter(
            Checkin.user_id == user_id,
            Checkin.status.in_([CheckinStatus.verified, CheckinStatus.awarded]),
            Checkin.started_at >= week_start,
            Checkin.started_at < week_end,
        )
        .count()
    )

    # 跑步次數
    run_count = (
        db.query(Run)
        .filter(
            Run.user_id == user_id,
            Run.status == RunStatus.awarded,
            Run.created_at >= week_start,
            Run.created_at < week_end,
        )
        .count()
    )

    return checkin_count + run_count


def calc_chicken_status(activity_count: int) -> str:
    """
    REQ-EVO-006 規則（文字版）：
    - 每週運動未達 2 次 → 虛弱狀態（exp 吸收率 50%）
    - 每週運動達 3 次 → 一般狀態（exp 吸收率 100%）
    - 每週運動達 5 次 → 強壯狀態（exp 吸收率 150%）

    我們做一個合理分段：
    < 2    → "weak"
    2~4    → "normal"
    >= 5   → "strong"
    """
    if activity_count < 2:
        return "weak"
    elif activity_count < 5:
        return "normal"
    else:
        return "strong"


def chicken_exp_multiplier(status: str) -> float:
    """
    之後要套用在 EXP 計算上的倍率：
    - weak   → 0.5
    - normal → 1.0
    - strong → 1.5
    """
    if status == "weak":
        return 0.5
    elif status == "strong":
        return 1.5
    return 1.0


# ========================
#  🔥 Streak 用的新工具
# ========================

def get_all_activity_dates(db: Session, user_id: int) -> set[date]:
    """
    回傳該使用者「有運動」的所有日期集合（UTC 的日期）
    - 有效打卡：status in [verified, awarded] → 使用 started_at.date()
    - 有效跑步：status = awarded → 使用 created_at.date()
    """
    q1 = (
        db.query(Checkin.started_at)
        .filter(
            Checkin.user_id == user_id,
            Checkin.status.in_([CheckinStatus.verified, CheckinStatus.awarded]),
        )
        .all()
    )
    q2 = (
        db.query(Run.created_at)
        .filter(
            Run.user_id == user_id,
            Run.status == RunStatus.awarded,
        )
        .all()
    )

    dates: set[date] = set()
    for (dt,) in q1:
        if dt:
            dates.add(dt.date())
    for (dt,) in q2:
        if dt:
            dates.add(dt.date())
    return dates


def calc_current_streak(activity_dates: set[date]) -> int:
    """
    計算「從今天往回算」的連續運動天數。
    例如今天有運動、昨天有、前天沒 → streak = 2
    """
    if not activity_dates:
        return 0

    today = datetime.utcnow().date()
    streak = 0
    cur = today

    while cur in activity_dates:
        streak += 1
        cur = cur - timedelta(days=1)

    return streak
