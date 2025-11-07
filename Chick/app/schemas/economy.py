# path: app/schemas/economy.py
from pydantic import BaseModel, Field, condecimal
from typing import Optional, Literal
from datetime import datetime
from app.models.economy import CheckinStatus, RunStatus

# /me
class MeSummary(BaseModel):
    user_id: int
    status: Literal["guest","user","admin"] = "guest"
    coins: int
    today_checkin_status: Literal["none","started","verified","awarded"]
    last_login_at: Optional[datetime] = None

# 打卡
class CheckinStartIn(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)

class CheckinStartOut(BaseModel):
    checkin_id: int
    status: CheckinStatus
    started_at: datetime

class CheckinHeartbeatIn(BaseModel):
    checkin_id: int

class CheckinEndIn(BaseModel):
    checkin_id: int
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)

class CheckinEndOut(BaseModel):
    verified: bool
    dwell_minutes: int
    coins_awarded: int

class CheckinRow(BaseModel):
    id: int
    status: CheckinStatus
    dwell_minutes: Optional[int]
    coins_awarded: int
    reason: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]

# 跑步
class RunSummaryIn(BaseModel):
    distance_km: condecimal(gt=0, max_digits=6, decimal_places=3)
    duration_sec: int = Field(..., gt=0)
    max_speed_kmh: condecimal(gt=0, max_digits=5, decimal_places=2)

class RunSummaryOut(BaseModel):
    coins_awarded: int
    status: RunStatus

class RunRow(BaseModel):
    id: int
    distance_km: float
    duration_sec: int
    max_speed_kmh: float
    coins_awarded: int
    status: RunStatus
    reason: Optional[str]
    created_at: datetime
