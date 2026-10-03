from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    TenantContext,
    require_role,
)
from app.core.db import get_db
from app.models import AuditLog, Role
from app.schemas import AuditLogRead

router = APIRouter(tags=["audit-logs"])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> list[AuditLogRead]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == ctx.tenant.id)
        .order_by(AuditLog.created_at.desc())
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)

    stmt = stmt.offset(offset).limit(limit)
    records = db.scalars(stmt).all()

    return [
        AuditLogRead(
            id=r.id,
            tenant_id=r.tenant_id,
            user_id=r.user_id,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            metadata=r.metadata_json or {},
            created_at=r.created_at,
        )
        for r in records
    ]
