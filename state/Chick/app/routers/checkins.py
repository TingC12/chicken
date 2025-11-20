# path: app/routers/checkins.py
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.models.economy import Checkin, CheckinStatus
from app.schemas.economy import (
    CheckinStartIn, CheckinStartOut, CheckinHeartbeatIn,
    CheckinEndIn, CheckinEndOut, CheckinRow, CheckinRewindStartIn
)
from app.services.ledger import add_ledger_entry
from app.models.user import User
from app.services.level import apply_exp_and_update
from app.services.chicken_status import (
    get_weekly_activity_count,
    calc_chicken_status,
    chicken_exp_multiplier,
)

from sqlalchemy import text
import math
from sqlalchemy import and_


router = APIRouter(prefix="/checkins", tags=["checkins"])


CHECKIN_AWARD_COINS = 100      # 原本 30 分一次性 100，等等可以改公式
REQUIRED_MINUTES = 30          # 至少 30 分才算成功
MAX_ACCUM_MINUTES = 60         # 每次 checkin 最多累積 40 分鐘
COINS_PER_5_MIN = 10           # 每 5 分鐘給幾幣（60 分就是 12*10=120，自己調整）
MAX_DAILY_AWARDED_CHECKINS = 2 # 每天最多幾次有獎勵的打卡


