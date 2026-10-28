"""Shared FastAPI dependencies: DB session, current user, permission gates."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, TokenType, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth import get_user_by_id
from app.services.rbac import Permission, require_permission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error
    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise credentials_error from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require(permission: Permission) -> Callable:
    async def _dependency(user: User = Depends(get_current_user)) -> User:
        require_permission(user, permission)
        return user

    return _dependency
