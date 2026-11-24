"""Schémas matériel informatique."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.materiel import StatutMateriel, TypeMateriel
from app.schemas.common import BaseSchema
from app.schemas.user import UserMinimal


class MaterielBase(BaseSchema):
    """Champs communs matériel."""

    type_materiel: TypeMateriel
    marque: str | None = Field(None, max_length=100)
    modele: str | None = Field(None, max_length=200)
    numero_serie: str | None = Field(None, max_length=100)
    date_acquisition: date
    date_fin_vie: date | None = None
    statut: StatutMateriel = StatutMateriel.EN_SERVICE
    description: str | None = None
    duree_vie_annees: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_dates(self):
        """Vérifie que la date de fin de vie est après la date d'acquisition."""
        if self.date_fin_vie and self.date_fin_vie < self.date_acquisition:
            raise ValueError("La date de fin de vie doit être après la date d'acquisition")
        return self


class MaterielCreate(MaterielBase):
    """Création d'un matériel."""

    user_id: UUID | None = None
    equipe_id: UUID | None = None
    # Optionnel: si non fourni, sera calculé depuis les facteurs d'émission
    impact_fabrication_kg: Decimal | None = None
    consommation_kwh_annuelle: Decimal | None = None


class MaterielUpdate(BaseSchema):
    """Mise à jour d'un matériel."""

    type_materiel: TypeMateriel | None = None
    marque: str | None = Field(None, max_length=100)
    modele: str | None = Field(None, max_length=200)
    numero_serie: str | None = Field(None, max_length=100)
    date_acquisition: date | None = None
    date_fin_vie: date | None = None
    statut: StatutMateriel | None = None
    description: str | None = None
    duree_vie_annees: int | None = Field(None, ge=1, le=20)
    user_id: UUID | None = None
    equipe_id: UUID | None = None
    impact_fabrication_kg: Decimal | None = None
    consommation_kwh_annuelle: Decimal | None = None


class MaterielResponse(MaterielBase):
    """Réponse matériel."""

    id: UUID
    impact_fabrication_kg: Decimal
    consommation_kwh_annuelle: Decimal | None
    impact_usage_annuel_kg: Decimal
    user_id: UUID | None
    equipe_id: UUID | None
    created_at: datetime
    updated_at: datetime

    # Propriétés calculées
    impact_total_kg: Decimal | None = None
    impact_amorti_annuel_kg: Decimal | None = None


class MaterielWithUser(MaterielResponse):
    """Matériel avec informations utilisateur."""

    user: UserMinimal | None


class MaterielWithDetails(MaterielResponse):
    """Matériel avec toutes les relations."""

    user: UserMinimal | None
    equipe_name: str | None = None


# ==================== Schémas pour les statistiques ====================


class MaterielStats(BaseSchema):
    """Statistiques du matériel."""

    total_materiels: int
    total_impact_fabrication_kg: Decimal
    total_impact_usage_annuel_kg: Decimal
    total_impact_amorti_annuel_kg: Decimal
    materiels_par_type: dict[str, int]
    materiels_par_statut: dict[str, int]
    age_moyen_annees: float


class MaterielParType(BaseSchema):
    """Agrégation par type de matériel."""

    type_materiel: str
    nombre: int
    impact_fabrication_total: Decimal
    impact_usage_annuel_total: Decimal
    age_moyen: float


# ==================== Schémas pour les facteurs d'émission ====================


class FacteurMaterielResponse(BaseSchema):
    """Facteur d'émission pour un type de matériel."""

    type_materiel: str
    impact_fabrication_kg: Decimal
    consommation_kwh_annuelle: Decimal | None
    duree_vie_standard: int
