# tests/unit/test_object_authorization.py

"""
Unit tests for Guarantee 6 — Object Authorization & Tenant Isolation (IDOR Resistance).
"""

from __future__ import annotations

import pytest
from security.object_authorization import (
    AccessAction,
    AuthorizationError,
    IdentityContext,
    ObjectAuthorizationGate,
    ResourceHandle,
)


def test_tenant_a_cannot_read_tenant_b_run() -> None:
    id_a = IdentityContext(tenant_id="tenant_a", user_id="user_a")
    res_b = ResourceHandle(resource_type="run", resource_id="run_100", owner_tenant_id="tenant_b", owner_user_id="user_b")

    with pytest.raises(AuthorizationError) as exc_info:
        ObjectAuthorizationGate.authorize(id_a, res_b, AccessAction.READ)
    assert exc_info.value.status_code == 404


def test_tenant_a_cannot_cancel_or_delete_tenant_b_execution() -> None:
    id_a = IdentityContext(tenant_id="tenant_a", user_id="user_a")
    res_b = ResourceHandle(resource_type="execution", resource_id="exec_55", owner_tenant_id="tenant_b", owner_user_id="user_b")

    for action in (AccessAction.CANCEL, AccessAction.DELETE, AccessAction.UPDATE, AccessAction.REPLAY):
        with pytest.raises(AuthorizationError) as exc_info:
            ObjectAuthorizationGate.authorize(id_a, res_b, action)
        assert exc_info.value.status_code == 404


def test_same_tenant_other_user_read_permitted_write_denied() -> None:
    user_1 = IdentityContext(tenant_id="tenant_a", user_id="user_1")
    res_user_2 = ResourceHandle(resource_type="artifact", resource_id="art_1", owner_tenant_id="tenant_a", owner_user_id="user_2")

    # Read within same tenant permitted
    assert ObjectAuthorizationGate.authorize(user_1, res_user_2, AccessAction.READ) is True

    # Mutate within same tenant by non-owner non-admin denied
    with pytest.raises(AuthorizationError) as exc_info:
        ObjectAuthorizationGate.authorize(user_1, res_user_2, AccessAction.DELETE)
    assert exc_info.value.status_code == 403


def test_parent_child_resource_id_mismatch_rejected() -> None:
    user_1 = IdentityContext(tenant_id="tenant_a", user_id="user_1")
    child_res = ResourceHandle(
        resource_type="artifact",
        resource_id="art_99",
        owner_tenant_id="tenant_a",
        owner_user_id="user_1",
        parent_resource_id="run_a",
    )

    with pytest.raises(AuthorizationError) as exc_info:
        ObjectAuthorizationGate.authorize(user_1, child_res, AccessAction.READ, requested_parent_id="run_b_tampered")
    assert exc_info.value.status_code == 403


def test_tenant_admin_can_manage_tenant_resources() -> None:
    admin = IdentityContext(tenant_id="tenant_a", user_id="admin_1", roles=("tenant_admin",))
    res_user_2 = ResourceHandle(resource_type="run", resource_id="run_42", owner_tenant_id="tenant_a", owner_user_id="user_2")

    assert ObjectAuthorizationGate.authorize(admin, res_user_2, AccessAction.DELETE) is True
    assert ObjectAuthorizationGate.authorize(admin, res_user_2, AccessAction.CANCEL) is True
