# path: app/routers/checkins.py
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.models.economy import Checkin, CheckinStatus
from app.schemas.economy import (
    CheckinStartIn, CheckinStartOut, CheckinHeartbeatIn,
    CheckinEndIn, CheckinEndOut, CheckinRow
)
from app.services.ledger import add_ledger_entry

router = APIRouter(prefix="/checkins", tags=["checkins"])

CHECKIN_AWARD_COINS = 100
REQUIRED_MINUTES = 30

@router.post("/start", response_model=CheckinStartOut)
def checkin_start(payload: CheckinStartIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    row = Checkin(
        user_id=user_id,
        start_lat=payload.lat,
        start_lng=payload.lng,
        started_at=now,
        status=CheckinStatus.started,
        created_at=now
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CheckinStartOut(checkin_id=row.id, status=row.status, started_at=row.started_at)

@router.post("/heartbeat")
def checkin_heartbeat(payload: CheckinHeartbeatIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.query(Checkin).filter(Checkin.id == payload.checkin_id, Checkin.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checkin not found")
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}

@router.post("/end", response_model=CheckinEndOut)
def checkin_end(payload: CheckinEndIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.query(Checkin).filter(Checkin.id == payload.checkin_id, Checkin.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checkin not found")
    if row.status not in (CheckinStatus.started, CheckinStatus.ended):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid status: {row.status}")

    now = datetime.utcnow()
    row.end_lat = payload.lat
    row.end_lng = payload.lng
    row.ended_at = now
    row.status = CheckinStatus.ended

    dwell = int((row.ended_at - row.started_at).total_seconds() // 60)
    row.dwell_minutes = dwell

    if dwell < REQUIRED_MINUTES:
        row.status = CheckinStatus.rejected
        row.reason = "DWELL_TOO_SHORT"
        db.commit()
        return CheckinEndOut(verified=False, dwell_minutes=dwell, coins_awarded=0)

    row.status = CheckinStatus.verified
    db.commit()

    awarded = add_ledger_entry(
        db=db,
        user_id=user_id,
        delta=CHECKIN_AWARD_COINS,
        source="checkin",
        ref_id=row.id,
        idempotency_key=f"checkin:{row.id}"
    )
    row.coins_awarded = awarded
    if awarded > 0:
        row.status = CheckinStatus.awarded
    db.commit()

    return CheckinEndOut(verified=True, dwell_minutes=dwell, coins_awarded=awarded)

@router.get("/latest", response_model=CheckinRow)
def checkin_latest(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.query(Checkin).filter(Checkin.user_id == user_id).order_by(Checkin.id.desc()).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no checkins")
    return CheckinRow(
        id=row.id, status=row.status, dwell_minutes=row.dwell_minutes,
        coins_awarded=row.coins_awarded, reason=row.reason,
        started_at=row.started_at, ended_at=row.ended_at
    )

@router.get("/history", response_model=list[CheckinRow])
def checkin_history(limit: int = 50, offset: int = 0, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.query(Checkin).filter(Checkin.user_id == user_id).order_by(Checkin.id.desc()).offset(offset).limit(limit).all()
    return [
        CheckinRow(
            id=r.id, status=r.status, dwell_minutes=r.dwell_minutes,
            coins_awarded=r.coins_awarded, reason=r.reason,
            started_at=r.started_at, ended_at=r.ended_at
        ) for r in rows
    ]
