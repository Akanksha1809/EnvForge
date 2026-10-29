"""Locks in the full RBAC permission matrix (section 12 of the spec) so a
future change to one role's permissions can't silently widen or narrow
another role's without a test failing. Complements
tests/integration/test_rbac_depth.py, which exercises the same matrix
through the actual API rather than calling the service directly.
"""

import pytest

from app.models.enums import PlatformRole
from app.models.user import User
from app.services.rbac import Permission, has_global_permission


def _user(role: PlatformRole) -> User:
    return User(email=f"{role.value}@example.com", full_name=role.value, platform_role=role.value)


@pytest.mark.parametrize(
    ("permission", "expected_roles"),
    [
        (
            Permission.APPLICATION_REGISTER,
            {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN, PlatformRole.DEVELOPER},
        ),
        (
            Permission.APPLICATION_MANAGE,
            {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN},
        ),
        (
            Permission.ENVIRONMENT_CREATE,
            {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN, PlatformRole.DEVELOPER},
        ),
        (
            Permission.ENVIRONMENT_DELETE,
            {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN, PlatformRole.DEVELOPER},
        ),
        (
            Permission.ENVIRONMENT_EXTEND,
            {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN, PlatformRole.DEVELOPER},
        ),
        (Permission.TEMPLATE_MANAGE, {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN}),
        (Permission.TEAM_MANAGE, {PlatformRole.PLATFORM_ADMIN, PlatformRole.TEAM_ADMIN}),
        (Permission.PLATFORM_ADMINISTER, {PlatformRole.PLATFORM_ADMIN}),
    ],
)
def test_permission_matrix(permission: Permission, expected_roles: set[PlatformRole]) -> None:
    for role in PlatformRole:
        expected = role in expected_roles
        actual = has_global_permission(_user(role), permission)
        assert actual == expected, (
            f"{role.value} {'should' if expected else 'should NOT'} have {permission.value}"
        )


def test_viewer_has_no_permissions_at_all() -> None:
    viewer = _user(PlatformRole.VIEWER)
    for permission in Permission:
        assert has_global_permission(viewer, permission) is False
