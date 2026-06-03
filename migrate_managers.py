import asyncio
import sys
import os

# Add current directory to path so we can import bot
sys.path.append(os.getcwd())

from bot.database.db import SessionLocal, engine
from bot.database.models import User, UserRole, Project
from sqlalchemy import select

async def migrate_managers():
    print("🚀 Starting manager migration...")
    async with SessionLocal() as session:
        # Find all managers
        res = await session.execute(
            select(User).where(User.role == UserRole.manager)
        )
        managers = res.scalars().all()
        
        count = 0
        for mgr in managers:
            if mgr.project_id:
                # Get the project to find its city
                pres = await session.execute(
                    select(Project).where(Project.id == mgr.project_id)
                )
                proj = pres.scalar_one_or_none()
                
                if proj:
                    print(f"🔄 Migrating {mgr.pretty_name} (ID: {mgr.telegram_id}): {proj.name} ({proj.city}) -> City-wide")
                    mgr.city = proj.city
                    mgr.project_id = None
                    count += 1
                else:
                    print(f"⚠️ Manager {mgr.pretty_name} has invalid project_id {mgr.project_id}. Clearing it.")
                    mgr.project_id = None
            elif not mgr.city:
                print(f"⚠️ Manager {mgr.pretty_name} has no project and no city. Please set city manually.")
            else:
                print(f"✅ Manager {mgr.pretty_name} is already city-wide ({mgr.city}).")

        await session.commit()
        print(f"🎉 Migration complete. Updated {count} managers.")

if __name__ == "__main__":
    asyncio.run(migrate_managers())
