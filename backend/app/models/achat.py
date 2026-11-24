"""Modèle achat."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.equipe import Equipe


class Achat(Base, TimestampMixin, SoftDeleteMixin):
    """Modèle achat/dépense."""

    __tablename__ = "achats"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    date_achat: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    montant_euros: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    code_nacres: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )
    categorie: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Impact carbone calculé
    impact_co2_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        default=Decimal("0"),
        nullable=False,
    )
    # Facteur utilisé pour le calcul (kgCO2/€)
    facteur_emission: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )

    # Relations
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user: Mapped["User"] = relationship("User")

    equipe_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipes.id", ondelete="SET NULL"),
        nullable=True,
    )
    equipe: Mapped["Equipe | None"] = relationship("Equipe")

    def __repr__(self) -> str:
        return f"<Achat {self.description[:30]} - {self.montant_euros}€>"
