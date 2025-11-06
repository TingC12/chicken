# app/core/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

class Base(DeclarativeBase):
    pass

# 使用 asyncmy 作為 MySQL 非同步驅動
engine = create_async_engine(
    settings.DATABASE_URL,  # 例如 mysql+asyncmy://user:pass@localhost:3306/chicken_db
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# 讓 router 以 Dependency 取到 session 用
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
