import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from bot.database.db import SessionLocal, init_db
from bot.database.models import City, SalaryRule
from bot.utils.salary import calculate_photographer_salary

async def test_salary_calculation():
    print("🚀 Starting dynamic salary calculation test...")
    
    # Ensure DB is initialized and seeded
    await init_db()
    
    async with SessionLocal() as session:
        # 1. Test Minsk (all_days rule)
        res = await session.execute(select(City).where(City.slug == "minsk"))
        minsk = res.scalar_one_or_none()
        if not minsk:
            print("❌ Minsk not found in DB")
            return

        rules_res = await session.execute(select(SalaryRule).where(SalaryRule.city_id == minsk.id))
        minsk_rules = rules_res.scalars().all()
        
        # Test Minsk full day, revenue 400 (should be base 45 + 10% = 85)
        # 400 is in [0, 450) -> base 45, 10%
        salary, desc = calculate_photographer_salary(400.0, 1, "minsk", 0, minsk_rules, "full")
        print(f"Minsk (Mon, 400р): {salary} BYN | {desc}")
        assert salary == 85.0
        
        # Test Minsk full day, revenue 500 (should be base 0 + 20% = 100)
        # 500 is in [450, 1000) -> base 0, 20%
        salary, desc = calculate_photographer_salary(500.0, 1, "minsk", 2, minsk_rules, "full")
        print(f"Minsk (Wed, 500р): {salary} BYN | {desc}")
        assert salary == 100.0

        # 2. Test Gomel (different by day)
        res = await session.execute(select(City).where(City.slug == "gomel"))
        gomel = res.scalar_one_or_none()
        
        rules_res = await session.execute(select(SalaryRule).where(SalaryRule.city_id == gomel.id))
        gomel_rules = rules_res.scalars().all()
        
        # Gomel Weekday (Mon=0), revenue 100 -> base 25 + 10% = 35
        salary, desc = calculate_photographer_salary(100.0, 1, "gomel", 0, gomel_rules, "full")
        print(f"Gomel (Mon, 100р): {salary} BYN | {desc}")
        assert salary == 35.0
        
        # Gomel Saturday (Sat=5), revenue 100 -> base 25 + 10% = 35 (threshold is 400)
        salary, desc = calculate_photographer_salary(100.0, 1, "gomel", 5, gomel_rules, "full")
        print(f"Gomel (Sat, 100р): {salary} BYN | {desc}")
        assert salary == 35.0
        
        # Gomel Sunday (Sun=6), revenue 500 -> base 0 + 20% = 100 (threshold 350-600)
        salary, desc = calculate_photographer_salary(500.0, 1, "gomel", 6, gomel_rules, "full")
        print(f"Gomel (Sun, 500р): {salary} BYN | {desc}")
        assert salary == 100.0

        # 3. Test Half-shift (even if deactivated in UI, logic should work)
        # Minsk Half, revenue 400 -> base 22.5 + 10% = 62.5
        salary, desc = calculate_photographer_salary(400.0, 1, "minsk", 0, minsk_rules, "half")
        print(f"Minsk Half (Mon, 400р): {salary} BYN | {desc}")
        assert salary == 62.5

    print("✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_salary_calculation())
