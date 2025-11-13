# path: app/schemas/economy.py
from pydantic import BaseModel, Field, condecimal
from typing import Optional, Literal
from datetime import datetime, date
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

# 👇 在這裡加一個 debug 用的輸入模型
class CheckinRewindStartIn(BaseModel):
    checkin_id: int
    # 往回調幾分鐘（上限先隨便抓個一天 1440 分鐘，避免亂炸）
    rewind_minutes: int = Field(..., ge=0, le=1440)
    
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


# ============================
# 訓練課表 / 紀錄
# ============================

class TrainingLogCreate(BaseModel):
    exercise_name: str = Field(..., max_length=64)
    weight_kg: condecimal(max_digits=5, decimal_places=2, gt=0)
    reps: int = Field(..., ge=1, le=1000)
    sets: int = Field(..., ge=1, le=100)
    performed_at: Optional[datetime] = None  # 不填就用後端現在時間

class TrainingLogRow(BaseModel):
    id: int
    exercise_name: str
    weight_kg: float
    reps: int
    sets: int
    volume: int
    performed_at: datetime

class TrainingStatsPoint(BaseModel):
    date: date
    total_volume: int
    total_sets: int

class TrainingStatsOut(BaseModel):
    range: Literal["week", "month"]
    points: list[TrainingStatsPoint]