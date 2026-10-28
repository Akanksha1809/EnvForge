from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import InvalidTokenError, TokenType, decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshRequest,
    TokenPair,
    UserLoginRequest,
    UserOut,
    UserRegisterRequest,
)
from app.services import auth as auth_service
from app.services.audit import record as audit_record

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    try:
        user = await auth_service.register_user(
            db, email=payload.email, full_name=payload.full_name, password=payload.password
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="user.register",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_label=user.email,
    )
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        user = await auth_service.authenticate_user(
            db, email=payload.email, password=payload.password
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    await audit_record(
        db,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_label=user.email,
    )
    return auth_service.issue_token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        decoded = decode_token(payload.refresh_token, expected_type=TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc

    user = await auth_service.get_user_by_id(db, decoded["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return auth_service.issue_token_pair(user)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
