import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from bot.config import config

# Create engine
engine = create_async_engine(config.database_url, echo=False)

# Standard session factory (SessionLocal)
# Using the sessionmaker + AsyncSession class pattern for maximum compatibility
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db() -> None:
    """Initialize the database: create tables and seed data."""
    from bot.database.models import Base, SalarySetting
    from sqlalchemy import select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Handle migrations without Alembic: ensure project_name column exists
        from sqlalchemy import text
        await conn.execute(text("ALTER TABLE management_expenses ADD COLUMN IF NOT EXISTS project_name VARCHAR(200);"))

    async with SessionLocal() as session:
        result = await session.execute(select(SalarySetting))
        if not result.scalars().first():
            defaults = [
                SalarySetting(level=1, threshold_min=0,     threshold_max=15000,  base_salary=2500, percentage=0.10),
                SalarySetting(level=2, threshold_min=15000,  threshold_max=30000,  base_salary=0,    percentage=0.20),
                SalarySetting(level=3, threshold_min=30000,  threshold_max=None,   base_salary=0,    percentage=0.22),
            ]
            session.add_all(defaults)
            await session.commit()
