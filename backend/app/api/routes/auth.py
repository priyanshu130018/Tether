from datetime import datetime, timedelta, timezone
import re
import uuid
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.auth import TenantContext, get_current_tenant_context, log_audit_event
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import RefreshToken, Role, Tenant, TenantMembership, User
from app.schemas import (
    AuthResponse,
    TenantMembershipRead,
    TenantRead,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserLogin,
    UserProfileResponse,
    UserRead,
    UserRegister,
)

router = APIRouter(tags=["authentication"])
settings = get_settings()


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or f"org-{uuid.uuid4().hex[:8]}"


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: UserRegister,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    # 1. Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"auth:register:{client_ip}", limit=15, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait a minute.",
        )

    # 2. Check if email exists
    existing = db.scalars(select(User).where(User.email == req.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # 3. Create User
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip(),
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    # 4. Create Organization / Tenant
    org_name = req.tenant_name.strip() if req.tenant_name else f"{user.full_name}'s Team"
    base_slug = _slugify(org_name)
    slug = base_slug
    idx = 1
    while db.scalars(select(Tenant).where(Tenant.slug == slug)).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    tenant = Tenant(name=org_name, slug=slug)
    db.add(tenant)
    db.flush()

    # 5. Create TenantMembership as OWNER
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=Role.OWNER,
    )
    db.add(membership)
    db.flush()

    # 6. Issue Tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": tenant.id,
        "role": Role.OWNER.value,
    })
    raw_refresh = generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_record)

    # 7. Audit Log
    log_audit_event(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        action="USER_REGISTER",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": user.email, "tenant_slug": tenant.slug},
    )
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    # 8. Set HttpOnly Cookie for Refresh Token
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
        secure=False,  # Set to True in production HTTPS
        path="/",
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
        active_tenant=TenantRead.model_validate(tenant),
        role=Role.OWNER,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    req: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    # 1. Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"auth:login:{client_ip}:{req.email.lower()}", limit=20, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again in 1 minute.",
        )

    # 2. Find user & verify password
    clean_email = req.email.strip().lower()
    user = db.scalars(select(User).where(User.email == clean_email)).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact your organization owner.",
        )

    # 3. Resolve active tenant
    memberships = db.scalars(
        select(TenantMembership)
        .where(TenantMembership.user_id == user.id)
        .options(joinedload(TenantMembership.tenant))
        .order_by(TenantMembership.id.asc())
    ).all()

    if not memberships:
        # Fallback to default tenant if no membership exists
        default_tenant = db.scalars(select(Tenant).where(Tenant.slug == "default-org")).first()
        if not default_tenant:
            default_tenant = Tenant(name="Default Organization", slug="default-org")
            db.add(default_tenant)
            db.flush()
        active_membership = TenantMembership(user_id=user.id, tenant_id=default_tenant.id, role=Role.OWNER)
        db.add(active_membership)
        db.flush()
    else:
        if req.tenant_id:
            active_membership = next((m for m in memberships if m.tenant_id == req.tenant_id), None)
            if not active_membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to the selected organization",
                )
        else:
            active_membership = memberships[0]

    # 4. Update last login
    user.last_login_at = datetime.now(timezone.utc)

    # 5. Issue Tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": active_membership.tenant_id,
        "role": active_membership.role.value,
    })
    raw_refresh = generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_record)

    log_audit_event(
        db,
        tenant_id=active_membership.tenant_id,
        user_id=user.id,
        action="USER_LOGIN",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": user.email, "ip": client_ip},
    )
    db.commit()

    # 6. Set HttpOnly Cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
        secure=False,
        path="/",
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
        active_tenant=TenantRead.model_validate(active_membership.tenant),
        role=active_membership.role,
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(
    response: Response,
    req: TokenRefreshRequest = TokenRefreshRequest(),
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    token_str = req.refresh_token or refresh_token_cookie
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    t_hash = hash_token(token_str)
    # 1. Query by hash to find any existing token record
    existing_record = db.scalars(
        select(RefreshToken)
        .where(RefreshToken.token_hash == t_hash)
        .options(joinedload(RefreshToken.user))
    ).first()

    if not existing_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session refresh token",
        )

    # 2. REUSE / REPLAY DETECTION:
    # If the token was already revoked, someone may be attempting a replay attack with an old token.
    # Invalidate all active tokens for this user immediately and log an audit event.
    if existing_record.revoked_at is not None:
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == existing_record.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        log_audit_event(
            db,
            tenant_id=1,
            user_id=existing_record.user_id,
            action="SECURITY_ALERT_REFRESH_TOKEN_REUSE",
            resource_type="auth",
            resource_id=str(existing_record.user_id),
            metadata={"reason": "Revoked refresh token presented for exchange"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security alert: Compromised refresh token reuse detected. All sessions revoked.",
        )

    # 3. Check expiration or inactive user
    token_expiry = existing_record.expires_at
    if token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)
    if token_expiry <= datetime.now(timezone.utc) or not existing_record.user or not existing_record.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session refresh token",
        )

    # 4. Token Rotation: Revoke current token
    existing_record.revoked_at = datetime.now(timezone.utc)

    # 5. Issue new refresh token
    new_raw_refresh = generate_refresh_token()
    new_refresh_record = RefreshToken(
        user_id=existing_record.user_id,
        token_hash=hash_token(new_raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_refresh_record)

    # 6. Determine user active tenant & issue new access token
    membership = db.scalars(
        select(TenantMembership)
        .where(TenantMembership.user_id == existing_record.user_id)
        .order_by(TenantMembership.id.asc())
    ).first()

    tenant_id = membership.tenant_id if membership else 1
    role_val = membership.role.value if membership else Role.MEMBER.value

    new_access_token = create_access_token({
        "sub": str(existing_record.user_id),
        "email": existing_record.user.email,
        "tenant_id": tenant_id,
        "role": role_val,
    })

    db.commit()

    # 7. Set rotated HttpOnly Cookie
    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
        secure=False,
        path="/",
    )

    return TokenRefreshResponse(access_token=new_access_token, token_type="bearer")


@router.post("/logout")
def logout(
    response: Response,
    req: TokenRefreshRequest = TokenRefreshRequest(),
    refresh_token_cookie: str | None = Cookie(None, alias="refresh_token"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token_str = req.refresh_token or refresh_token_cookie
    if token_str:
        t_hash = hash_token(token_str)
        record = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == t_hash)).first()
        if record:
            record.revoked_at = datetime.now(timezone.utc)
            db.commit()

    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="access_token", path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    memberships = db.scalars(
        select(TenantMembership)
        .where(TenantMembership.user_id == ctx.user.id)
        .options(joinedload(TenantMembership.tenant))
        .order_by(TenantMembership.id.asc())
    ).all()

    return UserProfileResponse(
        user=UserRead.model_validate(ctx.user),
        active_tenant=TenantRead.model_validate(ctx.tenant),
        role=ctx.role,
        memberships=[
            TenantMembershipRead(
                id=m.id,
                user_id=m.user_id,
                tenant_id=m.tenant_id,
                role=m.role,
                created_at=m.created_at,
            )
            for m in memberships
        ],
    )
