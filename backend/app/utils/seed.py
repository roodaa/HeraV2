"""Script de seed pour initialiser les données de base."""

import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.models import (
    FacteurEmissionElectricite,
    FacteurEmissionMateriel,
    FacteurEmissionTransport,
    Permission,
    Role,
    User,
)
from app.models.mission import ModeTransport
from app.models.materiel import TypeMateriel
from app.models.role import PermissionCodes, SystemRoles
from app.services.auth_service import AuthService


# ==================== Définition des permissions ====================

PERMISSIONS_DATA = [
    # Users
    {"code": PermissionCodes.USERS_READ, "name": "Voir les utilisateurs", "module": "users"},
    {"code": PermissionCodes.USERS_CREATE, "name": "Créer des utilisateurs", "module": "users"},
    {"code": PermissionCodes.USERS_UPDATE, "name": "Modifier des utilisateurs", "module": "users"},
    {"code": PermissionCodes.USERS_DELETE, "name": "Supprimer des utilisateurs", "module": "users"},
    {"code": PermissionCodes.USERS_MANAGE_ROLES, "name": "Gérer les rôles des utilisateurs", "module": "users"},
    # Roles
    {"code": PermissionCodes.ROLES_READ, "name": "Voir les rôles", "module": "roles"},
    {"code": PermissionCodes.ROLES_CREATE, "name": "Créer des rôles", "module": "roles"},
    {"code": PermissionCodes.ROLES_UPDATE, "name": "Modifier des rôles", "module": "roles"},
    {"code": PermissionCodes.ROLES_DELETE, "name": "Supprimer des rôles", "module": "roles"},
    # Missions
    {"code": PermissionCodes.MISSIONS_READ, "name": "Voir les missions", "module": "missions"},
    {"code": PermissionCodes.MISSIONS_CREATE, "name": "Créer des missions", "module": "missions"},
    {"code": PermissionCodes.MISSIONS_UPDATE, "name": "Modifier des missions", "module": "missions"},
    {"code": PermissionCodes.MISSIONS_DELETE, "name": "Supprimer des missions", "module": "missions"},
    {"code": PermissionCodes.MISSIONS_VALIDATE, "name": "Valider des missions", "module": "missions"},
    # Achats
    {"code": PermissionCodes.ACHATS_READ, "name": "Voir les achats", "module": "achats"},
    {"code": PermissionCodes.ACHATS_CREATE, "name": "Créer des achats", "module": "achats"},
    {"code": PermissionCodes.ACHATS_UPDATE, "name": "Modifier des achats", "module": "achats"},
    {"code": PermissionCodes.ACHATS_DELETE, "name": "Supprimer des achats", "module": "achats"},
    # Matériel
    {"code": PermissionCodes.MATERIEL_READ, "name": "Voir le matériel", "module": "materiel"},
    {"code": PermissionCodes.MATERIEL_CREATE, "name": "Créer du matériel", "module": "materiel"},
    {"code": PermissionCodes.MATERIEL_UPDATE, "name": "Modifier du matériel", "module": "materiel"},
    {"code": PermissionCodes.MATERIEL_DELETE, "name": "Supprimer du matériel", "module": "materiel"},
    # Équipes
    {"code": PermissionCodes.EQUIPES_READ, "name": "Voir les équipes", "module": "equipes"},
    {"code": PermissionCodes.EQUIPES_CREATE, "name": "Créer des équipes", "module": "equipes"},
    {"code": PermissionCodes.EQUIPES_UPDATE, "name": "Modifier des équipes", "module": "equipes"},
    {"code": PermissionCodes.EQUIPES_DELETE, "name": "Supprimer des équipes", "module": "equipes"},
    # Métriques
    {"code": PermissionCodes.METRIQUES_READ, "name": "Voir les métriques", "module": "metriques"},
    {"code": PermissionCodes.METRIQUES_CREATE, "name": "Créer des métriques", "module": "metriques"},
    {"code": PermissionCodes.METRIQUES_UPDATE, "name": "Modifier des métriques", "module": "metriques"},
    # Dashboard
    {"code": PermissionCodes.DASHBOARD_VIEW, "name": "Voir les tableaux de bord", "module": "dashboard"},
    {"code": PermissionCodes.DASHBOARD_EXPORT, "name": "Exporter les données", "module": "dashboard"},
    # Admin
    {"code": PermissionCodes.ADMIN_SETTINGS, "name": "Gérer les paramètres", "module": "admin"},
    {"code": PermissionCodes.ADMIN_AUDIT, "name": "Voir les logs d'audit", "module": "admin"},
    {"code": PermissionCodes.ADMIN_ETL, "name": "Gérer les ETL", "module": "admin"},
]


