import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlatformRole
from app.services import auth as auth_service
from app.services.rbac import Permission, has_global_permission


@pytest.mark.asyncio
async def test_first_registered_user_becomes_platform_admin(db_session: AsyncSession) -> None:
    user = await auth_service.register_user(
        db_session, email="first@example.com", full_name="First User", password="supersecret123"
    )
    assert user.platform_role == PlatformRole.PLATFORM_ADMIN.value


@pytest.mark.asyncio
async def test_second_registered_user_becomes_developer(db_session: AsyncSession) -> None:
    await auth_service.register_user(
        db_session, email="first@example.com", full_name="First User", password="supersecret123"
    )
    second = await auth_service.register_user(
        db_session, email="second@example.com", full_name="Second User", password="supersecret123"
    )
    assert second.platform_role == PlatformRole.DEVELOPER.value


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected(db_session: AsyncSession) -> None:
    await auth_service.register_user(
        db_session, email="dup@example.com", full_name="A", password="supersecret123"
    )
    with pytest.raises(auth_service.AuthError):
        await auth_service.register_user(
            db_session, email="dup@example.com", full_name="B", password="supersecret123"
        )


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password_rejected(db_session: AsyncSession) -> None:
    await auth_service.register_user(
        db_session, email="x@example.com", full_name="X", password="correct-password"
    )
    with pytest.raises(auth_service.AuthError):
        await auth_service.authenticate_user(
            db_session, email="x@example.com", password="wrong-password"
        )


@pytest.mark.asyncio
async def test_authenticate_user_success(db_session: AsyncSession) -> None:
    created = await auth_service.register_user(
        db_session, email="y@example.com", full_name="Y", password="correct-password"
    )
    authed = await auth_service.authenticate_user(
        db_session, email="y@example.com", password="correct-password"
    )
    assert authed.id == created.id


def test_viewer_cannot_create_environment() -> None:
    from app.models.user import User

    viewer = User(email="v@example.com", full_name="V", platform_role=PlatformRole.VIEWER.value)
    assert not has_global_permission(viewer, Permission.ENVIRONMENT_CREATE)


def test_developer_can_create_environment() -> None:
    from app.models.user import User

    dev = User(email="d@example.com", full_name="D", platform_role=PlatformRole.DEVELOPER.value)
    assert has_global_permission(dev, Permission.ENVIRONMENT_CREATE)


def test_platform_admin_has_every_permission() -> None:
    from app.models.user import User

    admin = User(
        email="a@example.com", full_name="A", platform_role=PlatformRole.PLATFORM_ADMIN.value
    )
    for permission in Permission:
        assert has_global_permission(admin, permission)
