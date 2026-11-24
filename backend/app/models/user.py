"""Modèles utilisateur."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Table, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.equipe import Equipe


# Table d'association User <-> Role (Many-to-Many)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base, TimestampMixin, SoftDeleteMixin):
    """Modèle utilisateur."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # Nullable car auth externe possible (SAML/OIDC)
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Identifiant externe (Renater eduPersonPrincipalName, OIDC sub, etc.)
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    # Provider d'authentification utilisé
    auth_provider: Mapped[str] = mapped_column(
        String(50),
        default="local",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relations
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )

    equipe_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipes.id", ondelete="SET NULL"),
        nullable=True,
    )
    equipe: Mapped["Equipe | None"] = relationship(
        "Equipe",
        back_populates="members",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, permission_code: str) -> bool:
        """Vérifie si l'utilisateur a une permission donnée."""
        if self.is_superuser:
            return True
        for role in self.roles:
            for permission in role.permissions:
                if permission.code == permission_code:
                    return True
        return False

    def __repr__(self) -> str:
        return f"<User {self.email}>"