# ==================== Définition des rôles ====================

ROLES_DATA = [
    {
        "code": SystemRoles.ADMIN,
        "name": "Administrateur",
        "description": "Accès complet à toutes les fonctionnalités",
        "is_system": True,
        "permissions": "all",
    },
    {
        "code": SystemRoles.TEAM_BGES,
        "name": "Team BGES",
        "description": "Équipe Bilan GES - Consultation des données, dashboards, rapports et gestion des métriques",
        "is_system": True,
        "permissions": [
            # Lecture seule sur les données
            PermissionCodes.MISSIONS_READ,
            PermissionCodes.ACHATS_READ,
            PermissionCodes.MATERIEL_READ,
            PermissionCodes.EQUIPES_READ,
            # Gestion des métriques (leur domaine)
            PermissionCodes.METRIQUES_READ,
            PermissionCodes.METRIQUES_CREATE,
            PermissionCodes.METRIQUES_UPDATE,
            # Dashboards et exports
            PermissionCodes.DASHBOARD_VIEW,
            PermissionCodes.DASHBOARD_EXPORT,
        ],
    },
    {
        "code": SystemRoles.GESTIONNAIRE,
        "name": "Gestionnaire",
        "description": "Gestion complète des missions et achats",
        "is_system": True,
        "permissions": [
            # Missions - CRUD complet + validation
            PermissionCodes.MISSIONS_READ,
            PermissionCodes.MISSIONS_CREATE,
            PermissionCodes.MISSIONS_UPDATE,
            PermissionCodes.MISSIONS_DELETE,
            PermissionCodes.MISSIONS_VALIDATE,
            # Achats - CRUD complet
            PermissionCodes.ACHATS_READ,
            PermissionCodes.ACHATS_CREATE,
            PermissionCodes.ACHATS_UPDATE,
            PermissionCodes.ACHATS_DELETE,
            # Équipes - lecture
            PermissionCodes.EQUIPES_READ,
        ],
    },
    {
        "code": SystemRoles.RESP_INFORMATIQUE,
        "name": "Responsable Informatique",
        "description": "Gestion complète du matériel informatique",
        "is_system": True,
        "permissions": [
            # Matériel - CRUD complet
            PermissionCodes.MATERIEL_READ,
            PermissionCodes.MATERIEL_CREATE,
            PermissionCodes.MATERIEL_UPDATE,
            PermissionCodes.MATERIEL_DELETE,
            # Équipes - lecture
            PermissionCodes.EQUIPES_READ,
        ],
    },
    {
        "code": SystemRoles.SECRETARIAT,
        "name": "Secrétariat",
        "description": "Saisie des missions et achats",
        "is_system": True,
        "permissions": [
            # Missions - création et lecture
            PermissionCodes.MISSIONS_READ,
            PermissionCodes.MISSIONS_CREATE,
            # Achats - création et lecture
            PermissionCodes.ACHATS_READ,
            PermissionCodes.ACHATS_CREATE,
            # Équipes - lecture
            PermissionCodes.EQUIPES_READ,
        ],
    },
    {
        "code": SystemRoles.MISSIONNAIRE,
        "name": "Missionnaire",
        "description": "Déclaration de ses propres missions",
        "is_system": True,
        "permissions": [
            # Missions - création et lecture (filtré sur ses propres missions côté API)
            PermissionCodes.MISSIONS_READ,
            PermissionCodes.MISSIONS_CREATE,
        ],
    },
    {
        "code": SystemRoles.EXTERIEUR,
        "name": "Extérieur",
        "description": "Accès externe limité",
        "is_system": True,
        "permissions": [],  # Aucune permission par défaut
    },
]


