
import asyncio
from sqlalchemy import select, func
from bot.database.db import SessionLocal
from bot.database.models import Report, Plan, ManagementExpense
from datetime import date

async def check():
    async with SessionLocal() as session:
        r_count = await session.execute(select(func.count(Report.id)).where(Report.date >= date(2026, 1, 1), Report.date <= date(2026, 1, 31)))
        p_count = await session.execute(select(func.count(Plan.id)))
        m_count = await session.execute(select(func.count(ManagementExpense.id)))
        
        print(f"Reports in Jan 2026: {r_count.scalar()}")
        print(f"Total Plans: {p_count.scalar()}")
        print(f"Total Management Expenses: {m_count.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
