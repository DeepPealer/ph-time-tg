from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import SalarySetting


async def get_salary_levels(session: AsyncSession) -> list[SalarySetting]:
    result = await session.execute(select(SalarySetting).order_by(SalarySetting.level))
    return list(result.scalars().all())


def calculate_salary(revenue: float, shift_count: int, levels: list[SalarySetting]) -> tuple[float, int]:
    """
    Returns (salary_per_person, level_number).
    Progressive scale: finds matching level by revenue, then divides by shift count.
    """
    matched = None
    for lvl in sorted(levels, key=lambda x: x.level):
        if revenue >= lvl.threshold_min:
            if lvl.threshold_max is None or revenue < lvl.threshold_max:
                matched = lvl
                break

    if not matched:
        matched = sorted(levels, key=lambda x: x.level)[-1]

    total = matched.base_salary + revenue * matched.percentage
    per_person = round(total / max(shift_count, 1), 2)
    return per_person, matched.level


def salary_level_description(level: SalarySetting) -> str:
    base = f"Оклад {level.base_salary:.0f}₽ + " if level.base_salary > 0 else ""
    max_str = f"до {level.threshold_max:.0f}₽" if level.threshold_max else "и выше"
    return (
        f"Ур.{level.level}: выручка {level.threshold_min:.0f}₽ {max_str} → "
        f"{base}{level.percentage * 100:.0f}% с выручки"
    )
