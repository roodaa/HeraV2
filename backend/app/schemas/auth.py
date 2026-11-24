"""Schémas authentification."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class LoginRequest(BaseSchema):
    """Requête de connexion (auth locale)."""

    email: EmailStr
    password: str


class TokenResponse(BaseSchema):
    """Réponse avec tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes


class RefreshTokenRequest(BaseSchema):
    """Requête de rafraîchissement de token."""

    refresh_token: str


class TokenPayload(BaseSchema):
    """Payload du token JWT."""

    sub: str  # user_id
    exp: datetime
    iat: datetime
    type: str  # "access" ou "refresh"


class SAMLLoginResponse(BaseSchema):
    """Réponse pour initier le login SAML."""

    redirect_url: str


class SAMLCallbackRequest(BaseSchema):
    """Callback SAML après authentification."""

    saml_response: str
    relay_state: str | None = None


class OIDCLoginResponse(BaseSchema):
    """Réponse pour initier le login OIDC."""

    redirect_url: str
    state: str


class OIDCCallbackRequest(BaseSchema):
    """Callback OIDC après authentification."""

    code: str
    state: str


class CurrentUser(BaseSchema):
    """Utilisateur courant avec permissions."""

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str
    is_superuser: bool
    auth_provider: str
    permissions: list[str]
    roles: list[str]


class PasswordResetRequest(BaseSchema):
    """Requête de réinitialisation de mot de passe."""

    email: EmailStr


class PasswordResetConfirm(BaseSchema):
    """Confirmation de réinitialisation de mot de passe."""

    token: str
    new_password: str = Field(..., min_length=8)
