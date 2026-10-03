from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import AuditLog, Role, Tenant, TenantMembership, User

security_bearer = HTTPBearer(auto_error=False)

ROLE_HIERARCHY: dict[Role, int] = {
    Role.VIEWER: 10,
    Role.MEMBER: 20,
    Role.ADMIN: 30,
    Role.OWNER: 40,
}


@dataclass
class TenantContext:
    user: User
    tenant: Tenant
    membership: TenantMembership
    role: Role


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    token: str | None = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token credentials",
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def get_current_tenant_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> TenantContext:
    # 1. Determine requested tenant id
    target_tenant_id: int | None = None
    if x_tenant_id:
        try:
            target_tenant_id = int(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Tenant-ID header format",
            )

    # 2. Query memberships for this user
    memberships_stmt = (
        select(TenantMembership)
        .where(TenantMembership.user_id == current_user.id)
        .order_by(TenantMembership.id.asc())
    )
    memberships = list(db.scalars(memberships_stmt).all())

    active_membership: TenantMembership | None = None

    if target_tenant_id is not None:
        for m in memberships:
            if m.tenant_id == target_tenant_id:
                active_membership = m
                break
        if not active_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the requested tenant organization",
            )
    else:
        if memberships:
            active_membership = memberships[0]
        else:
            # Fallback: if user has no memberships, attach to or create default tenant
            default_tenant = db.scalars(select(Tenant).where(Tenant.slug == "default-org")).first()
            if not default_tenant:
                default_tenant = Tenant(name="Default Organization", slug="default-org")
                db.add(default_tenant)
                db.flush()

            active_membership = TenantMembership(
                user_id=current_user.id,
                tenant_id=default_tenant.id,
                role=Role.OWNER,
            )
            db.add(active_membership)
            db.commit()
            db.refresh(active_membership)

    return TenantContext(
        user=current_user,
        tenant=active_membership.tenant,
        membership=active_membership,
        role=active_membership.role,
    )


def require_role(min_role: Role) -> Callable[[TenantContext], TenantContext]:
    """
    Dependency checking that the user has at least the specified minimum role
    (VIEWER < MEMBER < ADMIN < OWNER).
    """
    min_weight = ROLE_HIERARCHY[min_role]

    def role_checker(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        user_weight = ROLE_HIERARCHY.get(ctx.role, 0)
        if user_weight < min_weight:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires minimum role '{min_role.value}'. Your role is '{ctx.role.value}'.",
            )
        return ctx

    return role_checker


def log_audit_event(
    db: Session,
    tenant_id: int,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Record an immutable audit log entry."""
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry
