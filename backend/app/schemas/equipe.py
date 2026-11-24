"""Schémas équipe."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.user import UserMinimal


class EquipeBase(BaseSchema):
    """Champs communs équipe."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class EquipeCreate(EquipeBase):
    """Création d'une équipe."""

    pass


class EquipeUpdate(BaseSchema):
    """Mise à jour d'une équipe."""

    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class EquipeResponse(EquipeBase):
    """Réponse équipe."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class EquipeWithMembers(EquipeResponse):
    """Équipe avec ses membres."""

    members: list[UserMinimal]
    member_count: int


class AffectUserToEquipe(BaseSchema):
    """Affectation d'un utilisateur à une équipe."""

    user_id: UUID
