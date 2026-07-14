from .database import SessionLocal
from .models import AuditLog


async def write_audit(actor: str, action: str, resource_type: str | None = None, resource_id: str | None = None, metadata: dict | None = None):
    async with SessionLocal() as session:
        session.add(AuditLog(actor=actor, action=action, resource_type=resource_type, resource_id=resource_id, metadata_json=metadata or {}))
        await session.commit()
