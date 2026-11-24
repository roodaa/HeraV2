"""Tests pour l'API d'authentification."""

import pytest
from httpx import AsyncClient

from app.models import User


class TestLogin:
    """Tests pour le endpoint de login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, admin_user: User):
        """Test login avec credentials valides."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.local", "password": "password123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, client: AsyncClient):
        """Test login avec email invalide."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "invalid@test.local", "password": "password123"},
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, admin_user: User):
        """Test login avec mot de passe invalide."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.local", "password": "wrongpassword"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db_session, admin_user: User):
        """Test login avec utilisateur désactivé."""
        admin_user.is_active = False
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.local", "password": "password123"},
        )

        assert response.status_code == 401


class TestMe:
    """Tests pour le endpoint /me."""

    @pytest.mark.asyncio
    async def test_me_authenticated(self, client: AsyncClient, auth_headers: dict, admin_user: User):
        """Test récupération du profil avec token valide."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == admin_user.email
        assert data["first_name"] == admin_user.first_name
        assert "permissions" in data
        assert "roles" in data

    @pytest.mark.asyncio
    async def test_me_no_token(self, client: AsyncClient):
        """Test accès sans token."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client: AsyncClient):
        """Test accès avec token invalide."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401


class TestRefreshToken:
    """Tests pour le refresh token."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, admin_user: User):
        """Test refresh token valide."""
        # D'abord login pour obtenir un refresh token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.local", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Utilise le refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refresh token invalide."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"},
        )

        assert response.status_code == 401