# ==================== Facteurs d'émission transport (ADEME) ====================

FACTEURS_TRANSPORT = [
    {"mode": ModeTransport.AVION.value, "facteur": Decimal("0.259"), "description": "Avion court-courrier (< 1000 km)"},
    {"mode": ModeTransport.AVION_AFFAIRES.value, "facteur": Decimal("0.518"), "description": "Avion classe affaires"},
    {"mode": ModeTransport.TRAIN.value, "facteur": Decimal("0.0037"), "description": "Train (moyenne France)"},
    {"mode": ModeTransport.TGV.value, "facteur": Decimal("0.00293"), "description": "TGV"},
    {"mode": ModeTransport.TER.value, "facteur": Decimal("0.0298"), "description": "TER"},
    {"mode": ModeTransport.VOITURE.value, "facteur": Decimal("0.193"), "description": "Voiture thermique moyenne"},
    {"mode": ModeTransport.VOITURE_ELECTRIQUE.value, "facteur": Decimal("0.020"), "description": "Voiture électrique"},
    {"mode": ModeTransport.COVOITURAGE.value, "facteur": Decimal("0.064"), "description": "Covoiturage (3 personnes)"},
    {"mode": ModeTransport.BUS.value, "facteur": Decimal("0.104"), "description": "Autocar longue distance"},
    {"mode": ModeTransport.METRO.value, "facteur": Decimal("0.0025"), "description": "Métro/Tramway"},
    {"mode": ModeTransport.VELO.value, "facteur": Decimal("0"), "description": "Vélo"},
    {"mode": ModeTransport.MARCHE.value, "facteur": Decimal("0"), "description": "Marche à pied"},
]


# ==================== Facteurs d'émission matériel (ADEME) ====================

FACTEURS_MATERIEL = [
    {"type": TypeMateriel.ORDINATEUR_FIXE.value, "fabrication": Decimal("350"), "conso": Decimal("200"), "duree": 5},
    {"type": TypeMateriel.ORDINATEUR_PORTABLE.value, "fabrication": Decimal("280"), "conso": Decimal("50"), "duree": 5},
    {"type": TypeMateriel.ECRAN.value, "fabrication": Decimal("350"), "conso": Decimal("40"), "duree": 7},
    {"type": TypeMateriel.SERVEUR.value, "fabrication": Decimal("1200"), "conso": Decimal("1500"), "duree": 6},
    {"type": TypeMateriel.IMPRIMANTE.value, "fabrication": Decimal("80"), "conso": Decimal("30"), "duree": 5},
    {"type": TypeMateriel.SMARTPHONE.value, "fabrication": Decimal("70"), "conso": Decimal("5"), "duree": 3},
    {"type": TypeMateriel.TABLETTE.value, "fabrication": Decimal("100"), "conso": Decimal("10"), "duree": 4},
]


async def seed_permissions(db: AsyncSession) -> dict[str, Permission]:
    """Crée les permissions de base."""
    permissions = {}

    for perm_data in PERMISSIONS_DATA:
        stmt = select(Permission).where(Permission.code == perm_data["code"])
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            permissions[perm_data["code"]] = existing
        else:
            perm = Permission(**perm_data)
            db.add(perm)
            permissions[perm_data["code"]] = perm

    await db.commit()
    print(f"✅ {len(permissions)} permissions créées/vérifiées")
    return permissions


