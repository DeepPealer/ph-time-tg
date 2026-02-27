from bot.database.models import AuditLog

async def log_action(session: "AsyncSession", admin_id: int, action: str, details: str = None):
    """Log an administrative action to the database."""
    log = AuditLog(
        admin_id=admin_id,
        action=action,
        details=details
    )
    session.add(log)
    await session.commit()
