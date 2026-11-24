"""Modèles mission et étape."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ModeTransport(str, Enum):
    """Modes de transport disponibles."""

    AVION = "avion"
    AVION_AFFAIRES = "avion_affaires"
    TRAIN = "train"
    TGV = "tgv"
    TER = "ter"
    VOITURE = "voiture"
    VOITURE_ELECTRIQUE = "voiture_electrique"
    COVOITURAGE = "covoiturage"
    BUS = "bus"
    METRO = "metro"
    VELO = "velo"
    MARCHE = "marche"
    AUTRE = "autre"


class TypeMission(str, Enum):
    """Type de mission."""

    ALLER_SIMPLE = "aller_simple"
    ALLER_RETOUR = "aller_retour"


class StatutMission(str, Enum):
    """Statut de la mission."""

    BROUILLON = "brouillon"
    SOUMISE = "soumise"
    VALIDEE = "validee"
    REJETEE = "rejetee"


class Mission(Base, TimestampMixin, SoftDeleteMixin):
    """Modèle mission/déplacement."""

    __tablename__ = "missions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    date_depart: Mapped[date] = mapped_column(Date, nullable=False)
    date_retour: Mapped[date | None] = mapped_column(Date, nullable=True)
    motif: Mapped[str] = mapped_column(String(500), nullable=False)
    type_mission: Mapped[TypeMission] = mapped_column(
        String(20),
        default=TypeMission.ALLER_RETOUR,
        nullable=False,
    )
    statut: Mapped[StatutMission] = mapped_column(
        String(20),
        default=StatutMission.BROUILLON,
        nullable=False,
    )
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Totaux calculés
    distance_totale_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
        nullable=False,
    )
    impact_co2_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        default=Decimal("0"),
        nullable=False,
    )

    # Relations
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user: Mapped["User"] = relationship("User")

    etapes: Mapped[list["Etape"]] = relationship(
        "Etape",
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="Etape.ordre",
    )

    def __repr__(self) -> str:
        return f"<Mission {self.id} - {self.motif[:30]}>"


class Etape(Base, TimestampMixin):
    """Modèle étape d'une mission."""

    __tablename__ = "etapes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    ordre: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ville_depart: Mapped[str] = mapped_column(String(255), nullable=False)
    ville_arrivee: Mapped[str] = mapped_column(String(255), nullable=False)
    mode_transport: Mapped[ModeTransport] = mapped_column(
        String(30),
        nullable=False,
    )
    distance_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    # True si la distance a été calculée automatiquement
    distance_auto: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    impact_co2_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
    )

    # Optionnel: classe de transport pour l'avion
    classe_transport: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Relations
    mission_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mission: Mapped["Mission"] = relationship("Mission", back_populates="etapes")

    def __repr__(self) -> str:
        return f"<Etape {self.ville_depart} -> {self.ville_arrivee}>"
