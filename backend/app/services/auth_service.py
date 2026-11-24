"""Service d'authentification."""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models import User
from app.schemas import TokenPayload, TokenResponse

settings = get_settings()

# Configuration du hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service de gestion de l'authentification."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Gestion des mots de passe ====================

    @staticmethod
    def hash_password(password: str) -> str:
        """Hache un mot de passe."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe."""
        return pwd_context.verify(plain_password, hashed_password)

    # ==================== Gestion des tokens JWT ====================

    @staticmethod
    def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
        """Crée un token d'accès JWT."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

        now = datetime.now(UTC)
        expire = now + expires_delta

        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "type": "access",
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    @staticmethod
    def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
        """Crée un token de rafraîchissement JWT."""
        if expires_delta is None:
            expires_delta = timedelta(days=settings.refresh_token_expire_days)

        now = datetime.now(UTC)
        expire = now + expires_delta

        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "type": "refresh",
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    @staticmethod
    def decode_token(token: str) -> TokenPayload | None:
        """Décode et valide un token JWT."""
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"], UTC),
                iat=datetime.fromtimestamp(payload["iat"], UTC),
                type=payload["type"],
            )
        except JWTError:
            return None

    def create_tokens(self, user_id: str) -> TokenResponse:
        """Crée une paire de tokens (access + refresh)."""
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token(user_id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )

    # ==================== Authentification locale ====================

    async def authenticate_local(
        self, email: str, password: str
    ) -> User | None:
        """Authentifie un utilisateur avec email/mot de passe."""
        stmt = select(User).where(
            User.email == email,
            User.auth_provider == "local",
            User.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Récupère un utilisateur par son ID."""
        from uuid import UUID

        try:
            uuid = UUID(user_id)
        except ValueError:
            return None

        stmt = select(User).where(
            User.id == uuid,
            User.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_external_id(
        self, external_id: str, auth_provider: str
    ) -> User | None:
        """Récupère un utilisateur par son ID externe (SAML/OIDC)."""
        stmt = select(User).where(
            User.external_id == external_id,
            User.auth_provider == auth_provider,
            User.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_login(self, user: User) -> None:
        """Met à jour la date de dernière connexion."""
        user.last_login = datetime.now(UTC)
        await self.db.commit()

    # ==================== Authentification SAML (Renater) ====================

    async def process_saml_response(
        self, saml_attributes: dict[str, Any]
    ) -> User | None:
        """
        Traite la réponse SAML et crée/récupère l'utilisateur.

        Attributs SAML Renater typiques:
        - eduPersonPrincipalName: identifiant unique
        - mail: email
        - givenName: prénom
        - sn: nom de famille
        """
        external_id = saml_attributes.get("eduPersonPrincipalName")
        if not external_id:
            return None

        # Cherche l'utilisateur existant
        user = await self.get_user_by_external_id(external_id, "saml")

        if user:
            # Met à jour les infos si nécessaire
            user.email = saml_attributes.get("mail", user.email)
            user.first_name = saml_attributes.get("givenName", user.first_name)
            user.last_name = saml_attributes.get("sn", user.last_name)
            await self.db.commit()
        else:
            # Crée un nouvel utilisateur
            user = User(
                email=saml_attributes.get("mail"),
                first_name=saml_attributes.get("givenName", ""),
                last_name=saml_attributes.get("sn", ""),
                external_id=external_id,
                auth_provider="saml",
                is_active=True,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        return user

    # ==================== Authentification OIDC ====================

    async def process_oidc_userinfo(
        self, userinfo: dict[str, Any]
    ) -> User | None:
        """
        Traite les informations utilisateur OIDC et crée/récupère l'utilisateur.

        Claims OIDC standard:
        - sub: identifiant unique
        - email: email
        - given_name: prénom
        - family_name: nom de famille
        """
        external_id = userinfo.get("sub")
        if not external_id:
            return None

        # Cherche l'utilisateur existant
        user = await self.get_user_by_external_id(external_id, "oidc")

        if user:
            # Met à jour les infos si nécessaire
            user.email = userinfo.get("email", user.email)
            user.first_name = userinfo.get("given_name", user.first_name)
            user.last_name = userinfo.get("family_name", user.last_name)
            await self.db.commit()
        else:
            # Crée un nouvel utilisateur
            user = User(
                email=userinfo.get("email"),
                first_name=userinfo.get("given_name", ""),
                last_name=userinfo.get("family_name", ""),
                external_id=external_id,
                auth_provider="oidc",
                is_active=True,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        return user
