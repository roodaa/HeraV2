"""Routes d'authentification."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.settings import get_settings
from app.middleware.auth import CurrentUser
from app.schemas import (
    CurrentUser as CurrentUserSchema,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Authentification locale avec email/mot de passe.

    Retourne une paire de tokens JWT (access + refresh).
    """
    if settings.auth_provider != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"L'authentification locale n'est pas activée. Utilisez {settings.auth_provider}.",
        )

    auth_service = AuthService(db)
    user = await auth_service.authenticate_local(
        credentials.email, credentials.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    await auth_service.update_last_login(user)
    return auth_service.create_tokens(str(user.id))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Rafraîchit les tokens JWT avec un refresh token valide.
    """
    auth_service = AuthService(db)

    # Décode le refresh token
    payload = auth_service.decode_token(request.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de rafraîchissement invalide ou expiré",
        )

    if payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Type de token invalide",
        )

    # Vérifie que l'utilisateur existe toujours
    user = await auth_service.get_user_by_id(payload.sub)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé ou inactif",
        )

    return auth_service.create_tokens(str(user.id))


@router.post("/logout")
async def logout():
    """
    Déconnexion (côté client, invalide le token localement).

    Note: Pour une vraie invalidation côté serveur, il faudrait
    implémenter une liste noire de tokens (blacklist).
    """
    return {"message": "Déconnexion réussie"}


@router.get("/me", response_model=CurrentUserSchema)
async def get_me(user: CurrentUser):
    """
    Retourne les informations de l'utilisateur connecté.
    """
    # Collecte les permissions de l'utilisateur
    permissions = set()
    roles = []
    for role in user.roles:
        roles.append(role.code)
        for permission in role.permissions:
            permissions.add(permission.code)

    return CurrentUserSchema(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        is_superuser=user.is_superuser,
        auth_provider=user.auth_provider,
        permissions=list(permissions),
        roles=roles,
    )


# ==================== Routes SAML (Renater/Shibboleth) ====================


@router.get("/saml/login")
async def saml_login(request: Request):
    """
    Initie le processus de connexion SAML.
    Redirige vers l'IdP Renater.
    """
    if not settings.saml_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'authentification SAML n'est pas activée",
        )

    # TODO: Implémenter avec python3-saml
    # - Charger la configuration SAML
    # - Générer la requête AuthnRequest
    # - Retourner l'URL de redirection vers l'IdP

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentification SAML non encore implémentée",
    )


@router.post("/saml/callback")
async def saml_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Callback après authentification SAML.
    Traite la réponse de l'IdP et crée/récupère l'utilisateur.
    """
    if not settings.saml_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'authentification SAML n'est pas activée",
        )

    # TODO: Implémenter avec python3-saml
    # - Valider la réponse SAML
    # - Extraire les attributs utilisateur
    # - Créer/récupérer l'utilisateur
    # - Retourner les tokens

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentification SAML non encore implémentée",
    )


# ==================== Routes OIDC ====================


@router.get("/oidc/login")
async def oidc_login():
    """
    Initie le processus de connexion OIDC.
    Redirige vers le provider OIDC.
    """
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'authentification OIDC n'est pas activée",
        )

    # TODO: Implémenter
    # - Générer le state
    # - Construire l'URL d'autorisation
    # - Retourner l'URL de redirection

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentification OIDC non encore implémentée",
    )


@router.get("/oidc/callback")
async def oidc_callback(
    code: str,
    state: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Callback après authentification OIDC.
    Échange le code contre des tokens et crée/récupère l'utilisateur.
    """
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'authentification OIDC n'est pas activée",
        )

    # TODO: Implémenter
    # - Valider le state
    # - Échanger le code contre des tokens
    # - Récupérer les informations utilisateur
    # - Créer/récupérer l'utilisateur
    # - Retourner les tokens

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentification OIDC non encore implémentée",
    )
