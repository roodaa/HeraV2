"""Configuration des tests et fixtures pytest."""

import asyncio
from datetime import date
from decimal import Decimal
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config.database import Base, get_db
from app.main import app
from app.models import (
    FacteurEmissionMateriel,
    FacteurEmissionTransport,
    FacteurEmissionElectricite,
    Permission,
    Role,
    User,
)
from app.models.mission import ModeTransport
from app.models.materiel import TypeMateriel
from app.services.auth_service import AuthService

# URL de la base de données de test (SQLite en mémoire pour les tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Crée une event loop pour toute la session de tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Crée un moteur de base de données de test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ne supporte pas les schémas, on adapte
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Crée une session de base de données de test."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Crée un client HTTP de test."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ==================== Fixtures de données ====================


@pytest_asyncio.fixture
async def test_permissions(db_session: AsyncSession) -> list[Permission]:
    """Crée les permissions de test."""
    permissions_data = [
        # Users
        {"code": "users:read", "name": "Lire utilisateurs", "module": "users"},
        {"code": "users:create", "name": "Créer utilisateurs", "module": "users"},
        {"code": "users:update", "name": "Modifier utilisateurs", "module": "users"},
        {"code": "users:delete", "name": "Supprimer utilisateurs", "module": "users"},
        {"code": "users:manage_roles", "name": "Gérer rôles", "module": "users"},
        # Roles
        {"code": "roles:read", "name": "Lire rôles", "module": "roles"},
        {"code": "roles:create", "name": "Créer rôles", "module": "roles"},
        {"code": "roles:update", "name": "Modifier rôles", "module": "roles"},
        {"code": "roles:delete", "name": "Supprimer rôles", "module": "roles"},
        # Equipes
        {"code": "equipes:read", "name": "Lire équipes", "module": "equipes"},
        {"code": "equipes:create", "name": "Créer équipes", "module": "equipes"},
        {"code": "equipes:update", "name": "Modifier équipes", "module": "equipes"},
        {"code": "equipes:delete", "name": "Supprimer équipes", "module": "equipes"},
        # Missions
        {"code": "missions:read", "name": "Lire missions", "module": "missions"},
        {"code": "missions:create", "name": "Créer missions", "module": "missions"},
        {"code": "missions:update", "name": "Modifier missions", "module": "missions"},
        {"code": "missions:delete", "name": "Supprimer missions", "module": "missions"},
        {"code": "missions:validate", "name": "Valider missions", "module": "missions"},
        # Achats
        {"code": "achats:read", "name": "Lire achats", "module": "achats"},
        {"code": "achats:create", "name": "Créer achats", "module": "achats"},
        {"code": "achats:update", "name": "Modifier achats", "module": "achats"},
        {"code": "achats:delete", "name": "Supprimer achats", "module": "achats"},
        # Materiel
        {"code": "materiel:read", "name": "Lire matériel", "module": "materiel"},
        {"code": "materiel:create", "name": "Créer matériel", "module": "materiel"},
        {"code": "materiel:update", "name": "Modifier matériel", "module": "materiel"},
        {"code": "materiel:delete", "name": "Supprimer matériel", "module": "materiel"},
    ]

    permissions = []
    for perm_data in permissions_data:
        perm = Permission(**perm_data)
        db_session.add(perm)
        permissions.append(perm)

    await db_session.commit()
    return permissions


@pytest_asyncio.fixture
async def admin_role(db_session: AsyncSession, test_permissions: list[Permission]) -> Role:
    """Crée un rôle admin avec toutes les permissions."""
    role = Role(
        code="admin",
        name="Administrateur",
        description="Accès complet",
        is_system=True,
        permissions=test_permissions,
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    return role


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, admin_role: Role) -> User:
    """Crée un utilisateur admin de test."""
    user = User(
        email="admin@test.local",
        first_name="Admin",
        last_name="Test",
        hashed_password=AuthService.hash_password("password123"),
        auth_provider="local",
        is_active=True,
        is_superuser=True,
        roles=[admin_role],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur régulier sans permissions."""
    user = User(
        email="user@test.local",
        first_name="User",
        last_name="Test",
        hashed_password=AuthService.hash_password("password123"),
        auth_provider="local",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(admin_user: User) -> dict[str, str]:
    """Génère les headers d'authentification pour l'admin."""
    token = AuthService.create_access_token(str(admin_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_auth_headers(regular_user: User) -> dict[str, str]:
    """Génère les headers d'authentification pour un utilisateur régulier."""
    token = AuthService.create_access_token(str(regular_user.id))
    return {"Authorization": f"Bearer {token}"}


# ==================== Fixtures facteurs d'émission ====================


@pytest_asyncio.fixture
async def facteurs_transport(db_session: AsyncSession) -> list[FacteurEmissionTransport]:
    """Crée les facteurs d'émission transport de test."""
    facteurs_data = [
        {"mode": ModeTransport.AVION.value, "facteur": Decimal("0.259")},
        {"mode": ModeTransport.TRAIN.value, "facteur": Decimal("0.0037")},
        {"mode": ModeTransport.TGV.value, "facteur": Decimal("0.00293")},
        {"mode": ModeTransport.VOITURE.value, "facteur": Decimal("0.193")},
        {"mode": ModeTransport.VELO.value, "facteur": Decimal("0")},
    ]

    facteurs = []
    for f in facteurs_data:
        facteur = FacteurEmissionTransport(
            mode_transport=f["mode"],
            facteur_kg_par_km=f["facteur"],
            source="Test ADEME",
            date_debut=date(2024, 1, 1),
            is_active=True,
        )
        db_session.add(facteur)
        facteurs.append(facteur)

    await db_session.commit()
    return facteurs


@pytest_asyncio.fixture
async def facteurs_materiel(db_session: AsyncSession) -> list[FacteurEmissionMateriel]:
    """Crée les facteurs d'émission matériel de test."""
    facteurs_data = [
        {"type": TypeMateriel.ORDINATEUR_PORTABLE.value, "fab": Decimal("280"), "conso": Decimal("50"), "duree": 5},
        {"type": TypeMateriel.ECRAN.value, "fab": Decimal("350"), "conso": Decimal("40"), "duree": 7},
        {"type": TypeMateriel.SERVEUR.value, "fab": Decimal("1200"), "conso": Decimal("1500"), "duree": 6},
    ]

    facteurs = []
    for f in facteurs_data:
        facteur = FacteurEmissionMateriel(
            type_materiel=f["type"],
            impact_fabrication_kg=f["fab"],
            consommation_kwh_annuelle=f["conso"],
            duree_vie_standard=f["duree"],
            source="Test ADEME",
            date_debut=date(2024, 1, 1),
            is_active=True,
        )
        db_session.add(facteur)
        facteurs.append(facteur)

    await db_session.commit()
    return facteurs


@pytest_asyncio.fixture
async def facteur_electricite(db_session: AsyncSession) -> FacteurEmissionElectricite:
    """Crée le facteur d'émission électricité de test."""
    facteur = FacteurEmissionElectricite(
        pays="FR",
        facteur_kg_par_kwh=Decimal("0.0569"),
        source="Test ADEME",
        date_debut=date(2024, 1, 1),
        is_active=True,
    )
    db_session.add(facteur)
    await db_session.commit()
    return facteur
