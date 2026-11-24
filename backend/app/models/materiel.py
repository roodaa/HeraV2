"""Modèle matériel informatique."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.equipe import Equipe


class TypeMateriel(str, Enum):
    """Types de matériel informatique."""

    ORDINATEUR_FIXE = "ordinateur_fixe"
    ORDINATEUR_PORTABLE = "ordinateur_portable"
    ECRAN = "ecran"
    SERVEUR = "serveur"
    IMPRIMANTE = "imprimante"
    SMARTPHONE = "smartphone"
    TABLETTE = "tablette"
    PERIPHERIQUE = "peripherique"
    RESEAU = "reseau"
    STOCKAGE = "stockage"
    AUTRE = "autre"


class StatutMateriel(str, Enum):
    """Statut du matériel."""

    EN_SERVICE = "en_service"
    EN_STOCK = "en_stock"
    EN_PANNE = "en_panne"
    EN_REPARATION = "en_reparation"
    MIS_AU_REBUT = "mis_au_rebut"


class Materiel(Base, TimestampMixin, SoftDeleteMixin):
    """Modèle matériel informatique."""

    __tablename__ = "materiels"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    type_materiel: Mapped[TypeMateriel] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    marque: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modele: Mapped[str | None] = mapped_column(String(200), nullable=True)
    numero_serie: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    date_acquisition: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin_vie: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[StatutMateriel] = mapped_column(
        String(20),
        default=StatutMateriel.EN_SERVICE,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Durée de vie prévue en années
    duree_vie_annees: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    # Impact carbone
    impact_fabrication_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        default=Decimal("0"),
        nullable=False,
    )
    # Consommation électrique annuelle en kWh
    consommation_kwh_annuelle: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    # Impact usage annuel en kgCO2
    impact_usage_annuel_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        default=Decimal("0"),
        nullable=False,
    )

    # Relations
    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user: Mapped["User | None"] = relationship("User")

    equipe_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipes.id", ondelete="SET NULL"),
        nullable=True,
    )
    equipe: Mapped["Equipe | None"] = relationship("Equipe")

    @property
    def impact_total_kg(self) -> Decimal:
        """Impact total amorti sur la durée de vie."""
        return self.impact_fabrication_kg + (
            self.impact_usage_annuel_kg * self.duree_vie_annees
        )

    @property
    def impact_amorti_annuel_kg(self) -> Decimal:
        """Impact annuel amorti (fabrication + usage)."""
        return (
            self.impact_fabrication_kg / self.duree_vie_annees
        ) + self.impact_usage_annuel_kg

    def __repr__(self) -> str:
        return f"<Materiel {self.type_materiel} - {self.marque} {self.modele}>"