async def seed_roles(db: AsyncSession, permissions: dict[str, Permission]) -> dict[str, Role]:
    """Crée les rôles système."""
    roles = {}

    for role_data in ROLES_DATA:
        stmt = select(Role).where(Role.code == role_data["code"])
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            roles[role_data["code"]] = existing
            continue

        # Détermine les permissions
        if role_data["permissions"] == "all":
            role_permissions = list(permissions.values())
        else:
            role_permissions = [
                permissions[code] for code in role_data["permissions"] if code in permissions
            ]

        role = Role(
            code=role_data["code"],
            name=role_data["name"],
            description=role_data["description"],
            is_system=role_data["is_system"],
            permissions=role_permissions,
        )
        db.add(role)
        roles[role_data["code"]] = role

    await db.commit()
    print(f"✅ {len(roles)} rôles créés/vérifiés")
    return roles


async def seed_admin_user(db: AsyncSession, roles: dict[str, Role]) -> None:
    """Crée un utilisateur admin par défaut."""
    stmt = select(User).where(User.email == "admin@hera.local")
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        print("ℹ️  Utilisateur admin déjà existant")
        return

    admin = User(
        email="admin@hera.local",
        first_name="Admin",
        last_name="HERA",
        hashed_password=AuthService.hash_password("admin123"),
        auth_provider="local",
        is_active=True,
        is_superuser=True,
        roles=[roles[SystemRoles.ADMIN]],
    )
    db.add(admin)
    await db.commit()
    print("✅ Utilisateur admin créé (email: admin@hera.local, password: admin123)")


async def seed_facteurs_transport(db: AsyncSession) -> None:
    """Crée les facteurs d'émission transport."""
    count = 0
    for facteur_data in FACTEURS_TRANSPORT:
        stmt = select(FacteurEmissionTransport).where(
            FacteurEmissionTransport.mode_transport == facteur_data["mode"]
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if not existing:
            facteur = FacteurEmissionTransport(
                mode_transport=facteur_data["mode"],
                facteur_kg_par_km=facteur_data["facteur"],
                description=facteur_data["description"],
                source="ADEME Base Carbone 2024",
                date_debut=date(2024, 1, 1),
            )
            db.add(facteur)
            count += 1

    await db.commit()
    print(f"✅ {count} facteurs d'émission transport créés")


async def seed_facteurs_materiel(db: AsyncSession) -> None:
    """Crée les facteurs d'émission matériel."""
    count = 0
    for facteur_data in FACTEURS_MATERIEL:
        stmt = select(FacteurEmissionMateriel).where(
            FacteurEmissionMateriel.type_materiel == facteur_data["type"]
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if not existing:
            facteur = FacteurEmissionMateriel(
                type_materiel=facteur_data["type"],
                impact_fabrication_kg=facteur_data["fabrication"],
                consommation_kwh_annuelle=facteur_data["conso"],
                duree_vie_standard=facteur_data["duree"],
                source="ADEME Base Carbone 2024",
                date_debut=date(2024, 1, 1),
            )
            db.add(facteur)
            count += 1

    await db.commit()
    print(f"✅ {count} facteurs d'émission matériel créés")


async def seed_facteur_electricite(db: AsyncSession) -> None:
    """Crée le facteur d'émission électricité France."""
    stmt = select(FacteurEmissionElectricite).where(
        FacteurEmissionElectricite.pays == "FR"
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if not existing:
        facteur = FacteurEmissionElectricite(
            pays="FR",
            facteur_kg_par_kwh=Decimal("0.0569"),  # Mix électrique France 2024
            source="ADEME Base Carbone 2024",
            date_debut=date(2024, 1, 1),
        )
        db.add(facteur)
        await db.commit()
        print("✅ Facteur d'émission électricité France créé")


async def run_seed() -> None:
    """Exécute tous les seeds."""
    print("\n🌱 Initialisation des données de base HERA V2...\n")

    async with AsyncSessionLocal() as db:
        permissions = await seed_permissions(db)
        roles = await seed_roles(db, permissions)
        await seed_admin_user(db, roles)
        await seed_facteurs_transport(db)
        await seed_facteurs_materiel(db)
        await seed_facteur_electricite(db)

    print("\n✨ Initialisation terminée avec succès!\n")


if __name__ == "__main__":
    asyncio.run(run_seed())
