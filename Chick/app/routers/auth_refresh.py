# app/routers/auth_refresh.py
from __future__ import annotations
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    utcnow,
)
from app.repos.tokens_repo import find_rt_by_hash, add_refresh_token, revoke_rt_by_id
from app.schemas.auth_schema import RefreshRequest, RefreshResponse, ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- 超簡易限流（每 RT 每分鐘 6 次）----
RL_BUCKET: dict[str, tuple[int, float]] = {}
WINDOW_SEC = 60
MAX_REQ = 6

def rl_check(rt_hash: str):
    now = time.time()
    cnt, start = RL_BUCKET.get(rt_hash, (0, now))
    if now - start > WINDOW_SEC:
        RL_BUCKET[rt_hash] = (1, now)
        return
    cnt += 1
    RL_BUCKET[rt_hash] = (cnt, start)
    if cnt > MAX_REQ:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ErrorResponse(
                error_code="RATE_LIMITED",
                message="Too many refresh attempts.",
                retry_after_seconds=int(WINDOW_SEC - (now - start)),
            ).model_dump()
        )

def to_utc_naive(dt: datetime) -> datetime:
    """任何時間都轉成 UTC 並移除 tzinfo（MySQL DATETIME 友善）。"""
    if dt.tzinfo is None:
        # 視為 UTC-naive
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def to_utc_timestamp(dt: datetime) -> float:
    """把任何 datetime 轉成 UTC 的 epoch 秒數，用來比較大小。"""
    if dt.tzinfo is None:
        # 視為 UTC
        return dt.replace(tzinfo=timezone.utc).timestamp()
    return dt.astimezone(timezone.utc).timestamp()

@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def refresh_token(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    用 Refresh Token 明文換新 Access Token（並旋轉新的 RT）：
    1) 雜湊 RT、限流
    2) 取 DB 紀錄並檢查：存在 / 未撤銷 / 未過期
    3) 撤銷舊 RT
    4) 發新 AT + 新 RT（存雜湊）
    """
    if not body.refresh_token or len(body.refresh_token) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(error_code="INVALID_TOKEN", message="refresh_token missing or too short").model_dump(),
        )

    rt_hash = hash_refresh_token(body.refresh_token)
    rl_check(rt_hash)

    rt_row = await find_rt_by_hash(db, rt_hash)
    if not rt_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error_code="INVALID_TOKEN", message="Refresh token not found").model_dump(),
        )
    if rt_row.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error_code="TOKEN_REVOKED", message="Refresh token has been revoked").model_dump(),
        )

    # ---- 時間比較改用 timestamp，避免 naive/aware 衝突
    now = utcnow()
    now_ts = to_utc_timestamp(now)
    exp_ts = to_utc_timestamp(rt_row.expires_at)
    if now_ts >= exp_ts:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error_code="TOKEN_EXPIRED", message="Refresh token expired").model_dump(),
        )

    user_id = rt_row.user_id

    # 3) 撤銷舊 RT：寫入 UTC-naive（MySQL DATETIME 友善）
    await revoke_rt_by_id(db, rt_row.id, revoked_at=to_utc_naive(now))

    # 4) 新 AT & 新 RT
    at_token, at_expires_in, _ = create_access_token(user_id=user_id, is_guest=True)
    new_rt_plain = generate_refresh_token()
    new_rt_hash = hash_refresh_token(new_rt_plain)
    new_rt_expires_at, new_rt_expires_in = refresh_token_expiry()

    await add_refresh_token(
        db,
        user_id=user_id,
        token_hash=new_rt_hash,
        expires_at=to_utc_naive(new_rt_expires_at),  # 存 UTC-naive
        created_ip=(request.client.host if request.client else None),
        created_user_agent=request.headers.get("user-agent", "")[:255],
    )

    await db.commit()

    return RefreshResponse(
        access_token=at_token,
        access_token_expires_in=at_expires_in,
        refresh_token=new_rt_plain,
        refresh_token_expires_in=new_rt_expires_in,
    )
