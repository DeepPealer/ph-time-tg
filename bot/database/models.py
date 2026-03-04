from datetime import date as py_date, datetime
from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    Text, Enum, ForeignKey, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, PyEnum):
    pending = "pending"
    employee = "employee"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.pending)
    city: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'gomel' | 'minsk' | None
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="user")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    date: Mapped[py_date] = mapped_column(Date)
    project_name: Mapped[str] = mapped_column(String(200))
    employee_name: Mapped[str] = mapped_column(String(200))
    shift_count: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    acquiring: Mapped[float] = mapped_column(Float)
    salary_paid: Mapped[float] = mapped_column(Float) # Calculated salary at submission
    expense: Mapped[float] = mapped_column(Float)
    cash_balance: Mapped[float] = mapped_column(Float)
    visitors: Mapped[int] = mapped_column(Integer)
    birthdays: Mapped[int] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    salary_level: Mapped[int] = mapped_column(Integer)
    trainee_salary: Mapped[float] = mapped_column(Float, default=0.0)
    city: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'gomel' | 'minsk'
    
    # ─── Payment Tracking ───
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="reports")


class SalarySetting(Base):
    """Progressive salary scale level."""
    __tablename__ = "salary_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[int] = mapped_column(Integer)
    threshold_min: Mapped[float] = mapped_column(Float)
    threshold_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # None = unlimited
    base_salary: Mapped[float] = mapped_column(Float)
    percentage: Mapped[float] = mapped_column(Float)  # e.g. 0.10 for 10%


class Plan(Base):
    """Sales plan for a project or globally."""
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True) # NULL means global plan
    city: Mapped[str | None] = mapped_column(String(20), nullable=True) # 'gomel' | 'minsk'
    plan_amount: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(10)) # day, month
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(500))
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    admin: Mapped["User"] = relationship()


class ManagementExpense(Base):
    """Management expenses entered by admin as separate transactions."""
    __tablename__ = "management_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[py_date] = mapped_column(Date, index=True)
    city: Mapped[str] = mapped_column(String(20)) # 'gomel' | 'minsk'
    category: Mapped[str] = mapped_column(String(50)) # 'расходник' | 'техника' | 'аренда'
    amount: Mapped[float] = mapped_column(Float)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
