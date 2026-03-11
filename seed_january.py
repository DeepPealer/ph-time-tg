import asyncio
import random
import os
import sys

# Add current dir to path for imports to work
sys.path.append(os.getcwd())

from datetime import date, timedelta
from sqlalchemy import select, delete, func
from bot.database.db import SessionLocal
from bot.database.models import User, UserRole, Report, Plan, ManagementExpense, SalarySetting
from bot.utils.salary import calculate_photographer_salary

async def seed():
    async with SessionLocal() as session:
        print("🌱 Seeding data for January 2026...")
        
        # 1. Test Users
        photographers = [
            ("Алексей Фотографов", "minsk"),
            ("Виктория Снимаева", "minsk"),
            ("Дмитрий Вспышкин", "gomel"),
            ("Елена Затворова", "gomel"),
            ("Иван Объективов", "gomel")
        ]
        
        year, month = 2026, 1
        start_date = date(year, month, 1)
        end_date = date(year, month, 31)

        print("🧹 Cleaning old January data...")
        await session.execute(delete(Plan).where(Plan.period == 'month'))
        await session.execute(delete(Report).where(Report.date >= start_date, Report.date <= end_date))
        await session.execute(delete(ManagementExpense).where(ManagementExpense.date >= start_date, ManagementExpense.date <= end_date))
        
        db_photogs = []
        for name, city in photographers:
            res = await session.execute(select(User).where(User.full_name == name))
            up = res.scalar_one_or_none()
            if not up:
                up = User(
                    telegram_id=random.randint(1000000, 9999999), 
                    full_name=name, 
                    city=city, 
                    role=UserRole.employee, 
                    is_active=True
                )
                session.add(up)
            db_photogs.append(up)
        
        await session.flush()
        print(f"✅ Users ready: {len(db_photogs)}")

        # 2. Setup Plans
        projects = {
            "minsk": ["Green City", "Dana Mall"],
            "gomel": ["Цирк", "Бассейн"]
        }
        
        for city, projs in projects.items():
            for p_name in projs:
                plan = Plan(
                    city=city, 
                    project_name=p_name, 
                    plan_amount=random.choice([250000, 300000, 350000]),
                    period="month", 
                    is_active=True
                )
                session.add(plan)
        print("✅ Plans ready")
        
        # 3. Reports
        print("Generating reports...")
        report_count = 0
        for d in range(1, 32):
            curr_date = date(year, month, d)
            for city, projs in projects.items():
                for p_name in projs:
                    is_shared = random.random() < 0.2
                    count = 2 if is_shared else 1
                    
                    base_rev = random.randint(500, 1500)
                    revenue = round(base_rev, -1)
                    
                    cash = revenue * random.uniform(0.3, 0.5)
                    acq = revenue - cash
                    exp = random.randint(5, 50)
                    visitors = random.randint(50, 200)
                    bdays = 0 if random.random() > 0.3 else random.randint(1, 3)
                    
                    city_photogs = [p for p in db_photogs if p.city == city]
                    p_list = random.sample(city_photogs, count)
                    
                    for p in p_list:
                        # Correct: pass curr_date.weekday() (0=Mon, 6=Sun)
                        sal, _ = calculate_photographer_salary(revenue, count, city, curr_date.weekday())
                        
                        rep = Report(
                            date=curr_date,
                            user_id=p.id,
                            employee_name=p.full_name,
                            city=city,
                            project_name=p_name,
                            shift_count=count,
                            revenue=float(revenue),
                            cash=round(float(cash), 2),
                            acquiring=round(float(acq), 2),
                            expense=float(exp),
                            salary_paid=float(sal),
                            salary_level=1, # Fixed level as in bot/handlers/report.py:366
                            trainee_salary=0.0,
                            cash_balance=round(float(cash - exp), 2),
                            visitors=visitors,
                            birthdays=bdays,
                            comment="Тест",
                            is_paid=False
                        )
                        session.add(rep)
                        report_count += 1

        print(f"✅ Reports generated: {report_count}")

        # 4. Management Expenses
        print("Generating management expenses...")
        for city, projs in projects.items():
            for p_name in projs:
                session.add(ManagementExpense(
                    date=date(year, month, 1),
                    city=city,
                    project_name=p_name,
                    category="аренда",
                    amount=float(random.choice([2500, 3500, 4500])),
                    comment="Аренда за январь"
                ))
            
            session.add(ManagementExpense(
                date=date(year, month, 10),
                city=city,
                project_name=None,
                category="техника",
                amount=1200.0,
                comment="Обслуживание оборудования"
            ))
            session.add(ManagementExpense(
                date=date(year, month, 20),
                city=city,
                project_name=None,
                category="расходник",
                amount=850.0,
                comment="Расходники"
            ))

        print("Finalizing transaction...")
        try:
            await session.commit()
            print("✨ DONE! January 2026 data seeded successfully.")
        except Exception as e:
            print(f"❌ ERROR DURING COMMIT: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(seed())
