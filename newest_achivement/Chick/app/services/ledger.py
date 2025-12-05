# path: app/services/ledger.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.models.economy import CoinsLedger

def get_coins_balance(db: Session, user_id: int) -> int:
    total = db.query(func.coalesce(func.sum(CoinsLedger.delta), 0)).filter(
        CoinsLedger.user_id == user_id
    ).scalar()
    return int(total or 0)

def add_ledger_entry(
    db: Session,
    user_id: int,
    delta: int,
    source: str,
    ref_id: int | None,
    idempotency_key: str | None,
) -> int:
    exists = db.query(CoinsLedger).filter(
        CoinsLedger.user_id == user_id,
        CoinsLedger.source == source,
        CoinsLedger.ref_id == ref_id
    ).first()
    if exists:
        return 0
    row = CoinsLedger(
        user_id=user_id,
        delta=delta,
        source=source,
        ref_id=ref_id,
        idempotency_key=idempotency_key,
        created_at=datetime.utcnow()
    )
    db.add(row)
    db.commit()
    return delta
