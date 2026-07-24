# security/object_authorization.py

"""
Guarantee 6 — Object Authorization & Tenant Isolation (IDOR Resistance).

Enforces strict tenant ownership and access boundaries across all direct object references:
  - /v1/runs/{run_id}
  - /v1/executions/{execution_id}
  - /v1/artifacts/{artifact_id}
  - /v1/manifests/{manifest_id}
  - /v1/benchmarks/{benchmark_id}
  - /v1/replays/{run_id}
  - /v1/plugins/{plugin_id}
  - /v1/projects/{project_id}
  - /v1/organizations/{organization_id}
  - /v1/users/{user_id}
  - /v1/api-keys/{key_id}

Actions: read, update, delete, cancel, replay, download, export, admin.
Fails closed with 403 Forbidden or 404 Not Found (indistinguishable anti-enumeration).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class AccessAction(Enum):
    READ = auto()
    UPDATE = auto()
    DELETE = auto()
    CANCEL = auto()
    REPLAY = auto()
    DOWNLOAD = auto()
    EXPORT = auto()
    ADMIN = auto()


class AuthorizationError(Exception):
    """Raised when access control or tenant isolation boundary is violated."""
    def __init__(self, message: str = "Access denied", status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class IdentityContext:
    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = ("user",)
    organization_id: str | None = None

    def is_admin(self) -> bool:
        return "admin" in self.roles or "tenant_admin" in self.roles


@dataclass(frozen=True, slots=True)
class ResourceHandle:
    resource_type: str
    resource_id: str
    owner_tenant_id: str
    owner_user_id: str
    parent_resource_id: str | None = None
    parent_tenant_id: str | None = None


class ObjectAuthorizationGate:
    """Enforces strict IDOR protection and cross-tenant resource isolation."""

    @staticmethod
    def authorize(
        identity: IdentityContext,
        resource: ResourceHandle,
        action: AccessAction = AccessAction.READ,
        *,
        requested_parent_id: str | None = None,
    ) -> bool:
        """Enforces tenant ownership, parent-child integrity, and action-level authorization.

        Fails closed with AuthorizationError if any boundary condition is violated.
        """
        # 1. Primary Tenant Isolation Check
        if identity.tenant_id != resource.owner_tenant_id:
            # Mask existence with 404 to prevent tenant resource enumeration
            raise AuthorizationError("Resource not found or access denied", status_code=404)

        # 2. Parent-Child Relationship Integrity (Prevent cross-tenant child access)
        if resource.parent_tenant_id and resource.parent_tenant_id != identity.tenant_id:
            raise AuthorizationError("Resource not found or access denied", status_code=404)

        if requested_parent_id and resource.parent_resource_id and requested_parent_id != resource.parent_resource_id:
            raise AuthorizationError("Parent resource mismatch", status_code=403)

        # 3. User Ownership & Admin Override
        if not identity.is_admin() and identity.user_id != resource.owner_user_id:
            # Non-admin users cannot mutate, delete, cancel, or administer other users' resources
            if action in (AccessAction.UPDATE, AccessAction.DELETE, AccessAction.CANCEL, AccessAction.ADMIN):
                raise AuthorizationError("Insufficient permissions for target operation", status_code=403)

        return True
