"""Schémas utilisateur."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class UserBase(BaseSchema):
    """Champs communs utilisateur."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class UserCreate(UserBase):
    """Création d'un utilisateur (auth locale)."""

    password: str = Field(..., min_length=8)


class UserCreateExternal(UserBase):
    """Création d'un utilisateur depuis auth externe (SAML/OIDC)."""

    external_id: str
    auth_provider: str


class UserUpdate(BaseSchema):
    """Mise à jour d'un utilisateur."""

    email: EmailStr | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None
    equipe_id: UUID | None = None


class UserPasswordUpdate(BaseSchema):
    """Mise à jour du mot de passe."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    """Réponse utilisateur."""

    id: UUID
    is_active: bool
    is_superuser: bool
    auth_provider: str
    equipe_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None


class UserWithRoles(UserResponse):
    """Utilisateur avec ses rôles."""

    roles: list["RoleMinimal"]


class UserMinimal(BaseSchema):
    """Utilisateur minimal (pour les listes)."""

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str


class RoleMinimal(BaseSchema):
    """Rôle minimal (pour inclusion dans User)."""

    id: UUID
    code: str
    name: str


# Pour éviter les imports circulaires
UserWithRoles.model_rebuild()
