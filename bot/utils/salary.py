"""
Salary calculation rules (hardcoded per business rules).

Photographer Gomel:
  Mon-Fri:  <=200 → 25 + 10%; 200-300 → 20%; >300 → 22%
  Saturday: <=400 → 25 + 10%; 400-800 → 20%; >800 → 22%
  Sunday:   <=350 → 25 + 10%; 350-600 → 20%; >600 → 22%

Photographer Minsk (all days):
  <=450 → 45 + 10%; 450-1000 → 20%; >1000 → 22%

Percentage part is divided equally among shift_count.

Manager: % of monthly revenue vs plan.
  <60%    → 1% of turnover
  60-80%  → 2%
  80-110% → 3%
  >110%   → 4%
"""

from __future__ import annotations

CITY_GOMEL = "gomel"
CITY_MINSK = "minsk"

# (threshold_min, threshold_max_exclusive, base, percentage)
# threshold_max_exclusive=None means unlimited
_GOMEL_WEEKDAY = [  # Mon-Fri (weekday 0-4)
    (0,   200,  25.0, 0.10),
    (200, 300,   0.0, 0.20),
    (300, None,  0.0, 0.22),
]
_GOMEL_SATURDAY = [  # weekday 5
    (0,   400,  25.0, 0.10),
    (400, 800,   0.0, 0.20),
    (800, None,  0.0, 0.22),
]
_GOMEL_SUNDAY = [  # weekday 6
    (0,   350,  25.0, 0.10),
    (350, 600,   0.0, 0.20),
    (600, None,  0.0, 0.22),
]
_MINSK_ALL = [  # all days
    (0,    450,  45.0, 0.10),
    (450, 1000,   0.0, 0.20),
    (1000, None,  0.0, 0.22),
]

_MANAGER_TIERS = [
    (0,   60,  0.01),  # <60%  → 1%
    (60,  80,  0.02),  # 60-80% → 2%
    (80,  110, 0.03),  # 80-110% → 3%
    (110, None, 0.04), # >110% → 4%
]

CITY_LABELS = {
    CITY_GOMEL: "Гомель",
    CITY_MINSK: "Минск",
}


def _get_rules(city: str, weekday: int) -> list[tuple]:
    """Select the correct tier table based on city and weekday (0=Mon, 6=Sun)."""
    if city == CITY_MINSK:
        return _MINSK_ALL
    # Gomel
    if weekday == 5:
        return _GOMEL_SATURDAY
    if weekday == 6:
        return _GOMEL_SUNDAY
    return _GOMEL_WEEKDAY


def _apply_tiers(revenue: float, tiers: list[tuple]) -> tuple[float, float, float]:
    """Returns (base, pct_rate, tier_min) for the matching tier."""
    for tmin, tmax, base, pct in tiers:
        if revenue >= tmin and (tmax is None or revenue < tmax):
            return base, pct, tmin
    # fallback: last tier
    tmin, _, base, pct = tiers[-1]
    return base, pct, tmin


def calculate_photographer_salary(
    revenue: float, shift_count: int, city: str, weekday: int
) -> tuple[float, str]:
    """
    Returns (salary_per_person, description_string).
    Description suitable for display in Telegram.
    """
    city = city.lower()
    rules = _get_rules(city, weekday)
    base, pct, _ = _apply_tiers(revenue, rules)
    pct_total = revenue * pct
    pct_per_person = pct_total / max(shift_count, 1)
    salary = round(base + pct_per_person, 2)

    city_label = CITY_LABELS.get(city, city)
    day_label = _day_type_label(city, weekday)
    shared_note = f" (на {shift_count} чел.)" if shift_count > 1 else ""

    if base > 0:
        desc = f"{city_label}/{day_label}: {base:.0f}+{pct*100:.0f}%{shared_note}"
    else:
        desc = f"{city_label}/{day_label}: {pct*100:.0f}%{shared_note}"

    return salary, desc


def _day_type_label(city: str, weekday: int) -> str:
    if city == CITY_MINSK:
        return "Пн–Вс"
    if weekday == 5:
        return "Сб"
    if weekday == 6:
        return "Вс"
    return "Пн–Пт"


def calculate_manager_salary(turnover: float, plan: float) -> tuple[float, str]:
    """
    Returns (salary, description).
    plan=0 means no plan set.
    """
    if not plan:
        return 0.0, "План не установлен"
    pct_done = (turnover / plan * 100) if plan else 0

    for tmin, tmax, rate in _MANAGER_TIERS:
        if pct_done >= tmin and (tmax is None or pct_done < tmax):
            salary = round(turnover * rate, 2)
            desc = (
                f"Выполнение {pct_done:.1f}% → ставка {rate*100:.0f}% от оборота"
            )
            return salary, desc

    # edge: 100%+ last
    rate = _MANAGER_TIERS[-1][2]
    return round(turnover * rate, 2), f"Выполнение {pct_done:.1f}% → {rate*100:.0f}%"


# ─── Legacy compat (still used by admin.py for display, will be cleaned up) ───

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def get_salary_levels(session: AsyncSession) -> list:
    """Returns empty list — kept for backward compat during migration."""
    return []


def salary_level_description(level) -> str:
    return ""
