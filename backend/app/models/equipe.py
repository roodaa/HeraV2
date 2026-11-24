"""Modèle équipe."""

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Equipe(Base, TimestampMixin, SoftDeleteMixin):
    """Modèle équipe/unité organisationnelle."""

    __tablename__ = "equipes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    members: Mapped[list["User"]] = relationship(
        "User",
        back_populates="equipe",
    )

    def __repr__(self) -> str:
        return f"<Equipe {self.code}>"
