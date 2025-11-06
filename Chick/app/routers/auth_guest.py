# app/routers/auth_guest.py
from __future__ import annotations
from datetime import datetime
import secrets
import time
from typing import Dict, Tuple

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
from app.repos.users_repo import (
    get_user_by_device_id,
    create_guest_user,
    touch_last_login,
)
from app.repos.tokens_repo import add_refresh_token
from app.schemas.auth_schema import (
    GuestLoginRequest,
    GuestLoginResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- 超簡易「記憶體」限流（之後可換成 Redis） ----
RATE_BUCKET: Dict[str, Tuple[int, float]] = {}
# key -> (count_in_window, window_start_ts)
WINDOW_SEC = 60
MAX_REQ_PER_WINDOW = 10

def rate_limit_key(ip: str, device_id: str | None) -> str:
    return f"{ip}:{device_id or '-'}"

def check_rate_limit(ip: str, device_id: str | None):
    now = time.time()
    key = rate_limit_key(ip, device_id)
    cnt, start = RATE_BUCKET.get(key, (0, now))
    if now - start > WINDOW_SEC:
        # reset window
        RATE_BUCKET[key] = (1, now)
        return
    # same window
    cnt += 1
    RATE_BUCKET[key] = (cnt, start)
    if cnt > MAX_REQ_PER_WINDOW:
        retry_after = int(WINDOW_SEC - (now - start))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ErrorResponse(
                error_code="RATE_LIMITED",
                message="Too many requests.",
                retry_after_seconds=retry_after,
            ).model_dump(),
        )

# ---- 正式：POST /auth/guest ----
@router.post(
    "/guest",
    response_model=GuestLoginResponse,
    responses={429: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def guest_login(
    body: GuestLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    遊客登入流程：
    1) 限流（IP+device_id）
    2) 找/建 user（status=guest；必要時生成 device_id）
    3) 簽發 AT；產生 RT（只回明文一次），雜湊寫入 DB
    4) 交易提交；回傳標準回應
    """
    # 1) 限流
    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("user-agent", "")[:255]
    check_rate_limit(client_ip, body.device_id)

    # 2) 找/建 guest 使用者
    device_id = body.device_id.strip() if body.device_id else None
    user = None
    if device_id:
        user = await get_user_by_device_id(db, device_id)

    if user is None:
        # 若前端沒提供 device_id，後端生成一個回傳，並綁在使用者上
        if not device_id:
            device_id = secrets.token_urlsafe(24)  # ~32字元的 URL-safe ID
        user = await create_guest_user(db, device_id=device_id)

    await touch_last_login(db, user.id)

    # 3) 產生 AT / RT
    at_token, at_expires_in, _ = create_access_token(
        user_id=user.id,
        is_guest=True,
    )

    rt_plain = generate_refresh_token()
    rt_hash = hash_refresh_token(rt_plain)
    rt_expires_at, rt_expires_in = refresh_token_expiry()

    # 4) 寫入 refresh_tokens（只存雜湊）
    await add_refresh_token(
        db,
        user_id=user.id,
        token_hash=rt_hash,
        expires_at=rt_expires_at,
        created_ip=client_ip,
        created_user_agent=user_agent,
    )

    # 單一交易提交
    await db.commit()

    return GuestLoginResponse(
        user_id=user.id,
        access_token=at_token,
        access_token_expires_in=at_expires_in,
        refresh_token=rt_plain,  # 明文只在這裡回一次
        refresh_token_expires_in=rt_expires_in,
        is_guest=True,
        device_id=device_id,
    )


# （保留 GET 版本讓你快速手測）
@router.get("/guest")
async def guest_get_placeholder():
    return {"ok": True, "endpoint": "/auth/guest", "method": "GET"}
