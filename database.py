from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from fastapi import Depends

# Create Base first before models
Base = declarative_base()

# SQLite database URL
DATABASE_URL = "sqlite+aiosqlite:///./careerprep.db"

engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    future=True, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

async def get_db():
    async with SessionLocal() as session:
        yield session