"""Routes API pour HERA V2."""

from fastapi import APIRouter

from app.routes import achats, auth, equipes, materiel, missions, permissions, roles, users

api_router = APIRouter()

# Inclusion des routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentification"])
api_router.include_router(users.router, prefix="/users", tags=["Utilisateurs"])
api_router.include_router(roles.router, prefix="/roles", tags=["Rôles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(equipes.router, prefix="/equipes", tags=["Équipes"])
api_router.include_router(missions.router, prefix="/missions", tags=["Missions"])
api_router.include_router(achats.router, prefix="/achats", tags=["Achats"])
api_router.include_router(materiel.router, prefix="/materiel", tags=["Matériel"])
