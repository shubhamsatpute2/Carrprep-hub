# create_tables.py
import asyncio
from database import Base, engine
from models import User, Resume, UserProgress

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init_models())
