# app/main.py
from fastapi import FastAPI
from app.routers import auth_guest
from app.core.db import engine, Base
from app.routers import auth_refresh          # ← 新增


app = FastAPI()
app.include_router(auth_guest.router)
app.include_router(auth_refresh.router)        # ← 新增

@app.get("/health")
def health():
    return {"status": "ok"}

# 啟動時自動建立 ORM 對應資料表（與你 Workbench 結構相容時就會略過）
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
