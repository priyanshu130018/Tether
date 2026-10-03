import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import (
    TenantContext,
    get_current_user,
    log_audit_event,
    require_role,
)
from app.core.db import get_db
from app.core.security import hash_password
from app.models import Role, Tenant, TenantMembership, User
from app.schemas import (
    MemberInvite,
    MemberRoleUpdate,
    TenantCreate,
    TenantMembershipRead,
    TenantRead,
    UserRead,
)

router = APIRouter(tags=["tenants"])


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or f"org-{uuid.uuid4().hex[:8]}"


@router.get("", response_model=list[TenantRead])
def list_user_tenants(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TenantRead]:
    memberships = db.scalars(
        select(TenantMembership)
        .where(TenantMembership.user_id == user.id)
        .options(joinedload(TenantMembership.tenant))
        .order_by(TenantMembership.id.asc())
    ).all()

    result = []
    for m in memberships:
        t_read = TenantRead.model_validate(m.tenant)
        t_read.role = m.role
        result.append(t_read)
    return result


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    req: TenantCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantRead:
    base_slug = req.slug or _slugify(req.name)
    slug = base_slug
    idx = 1
    while db.scalars(select(Tenant).where(Tenant.slug == slug)).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    tenant = Tenant(name=req.name.strip(), slug=slug)
    db.add(tenant)
    db.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=Role.OWNER,
    )
    db.add(membership)

    log_audit_event(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        action="TENANT_CREATED",
        resource_type="tenant",
        resource_id=str(tenant.id),
        metadata={"name": tenant.name, "slug": tenant.slug},
    )
    db.commit()
    db.refresh(tenant)

    t_read = TenantRead.model_validate(tenant)
    t_read.role = Role.OWNER
    return t_read


@router.get("/members", response_model=list[TenantMembershipRead])
def list_tenant_members(
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[TenantMembershipRead]:
    memberships = db.scalars(
        select(TenantMembership)
        .where(TenantMembership.tenant_id == ctx.tenant.id)
        .options(joinedload(TenantMembership.user))
        .order_by(TenantMembership.id.asc())
    ).all()

    return [
        TenantMembershipRead(
            id=m.id,
            user_id=m.user_id,
            tenant_id=m.tenant_id,
            role=m.role,
            user=UserRead.model_validate(m.user) if m.user else None,
            created_at=m.created_at,
        )
        for m in memberships
    ]


@router.post("/members", response_model=TenantMembershipRead, status_code=status.HTTP_201_CREATED)
def invite_or_add_member(
    req: MemberInvite,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> TenantMembershipRead:
    # Only OWNER can grant OWNER role
    if req.role == Role.OWNER and ctx.role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an organization OWNER can assign the OWNER role.",
        )

    clean_email = req.email.strip().lower()
    target_user = db.scalars(select(User).where(User.email == clean_email)).first()

    if not target_user:
        # Auto-provision user with temporary account
        full_name = req.full_name.strip() if req.full_name else clean_email.split("@")[0].capitalize()
        temp_pwd = f"Tether_{uuid.uuid4().hex[:12]}!"
        target_user = User(
            email=clean_email,
            password_hash=hash_password(temp_pwd),
            full_name=full_name,
            is_active=True,
            is_verified=True,
        )
        db.add(target_user)
        db.flush()

    # Check if already a member
    existing_membership = db.scalars(
        select(TenantMembership).where(
            TenantMembership.user_id == target_user.id,
            TenantMembership.tenant_id == ctx.tenant.id,
        )
    ).first()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user is already a member of this organization.",
        )

    membership = TenantMembership(
        user_id=target_user.id,
        tenant_id=ctx.tenant.id,
        role=req.role,
    )
    db.add(membership)

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="MEMBER_INVITED",
        resource_type="tenant_membership",
        resource_id=str(target_user.id),
        metadata={"invited_email": target_user.email, "role": req.role.value},
    )
    db.commit()
    db.refresh(membership)

    return TenantMembershipRead(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        user=UserRead.model_validate(target_user),
        created_at=membership.created_at,
    )


@router.patch("/members/{membership_id}", response_model=TenantMembershipRead)
def update_member_role(
    membership_id: int,
    req: MemberRoleUpdate,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> TenantMembershipRead:
    membership = db.scalars(
        select(TenantMembership)
        .where(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == ctx.tenant.id,
        )
        .options(joinedload(TenantMembership.user))
    ).first()

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    if req.role == Role.OWNER and ctx.role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an OWNER can promote members to OWNER",
        )

    # Prevent demoting the last OWNER
    if membership.role == Role.OWNER and req.role != Role.OWNER:
        owner_count = db.scalar(
            select(func.count(TenantMembership.id)).where(
                TenantMembership.tenant_id == ctx.tenant.id,
                TenantMembership.role == Role.OWNER,
            )
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last remaining OWNER of the organization.",
            )

    old_role = membership.role
    membership.role = req.role

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="MEMBER_ROLE_CHANGED",
        resource_type="tenant_membership",
        resource_id=str(membership.id),
        metadata={"user_id": membership.user_id, "from_role": old_role.value, "to_role": req.role.value},
    )
    db.commit()
    db.refresh(membership)

    return TenantMembershipRead(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        user=UserRead.model_validate(membership.user) if membership.user else None,
        created_at=membership.created_at,
    )


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    membership_id: int,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    membership = db.scalars(
        select(TenantMembership).where(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == ctx.tenant.id,
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    # Prevent removing the last owner
    if membership.role == Role.OWNER:
        owner_count = db.scalar(
            select(func.count(TenantMembership.id)).where(
                TenantMembership.tenant_id == ctx.tenant.id,
                TenantMembership.role == Role.OWNER,
            )
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last remaining OWNER of the organization.",
            )

    db.delete(membership)
    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="MEMBER_REMOVED",
        resource_type="tenant_membership",
        resource_id=str(membership_id),
        metadata={"removed_user_id": membership.user_id},
    )
    db.commit()