@router.post("/start", response_model=CheckinStartOut)
def checkin_start(payload: CheckinStartIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    row = Checkin(
        user_id=user_id,
        start_lat=payload.lat,
        start_lng=payload.lng,
        started_at=now,
        status=CheckinStatus.started,
        created_at=now,
        accum_minutes=0,      # 👈 新增
        last_tick_at=now,     # 👈 新增
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CheckinStartOut(checkin_id=row.id, status=row.status, started_at=row.started_at)

@router.post("/heartbeat")
def checkin_heartbeat(payload: CheckinHeartbeatIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.query(Checkin).filter(
        Checkin.id == payload.checkin_id,
        Checkin.user_id == user_id
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checkin not found")
    if row.status not in (CheckinStatus.started, CheckinStatus.ended):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid status: {row.status}")

    now = datetime.utcnow()
    last = row.last_tick_at or row.started_at
    delta_min = int((now - last).total_seconds() // 60)

    if delta_min > 0 and row.accum_minutes < MAX_ACCUM_MINUTES:
        gain = min(delta_min, MAX_ACCUM_MINUTES - row.accum_minutes)
        row.accum_minutes += gain
        row.last_tick_at = last + timedelta(minutes=gain)

    row.updated_at = now
    db.commit()
    return {"ok": True, "accum_minutes": row.accum_minutes}

# 👇 這裡是新加的 debug 版 API
@router.post("/rewind_start", response_model=CheckinRow)
def checkin_rewind_start(
    payload: CheckinRewindStartIn,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    ⚠️ Debug 專用：
    把某一筆 checkin 的 started_at / created_at 往前調 N 分鐘，
    讓你可以不用手改 DB 就測試「已經待超過 30 分鐘」的情況。
    """
    row = db.query(Checkin).filter(
        Checkin.id == payload.checkin_id,
        Checkin.user_id == user_id
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="checkin not found"
        )

    # 通常只有 status=started 才有意義，避免已經結束的亂改
    if row.status != CheckinStatus.started:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"cannot rewind when status={row.status}"
        )

    delta = timedelta(minutes=payload.rewind_minutes)

    # 讓「開始時間」看起來更早
    if row.started_at:
        row.started_at -= delta

    # created_at 也一起倒退，讓歷史紀錄看起來合理
    if hasattr(row, "created_at") and row.created_at:
        row.created_at -= delta

    # ⭐ 關鍵：把 last_tick_at 也一起往前調
    if hasattr(row, "last_tick_at") and row.last_tick_at:
        row.last_tick_at -= delta

    # （accum_minutes 暫時不用動，單純靠 last_tick_at 就能假裝時間過很久）

    db.commit()
    db.refresh(row)

    return CheckinRow(
        id=row.id,
        status=row.status,
        dwell_minutes=row.dwell_minutes,
        coins_awarded=row.coins_awarded,
        reason=row.reason,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )
    
@router.post("/end", response_model=CheckinEndOut)
def checkin_end(payload: CheckinEndIn, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.query(Checkin).filter(
        Checkin.id == payload.checkin_id,
        Checkin.user_id == user_id
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checkin not found")
    if row.status not in (CheckinStatus.started, CheckinStatus.ended):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid status: {row.status}")

    now = datetime.utcnow()

    # --- 更新結束資訊 ---
    row.end_lat = payload.lat
    row.end_lng = payload.lng
    row.ended_at = now
    row.status = CheckinStatus.ended

    # --- 再跑一次累積邏輯（避免使用者沒打最後一個 heartbeat）---
    last = row.last_tick_at or row.started_at
    delta_min = int((now - last).total_seconds() // 60)
    if delta_min > 0 and row.accum_minutes < MAX_ACCUM_MINUTES:
        gain = min(delta_min, MAX_ACCUM_MINUTES - row.accum_minutes)
        row.accum_minutes += gain
        row.last_tick_at = last + timedelta(minutes=gain)

    # 兼容舊的 dwell_minutes 欄位（純紀錄用）
    row.dwell_minutes = row.accum_minutes

    # --- 未達最低門檻：直接拒絕 ---
    if row.accum_minutes < REQUIRED_MINUTES:
        row.status = CheckinStatus.rejected
        row.reason = "DWELL_TOO_SHORT"
        db.commit()
        return CheckinEndOut(verified=False, dwell_minutes=row.accum_minutes, coins_awarded=0)

    # --- 每日發獎上限檢查 ---
    today = now.date()
    today_start = datetime(today.year, today.month, today.day)
    tomorrow_start = today_start + timedelta(days=1)

    awarded_today = db.query(Checkin).filter(
        Checkin.user_id == user_id,
        Checkin.status.in_([CheckinStatus.verified, CheckinStatus.awarded]),
        Checkin.started_at >= today_start,
        Checkin.started_at < tomorrow_start,
    ).count()

    if awarded_today >= MAX_DAILY_AWARDED_CHECKINS:
        # 今天已經獲得過獎勵了，這次就算過關但不再給幣
        row.status = CheckinStatus.verified
        row.reason = "DAILY_LIMIT_REACHED"
        db.commit()
        return CheckinEndOut(verified=True, dwell_minutes=row.accum_minutes, coins_awarded=0)

    # --- 計算獎勵金幣（以 5 分鐘為單位，最多 40 分）---
    effective_min = min(row.accum_minutes, MAX_ACCUM_MINUTES)
    units = effective_min // 5         # 幾個 5 分鐘
    coins = units * COINS_PER_5_MIN   # 依你設的常數調整

    row.status = CheckinStatus.verified
    db.commit()

    awarded = add_ledger_entry(
        db=db,
        user_id=user_id,
        delta=coins,
        source="checkin",
        ref_id=row.id,
        idempotency_key=f"checkin:{row.id}"
    )
    row.coins_awarded = awarded
    if awarded > 0:
        row.status = CheckinStatus.awarded
    db.commit()

    # ✅ 打卡給 EXP：只有真的有發幣時才給
    if awarded > 0:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            # 👉「基礎 EXP」公式：示範用金幣的一半，可依停留時間/習慣再調整
            base_exp = max(1, awarded // 2)

            weekly_count = get_weekly_activity_count(db, user_id)
            status = calc_chicken_status(weekly_count)      # "weak" / "normal" / "strong"
            multiplier = chicken_exp_multiplier(status)     # 0.5 / 1.0 / 1.5

            exp_gain = int(base_exp * multiplier)
            apply_exp_and_update(user, exp_gain)
            db.commit()
            
    return CheckinEndOut(verified=True, dwell_minutes=row.accum_minutes, coins_awarded=awarded)


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

def haversine_distance_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c