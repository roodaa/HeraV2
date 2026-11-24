"""Middleware d'authentification et d'autorisation."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models import User
from app.services.auth_service import AuthService

# Schéma de sécurité Bearer
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Dépendance pour obtenir l'utilisateur courant à partir du token JWT.

    Raises:
        HTTPException 401: Token invalide ou expiré
        HTTPException 401: Utilisateur non trouvé ou inactif
    """
    token = credentials.credentials
    auth_service = AuthService(db)

    # Décode le token
    payload = auth_service.decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifie que c'est un token d'accès
    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Type de token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Récupère l'utilisateur
    user = await auth_service.get_user_by_id(payload.sub)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte utilisateur désactivé",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# Type alias pour simplifier l'utilisation dans les routes
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission_code: str):
    """
    Dépendance factory pour vérifier une permission.

    Usage:
        @router.get("/admin")
        async def admin_route(user: CurrentUser = Depends(require_permission("admin:settings"))):
            ...
    """

    async def check_permission(user: CurrentUser) -> User:
        if not user.has_permission(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise: {permission_code}",
            )
        return user

    return check_permission


def require_superuser(user: CurrentUser) -> User:
    """
    Dépendance pour vérifier que l'utilisateur est superuser.

    Usage:
        @router.delete("/users/{id}")
        async def delete_user(user: User = Depends(require_superuser)):
            ...
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return user


class PermissionChecker:
    """
    Classe pour vérifier les permissions de manière plus flexible.

    Usage:
        permission_checker = PermissionChecker(["users:read", "users:create"])

        @router.get("/users")
        async def list_users(user: User = Depends(permission_checker)):
            ...
    """

    def __init__(self, required_permissions: list[str], require_all: bool = False):
        """
        Args:
            required_permissions: Liste des permissions à vérifier
            require_all: Si True, toutes les permissions sont requises.
                        Si False, une seule suffit.
        """
        self.required_permissions = required_permissions
        self.require_all = require_all

    async def __call__(self, user: CurrentUser) -> User:
        if user.is_superuser:
            return user

        if self.require_all:
            # Toutes les permissions sont requises
            for permission in self.required_permissions:
                if not user.has_permission(permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission requise: {permission}",
                    )
        else:
            # Au moins une permission suffit
            has_any = any(
                user.has_permission(p) for p in self.required_permissions
            )
            if not has_any:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Une des permissions suivantes est requise: {', '.join(self.required_permissions)}",
                )

        return user
