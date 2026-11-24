"""Modèles rôles et permissions."""

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


# Table d'association Role <-> Permission (Many-to-Many)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base, TimestampMixin):
    """Modèle permission."""

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # Ex: "users", "missions", "achats", etc.

    # Relations
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return f"<Permission {self.code}>"


class Role(Base, TimestampMixin):
    """Modèle rôle."""

    __tablename__ = "roles"

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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )  # Rôles système non modifiables

    # Relations
    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
    )

    def __repr__(self) -> str:
        return f"<Role {self.code}>"


# Constantes pour les rôles système
class SystemRoles:
    """Codes des rôles système."""

    ADMIN = "admin"
    TEAM_BGES = "team_bges"
    GESTIONNAIRE = "gestionnaire"
    RESP_INFORMATIQUE = "resp_informatique"
    SECRETARIAT = "secretariat"
    MISSIONNAIRE = "missionnaire"
    EXTERIEUR = "exterieur"


# Constantes pour les permissions par module
class PermissionCodes:
    """Codes des permissions."""

    # Users
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    USERS_MANAGE_ROLES = "users:manage_roles"

    # Roles
    ROLES_READ = "roles:read"
    ROLES_CREATE = "roles:create"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"

    # Missions
    MISSIONS_READ = "missions:read"
    MISSIONS_CREATE = "missions:create"
    MISSIONS_UPDATE = "missions:update"
    MISSIONS_DELETE = "missions:delete"
    MISSIONS_VALIDATE = "missions:validate"

    # Achats
    ACHATS_READ = "achats:read"
    ACHATS_CREATE = "achats:create"
    ACHATS_UPDATE = "achats:update"
    ACHATS_DELETE = "achats:delete"

    # Matériel
    MATERIEL_READ = "materiel:read"
    MATERIEL_CREATE = "materiel:create"
    MATERIEL_UPDATE = "materiel:update"
    MATERIEL_DELETE = "materiel:delete"

    # Équipes
    EQUIPES_READ = "equipes:read"
    EQUIPES_CREATE = "equipes:create"
    EQUIPES_UPDATE = "equipes:update"
    EQUIPES_DELETE = "equipes:delete"

    # Métriques
    METRIQUES_READ = "metriques:read"
    METRIQUES_CREATE = "metriques:create"
    METRIQUES_UPDATE = "metriques:update"

    # Dashboard
    DASHBOARD_VIEW = "dashboard:view"
    DASHBOARD_EXPORT = "dashboard:export"

    # Admin
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_ETL = "admin:etl"
