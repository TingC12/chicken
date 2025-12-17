# path: app/routers/auth_refresh.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from starlette import status
from app.core.db import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User  # ✅ 新增

from app.core.security import create_access_token, hash_refresh_token

router = APIRouter(tags=["auth"])

class RefreshIn(BaseModel):
    refresh_token: str

class RefreshOut(BaseModel):
    access_token: str
    expires_in: int

@router.post("/refresh", response_model=RefreshOut)
def refresh_token(payload: RefreshIn, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token_hash = hash_refresh_token(payload.refresh_token)

    row = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not row or row.revoked_at or row.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # 簽新 AT
    at, expires_in, _ = create_access_token(user_id=row.user_id, is_guest=True)
    return RefreshOut(access_token=at, expires_in=expires_in)
