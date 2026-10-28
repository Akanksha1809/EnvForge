"""Registration/login/token-refresh business logic, kept out of the router
so it's directly unit-testable and reusable (e.g. by the GitHub OAuth path)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, create_token, hash_password, verify_password
from app.models.enums import PlatformRole
from app.models.user import User
from app.schemas.auth import TokenPair


class AuthError(Exception):
    pass


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, *, email: str, full_name: str, password: str) -> User:
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise AuthError("A user with this email already exists")

    # First registered user becomes platform admin — every subsequent user
    # defaults to developer. This mirrors how most self-hosted IDPs bootstrap
    # an initial admin without a separate seeding step.
    user_count = (await db.execute(select(User.id))).scalars().all()
    role = PlatformRole.PLATFORM_ADMIN if not user_count else PlatformRole.DEVELOPER

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        platform_role=role.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or user.hashed_password is None:
        raise AuthError("Invalid email or password")
    if not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("User account is disabled")
    return user


def issue_token_pair(user: User) -> TokenPair:
    claims = {"role": user.platform_role, "email": user.email}
    access = create_token(user.id, TokenType.ACCESS, claims)
    refresh = create_token(user.id, TokenType.REFRESH, claims)
    return TokenPair(access_token=access, refresh_token=refresh)
