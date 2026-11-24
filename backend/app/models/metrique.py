"""Modèle métriques laboratoire."""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.equipe import Equipe


class Metrique(Base, TimestampMixin):
    """Modèle métriques annuelles du laboratoire/équipe."""

    __tablename__ = "metriques"
    __table_args__ = (
        UniqueConstraint("annee", "equipe_id", name="uq_metrique_annee_equipe"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    annee: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Indicateurs RH
    effectif_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etp: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )  # Équivalent Temps Plein

    # Indicateurs de production scientifique
    nb_publications: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nb_theses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nb_brevets: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relations (si null = métriques globales du labo)
    equipe_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipes.id", ondelete="CASCADE"),
        nullable=True,
    )
    equipe: Mapped["Equipe | None"] = relationship("Equipe")

    def __repr__(self) -> str:
        equipe_str = self.equipe.code if self.equipe else "Global"
        return f"<Metrique {self.annee} - {equipe_str}>"
