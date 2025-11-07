# path: app/routers/me.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.services.ledger import get_coins_balance
from app.schemas.economy import MeSummary
from app.models.economy import Checkin

router = APIRouter(prefix="/me", tags=["me"])

@router.get("", response_model=MeSummary)
def read_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    coins = get_coins_balance(db, user_id)
    today = datetime.utcnow().date()
    latest = db.query(Checkin).filter(Checkin.user_id == user_id).order_by(Checkin.id.desc()).first()
    if latest and latest.started_at and latest.started_at.date() == today and latest.status.name in ("started","verified","awarded"):
        today_status = latest.status.name
    else:
        today_status = "none"
    return MeSummary(user_id=user_id, status="guest", coins=coins, today_checkin_status=today_status, last_login_at=None)
