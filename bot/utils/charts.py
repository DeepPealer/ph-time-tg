import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date, timedelta
from sqlalchemy import select, func
from bot.database.models import Report

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['font.sans-serif'] = ['Inter', 'DejaVu Sans'] # DejaVu Sans as fallback

async def generate_revenue_chart(session: "AsyncSession", days: int = 30) -> io.BytesIO:
    """Generate a chart showing daily revenue for the last X days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    stmt = (
        select(Report.date, func.sum(Report.revenue))
        .where(Report.date >= start_date)
        .group_by(Report.date)
        .order_by(Report.date)
    )
    res = await session.execute(stmt)
    data = res.all()
    
    if not data:
        return None
    
    dates = [d[0] for d in data]
    revenues = [d[1] for d in data]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(dates, revenues, marker='o', linestyle='-', color='#4e73df', linewidth=2, markersize=6)
    ax.fill_between(dates, revenues, color='#4e73df', alpha=0.1)
    
    ax.set_title(f'Выручка за последние {days} дней', fontsize=16, fontweight='bold', pad=20)
    ax.set_ylabel('₽', fontsize=12)
    
    # Format dates on X-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
    plt.xticks(rotation=45)
    
    # Grid and layout
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    buf.seek(0)
    plt.close(fig)
    
    return buf

async def generate_plan_performance_chart(session: "AsyncSession") -> io.BytesIO:
    """Generate a bar chart showing plan performance for each project."""
    from bot.database.models import Plan
    
    # Get active project plans (period=month)
    stmt_plans = select(Plan).where(Plan.is_active == True, Plan.period == 'month', Plan.project_name != None)
    res_plans = await session.execute(stmt_plans)
    plans = res_plans.scalars().all()
    
    if not plans:
        return None
    
    today = date.today()
    start_of_month = today.replace(day=1)
    
    labels = []
    performance = []
    
    for plan in plans:
        stmt_rev = select(func.sum(Report.revenue)).where(
            Report.project_name == plan.project_name,
            Report.date >= start_of_month
        )
        res_rev = await session.execute(stmt_rev)
        actual = res_rev.scalar() or 0
        
        pct = (actual / plan.plan_amount * 100) if plan.plan_amount else 0
        labels.append(plan.project_name)
        performance.append(pct)
        
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = ['#1cc88a' if p >= 100 else '#f6c23e' if p >= 70 else '#e74a3b' for p in performance]
    bars = ax.bar(labels, performance, color=colors)
    
    ax.axhline(100, color='red', linestyle='--', alpha=0.5, label='План (100%)')
    ax.set_title(f'Выполнение планов за {today.strftime("%B %Y")}', fontsize=16, fontweight='bold', pad=20)
    ax.set_ylabel('% выполнения', fontsize=12)
    ax.set_ylim(0, max(performance + [110]))
    
    # Add labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    buf.seek(0)
    plt.close(fig)
    
    return buf
