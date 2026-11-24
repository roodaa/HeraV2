"""Schémas mission et étape."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.mission import ModeTransport, StatutMission, TypeMission
from app.schemas.common import BaseSchema
from app.schemas.user import UserMinimal


# ==================== Schémas Étape ====================


class EtapeBase(BaseSchema):
    """Champs communs étape."""

    ville_depart: str = Field(..., min_length=1, max_length=255)
    ville_arrivee: str = Field(..., min_length=1, max_length=255)
    mode_transport: ModeTransport
    distance_km: Decimal = Field(..., gt=0, decimal_places=2)
    classe_transport: str | None = Field(None, max_length=50)


class EtapeCreate(EtapeBase):
    """Création d'une étape."""

    ordre: int = Field(default=1, ge=1)


class EtapeUpdate(BaseSchema):
    """Mise à jour d'une étape."""

    ville_depart: str | None = Field(None, min_length=1, max_length=255)
    ville_arrivee: str | None = Field(None, min_length=1, max_length=255)
    mode_transport: ModeTransport | None = None
    distance_km: Decimal | None = Field(None, gt=0)
    classe_transport: str | None = Field(None, max_length=50)
    ordre: int | None = Field(None, ge=1)


class EtapeResponse(EtapeBase):
    """Réponse étape."""

    id: UUID
    ordre: int
    distance_auto: bool
    impact_co2_kg: Decimal
    created_at: datetime
    updated_at: datetime


# ==================== Schémas Mission ====================


class MissionBase(BaseSchema):
    """Champs communs mission."""

    date_depart: date
    date_retour: date | None = None
    motif: str = Field(..., min_length=1, max_length=500)
    type_mission: TypeMission = TypeMission.ALLER_RETOUR
    commentaire: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        """Vérifie que la date de retour est après la date de départ."""
        if self.date_retour and self.date_retour < self.date_depart:
            raise ValueError("La date de retour doit être après la date de départ")
        return self


class MissionCreate(MissionBase):
    """Création d'une mission avec étapes."""

    etapes: list[EtapeCreate] = Field(..., min_length=1)


class MissionUpdate(BaseSchema):
    """Mise à jour d'une mission."""

    date_depart: date | None = None
    date_retour: date | None = None
    motif: str | None = Field(None, min_length=1, max_length=500)
    type_mission: TypeMission | None = None
    commentaire: str | None = None


class MissionResponse(MissionBase):
    """Réponse mission (sans étapes)."""

    id: UUID
    statut: StatutMission
    distance_totale_km: Decimal
    impact_co2_kg: Decimal
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class MissionWithEtapes(MissionResponse):
    """Mission avec ses étapes."""

    etapes: list[EtapeResponse]
    user: UserMinimal


class MissionWithUser(MissionResponse):
    """Mission avec informations utilisateur."""

    user: UserMinimal


# ==================== Schémas pour les actions ====================


class MissionValidate(BaseSchema):
    """Validation/rejet d'une mission."""

    commentaire: str | None = Field(None, max_length=500)


class MissionSubmit(BaseSchema):
    """Soumission d'une mission pour validation."""

    pass


# ==================== Schémas pour les statistiques ====================


class MissionStats(BaseSchema):
    """Statistiques des missions."""

    total_missions: int
    total_distance_km: Decimal
    total_impact_co2_kg: Decimal
    missions_par_statut: dict[str, int]
    missions_par_transport: dict[str, int]
