import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import select, func
from bot.database.models import Report

# Set premium theme
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['font.sans-serif'] = ['Inter', 'DejaVu Sans']
plt.rcParams['axes.titlepad'] = 20
plt.rcParams['axes.labelpad'] = 10

async def generate_revenue_chart(session: "AsyncSession", days: int = 30) -> io.BytesIO:
    """Generate a premium-style chart showing daily revenue."""
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
    
    # Create DataFrame for Seaborn
    df = pd.DataFrame(data, columns=['date', 'revenue'])
    df['date'] = pd.to_datetime(df['date'])
    
    fig, ax = plt.subplots(figsize=(11, 6))
    
    # Line plot with shadows and markers
    sns.lineplot(data=df, x='date', y='revenue', ax=ax, 
                 marker='o', markersize=8, color='#4e73df', 
                 linewidth=3, label='Выручка')
    
    # Fill the area under the line
    ax.fill_between(df['date'], df['revenue'], color='#4e73df', alpha=0.15)
    
    ax.set_title(f'Динамика выручки за {days} дней', fontsize=18, fontweight='bold')
    ax.set_ylabel('Выручка (₽)', fontsize=12)
    ax.set_xlabel(None)
    
    # Format dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45, ha='right')
    
    # Remove top and right spines for a modern look
    sns.despine(offset=10, trim=True)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=140)
    buf.seek(0)
    plt.close(fig)
    
    return buf

async def generate_plan_performance_chart(session: "AsyncSession") -> io.BytesIO:
    """Generate a clean bar chart showing plan performance."""
    from bot.database.models import Plan
    
    stmt_plans = select(Plan).where(Plan.is_active == True, Plan.period == 'month', Plan.project_name != None)
    res_plans = await session.execute(stmt_plans)
    plans = res_plans.scalars().all()
    
    if not plans:
        return None
    
    today = date.today()
    start_of_month = today.replace(day=1)
    
    data_list = []
    for plan in plans:
        stmt_rev = select(func.sum(Report.revenue)).where(
            Report.project_name == plan.project_name,
            Report.date >= start_of_month
        )
        res_rev = await session.execute(stmt_rev)
        actual = res_rev.scalar() or 0
        pct = (actual / plan.plan_amount * 100) if plan.plan_amount else 0
        data_list.append({'Проект': plan.project_name, 'Выполнение': pct})
        
    df = pd.DataFrame(data_list)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Dynamic coloring based on performance
    colors = ['#1cc88a' if p >= 100 else '#f6c23e' if p >= 70 else '#e74a3b' for p in df['Выполнение']]
    
    bars = sns.barplot(data=df, x='Проект', y='Выполнение', palette=colors, ax=ax, hue='Проект', legend=False)
    
    ax.axhline(100, color='#e74a3b', linestyle='--', alpha=0.6, label='Цель (100%)', linewidth=2)
    ax.set_title(f'Выполнение планов: {today.strftime("%B %Y")}', fontsize=18, fontweight='bold')
    ax.set_ylabel('% выполнения', fontsize=12)
    ax.set_ylim(0, max(df['Выполнение'].max() + 15, 115))
    
    # Text labels on bars
    for i, p in enumerate(df['Выполнение']):
        ax.text(i, p + 2, f'{p:.1f}%', ha='center', fontweight='bold', size=11)
        
    sns.despine()
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=140)
    buf.seek(0)
    plt.close(fig)
    
    return buf

async def generate_yearly_revenue_chart(session: "AsyncSession") -> io.BytesIO:
    """Generate a monthly revenue breakdown chart for the current year."""
    today = date.today()
    start_year = today.replace(month=1, day=1)
    
    stmt = (
        select(
            func.extract('month', Report.date).label('month'),
            func.sum(Report.revenue).label('revenue')
        )
        .where(Report.date >= start_year)
        .group_by(func.extract('month', Report.date))
        .order_by('month')
    )
    res = await session.execute(stmt)
    data = res.all()
    
    if not data:
        return None
    
    month_names = {
        1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
        7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек'
    }
    
    df = pd.DataFrame(data, columns=['month', 'revenue'])
    df['month_name'] = df['month'].map(month_names)
    
    fig, ax = plt.subplots(figsize=(11, 6))
    
    # Use a gradient-like palette
    sns.barplot(data=df, x='month_name', y='revenue', palette="viridis", ax=ax, hue='month_name', legend=False)
    
    ax.set_title(f'Годовая выручка: {today.year}', fontsize=18, fontweight='bold')
    ax.set_ylabel('Сумма (₽)', fontsize=12)
    ax.set_xlabel(None)
    
    # Label formatting
    for i, v in enumerate(df['revenue']):
        ax.text(i, v + (df['revenue'].max() * 0.02), f'{v:,.0f}', ha='center', fontweight='bold')
        
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    sns.despine()
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=140)
    buf.seek(0)
    plt.close(fig)
    
    return buf
