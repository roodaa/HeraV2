"""Schémas rôles et permissions."""

from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class PermissionBase(BaseSchema):
    """Champs communs permission."""

    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    module: str = Field(..., min_length=1, max_length=50)


class PermissionResponse(PermissionBase):
    """Réponse permission."""

    id: UUID


class PermissionsByModule(BaseSchema):
    """Permissions groupées par module."""

    module: str
    permissions: list[PermissionResponse]


class RoleBase(BaseSchema):
    """Champs communs rôle."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class RoleCreate(RoleBase):
    """Création d'un rôle."""

    permission_ids: list[UUID] = []


class RoleUpdate(BaseSchema):
    """Mise à jour d'un rôle."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    permission_ids: list[UUID] | None = None


class RoleResponse(RoleBase):
    """Réponse rôle."""

    id: UUID
    is_system: bool


class RoleWithPermissions(RoleResponse):
    """Rôle avec ses permissions."""

    permissions: list[PermissionResponse]


class RoleAssign(BaseSchema):
    """Attribution d'un rôle."""

    role_id: UUID


class RoleRemove(BaseSchema):
    """Retrait d'un rôle."""

    role_id: UUID
