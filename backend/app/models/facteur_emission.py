"""Modèle facteurs d'émission CO2."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base
from app.models.base import TimestampMixin


class FacteurEmissionTransport(Base, TimestampMixin):
    """Facteurs d'émission CO2 pour les modes de transport."""

    __tablename__ = "facteurs_emission_transport"
    __table_args__ = (
        UniqueConstraint(
            "mode_transport", "date_debut", name="uq_facteur_transport_mode_date"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    mode_transport: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    # Facteur en kgCO2/km
    facteur_kg_par_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(100),
        default="ADEME",
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<FacteurTransport {self.mode_transport}: {self.facteur_kg_par_km} kgCO2/km>"


class FacteurEmissionNacres(Base, TimestampMixin):
    """Facteurs d'émission CO2 par code NACRES (achats)."""

    __tablename__ = "facteurs_emission_nacres"
    __table_args__ = (
        UniqueConstraint("code_nacres", "date_debut", name="uq_facteur_nacres_code_date"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code_nacres: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    # Facteur en kgCO2/€
    facteur_kg_par_euro: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(100),
        default="ADEME",
        nullable=False,
    )
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<FacteurNacres {self.code_nacres}: {self.facteur_kg_par_euro} kgCO2/€>"


class FacteurEmissionMateriel(Base, TimestampMixin):
    """Facteurs d'émission CO2 pour le matériel informatique."""

    __tablename__ = "facteurs_emission_materiel"
    __table_args__ = (
        UniqueConstraint(
            "type_materiel", "date_debut", name="uq_facteur_materiel_type_date"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    type_materiel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    # Impact fabrication en kgCO2
    impact_fabrication_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
    )
    # Consommation électrique moyenne en kWh/an
    consommation_kwh_annuelle: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    # Durée de vie standard en années
    duree_vie_standard: Mapped[int] = mapped_column(default=5, nullable=False)
    source: Mapped[str] = mapped_column(
        String(100),
        default="ADEME",
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<FacteurMateriel {self.type_materiel}: {self.impact_fabrication_kg} kgCO2>"


# Facteur d'émission de l'électricité (pour le calcul de l'impact usage)
class FacteurEmissionElectricite(Base, TimestampMixin):
    """Facteur d'émission de l'électricité."""

    __tablename__ = "facteurs_emission_electricite"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    pays: Mapped[str] = mapped_column(
        String(10),
        default="FR",
        nullable=False,
        index=True,
    )
    # Facteur en kgCO2/kWh
    facteur_kg_par_kwh: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(100),
        default="ADEME",
        nullable=False,
    )
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<FacteurElectricite {self.pays}: {self.facteur_kg_par_kwh} kgCO2/kWh>"
