# app/services/challenges.py

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.economy import WeeklyChallenge
from app.services.chicken_status import get_week_range_utc, get_weekly_activity_count
from app.services.ledger import add_ledger_entry
from app.services.level import apply_exp_and_update
from app.models.user import User

def get_or_create_this_week_challenge(db: Session, user: User) -> WeeklyChallenge:
    week_start, _ = get_week_range_utc()
    ws_date = week_start.date()

    row = (
        db.query(WeeklyChallenge)
        .filter(WeeklyChallenge.user_id == user.id, WeeklyChallenge.week_start == ws_date)
        .first()
    )
    if row:
        return row

    # 這邊你可以調整 target / reward
    row = WeeklyChallenge(
        user_id=user.id,
        week_start=ws_date,
        target_count=3,
        reward_coins=50,
        reward_exp=100,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def check_weekly_challenge(db: Session, user: User) -> WeeklyChallenge | None:
    """
    在每次運動成功（打卡 or 跑步）後呼叫。
    如果達成條件而且尚未完成，就發獎勵。
    """
    wc = get_or_create_this_week_challenge(db, user)
    if wc.completed_at is not None:
        return wc

    count = get_weekly_activity_count(db, user.id)
    if count < wc.target_count:
        return wc

    now = datetime.utcnow()
    wc.completed_at = now
    db.commit()

    if wc.reward_coins != 0:
        add_ledger_entry(
            db=db,
            user_id=user.id,
            delta=wc.reward_coins,
            source="weekly_challenge",
            ref_id=wc.id,
            idempotency_key=f"weekly_challenge:{user.id}:{wc.week_start}",
        )
    if wc.reward_exp != 0:
        apply_exp_and_update(user, wc.reward_exp)
        db.commit()

    return wc
