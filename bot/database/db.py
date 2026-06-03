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
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(200);"))
        await conn.execute(text("""DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'manager' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')) THEN ALTER TYPE userrole ADD VALUE 'manager'; END IF; END $$;"""))
        await conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS is_reviewed BOOLEAN DEFAULT FALSE;"))
        await conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS reviewed_by_id INTEGER REFERENCES users(id);"))
        await conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id);"))
        await conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS shift_type VARCHAR(20) DEFAULT 'full';"))
        await conn.execute(text("ALTER TABLE plans ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id);"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id);"))

    async with SessionLocal() as session:
        # Seed dynamic cities and rules
        from bot.database.models import City, SalaryRule
        city_check = await session.execute(select(City))
        if not city_check.scalars().first():
            gomel = City(
                slug="gomel",
                name="Гомель",
                emoji="🏙️",
                thread_id=config.city_thread_gomel,
                is_active=True
            )
            minsk = City(
                slug="minsk",
                name="Минск",
                emoji="🌆",
                thread_id=config.city_thread_minsk,
                is_active=True
            )
            session.add_all([gomel, minsk])
            await session.flush()  # to populate IDs
            
            gomel_rules = [
                # Weekday
                SalaryRule(city_id=gomel.id, day_type="weekday", shift_type="full", threshold_min=0.0, threshold_max=200.0, base_salary=25.0, percentage=0.10),
                SalaryRule(city_id=gomel.id, day_type="weekday", shift_type="full", threshold_min=200.0, threshold_max=300.0, base_salary=0.0, percentage=0.20),
                SalaryRule(city_id=gomel.id, day_type="weekday", shift_type="full", threshold_min=300.0, threshold_max=None, base_salary=0.0, percentage=0.22),
                # Saturday
                SalaryRule(city_id=gomel.id, day_type="saturday", shift_type="full", threshold_min=0.0, threshold_max=400.0, base_salary=25.0, percentage=0.10),
                SalaryRule(city_id=gomel.id, day_type="saturday", shift_type="full", threshold_min=400.0, threshold_max=800.0, base_salary=0.0, percentage=0.20),
                SalaryRule(city_id=gomel.id, day_type="saturday", shift_type="full", threshold_min=800.0, threshold_max=None, base_salary=0.0, percentage=0.22),
                # Sunday
                SalaryRule(city_id=gomel.id, day_type="sunday", shift_type="full", threshold_min=0.0, threshold_max=350.0, base_salary=25.0, percentage=0.10),
                SalaryRule(city_id=gomel.id, day_type="sunday", shift_type="full", threshold_min=350.0, threshold_max=600.0, base_salary=0.0, percentage=0.20),
                SalaryRule(city_id=gomel.id, day_type="sunday", shift_type="full", threshold_min=600.0, threshold_max=None, base_salary=0.0, percentage=0.22),
            ]
            
            minsk_rules = [
                # Full day
                SalaryRule(city_id=minsk.id, day_type="all_days", shift_type="full", threshold_min=0.0, threshold_max=450.0, base_salary=45.0, percentage=0.10),
                SalaryRule(city_id=minsk.id, day_type="all_days", shift_type="full", threshold_min=450.0, threshold_max=1000.0, base_salary=0.0, percentage=0.20),
                SalaryRule(city_id=minsk.id, day_type="all_days", shift_type="full", threshold_min=1000.0, threshold_max=None, base_salary=0.0, percentage=0.22),
            ]
            
            session.add_all(gomel_rules + minsk_rules)

        result = await session.execute(select(SalarySetting))
        if not result.scalars().first():
            defaults = [
                SalarySetting(level=1, threshold_min=0,     threshold_max=15000,  base_salary=2500, percentage=0.10),
                SalarySetting(level=2, threshold_min=15000,  threshold_max=30000,  base_salary=0,    percentage=0.20),
                SalarySetting(level=3, threshold_min=30000,  threshold_max=None,   base_salary=0,    percentage=0.22),
            ]
            session.add_all(defaults)
        await session.commit()

        # Update CITY_LABELS dynamically
        from bot.utils.salary import CITY_LABELS
        res_c = await session.execute(select(City))
        for c in res_c.scalars().all():
            CITY_LABELS[c.slug] = c.name

