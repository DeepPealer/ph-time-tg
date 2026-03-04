import asyncio
from bot.database.main import session_factory
from bot.utils.excel import generate_monthly_calendar

async def test():
    async with session_factory() as session:
        print("Starting report generation...")
        try:
            # Test for March 2026, city gomel (as in user report)
            data = await generate_monthly_calendar(session, 2026, 3, city="gomel")
            print(f"Success! Generated {len(data)} bytes")
            with open("test_report.xlsx", "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
