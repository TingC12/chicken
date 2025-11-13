# path: app/routers/runs.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from random import randint
from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.models.economy import Run, RunStatus
from app.schemas.economy import RunSummaryIn, RunSummaryOut, RunRow
from app.services.ledger import add_ledger_entry

router = APIRouter(prefix="/runs", tags=["runs"])
MAX_VALID_SPEED = 20.0  # km/h

@router.post("/summary", response_model=RunSummaryOut)
def runs_summary(payload: RunSummaryIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    if float(payload.max_speed_kmh) > MAX_VALID_SPEED:
        row = Run(
            user_id=user_id,
            distance_km=payload.distance_km,
            duration_sec=payload.duration_sec,
            max_speed_kmh=payload.max_speed_kmh,
            status=RunStatus.rejected,
            reason="OVERSPEED",
            created_at=datetime.utcnow()
        )
        db.add(row)
        db.commit()
        return RunSummaryOut(coins_awarded=0, status=row.status)

    random_unit = randint(25, 50)
    coins = int(float(payload.distance_km) * random_unit)

    row = Run(
        user_id=user_id,
        distance_km=payload.distance_km,
        duration_sec=payload.duration_sec,
        max_speed_kmh=payload.max_speed_kmh,
        status=RunStatus.awarded,
        coins_awarded=coins,
        created_at=datetime.utcnow()
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    add_ledger_entry(
        db=db, user_id=user_id, delta=coins,
        source="run", ref_id=row.id, idempotency_key=f"run:{row.id}"
    )
    return RunSummaryOut(coins_awarded=coins, status=row.status)

@router.get("/history", response_model=list[RunRow])
def runs_history(limit: int = 50, offset: int = 0, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.query(Run).filter(Run.user_id == user_id).order_by(Run.id.desc()).offset(offset).limit(limit).all()
    return [
        RunRow(
            id=r.id, distance_km=float(r.distance_km), duration_sec=r.duration_sec,
            max_speed_kmh=float(r.max_speed_kmh), coins_awarded=r.coins_awarded,
            status=r.status, reason=r.reason, created_at=r.created_at
        ) for r in rows
    ]
