"""Schémas achat."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.user import UserMinimal


class AchatBase(BaseSchema):
    """Champs communs achat."""

    date_achat: date
    description: str = Field(..., min_length=1, max_length=500)
    montant_euros: Decimal = Field(..., gt=0, decimal_places=2)
    code_nacres: str | None = Field(None, max_length=20)
    categorie: str | None = Field(None, max_length=100)
    commentaire: str | None = None


class AchatCreate(AchatBase):
    """Création d'un achat."""

    equipe_id: UUID | None = None


class AchatUpdate(BaseSchema):
    """Mise à jour d'un achat."""

    date_achat: date | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    montant_euros: Decimal | None = Field(None, gt=0)
    code_nacres: str | None = Field(None, max_length=20)
    categorie: str | None = Field(None, max_length=100)
    commentaire: str | None = None
    equipe_id: UUID | None = None


class AchatResponse(AchatBase):
    """Réponse achat."""

    id: UUID
    impact_co2_kg: Decimal
    facteur_emission: Decimal | None
    user_id: UUID
    equipe_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AchatWithUser(AchatResponse):
    """Achat avec informations utilisateur."""

    user: UserMinimal


class AchatWithDetails(AchatResponse):
    """Achat avec toutes les relations."""

    user: UserMinimal
    equipe_name: str | None = None


# ==================== Schémas pour les statistiques ====================


class AchatStats(BaseSchema):
    """Statistiques des achats."""

    total_achats: int
    total_montant_euros: Decimal
    total_impact_co2_kg: Decimal
    achats_par_categorie: dict[str, int]
    impact_par_categorie: dict[str, float]


class AchatParNacres(BaseSchema):
    """Agrégation par code NACRES."""

    code_nacres: str
    libelle: str | None
    nombre_achats: int
    total_montant: Decimal
    total_impact_co2: Decimal
