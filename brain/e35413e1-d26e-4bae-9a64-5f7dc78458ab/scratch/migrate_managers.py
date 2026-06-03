import asyncio
from sqlalchemy import select
from bot.database.db import SessionLocal
from bot.database.models import User, Project, UserRole

async def migrate():
    async with SessionLocal() as session:
        # Find all managers with a project assigned
        res = await session.execute(
            select(User).where(User.role == UserRole.manager, User.project_id != None)
        )
        managers = res.scalars().all()
        
        count = 0
        for m in managers:
            # Get the city from their current project
            pres = await session.execute(select(Project).where(Project.id == m.project_id))
            p = pres.scalar_one_or_none()
            if p:
                m.city = p.city
                m.project_id = None
                count += 1
        
        await session.commit()
        print(f"Successfully migrated {count} managers to city-wide management.")

if __name__ == "__main__":
    asyncio.run(migrate())
