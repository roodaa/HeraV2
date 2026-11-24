"""Tests pour l'API des équipes."""

import pytest
from httpx import AsyncClient

from app.models import User
from app.models.equipe import Equipe


class TestListEquipes:
    """Tests pour la liste des équipes."""

    @pytest.mark.asyncio
    async def test_list_equipes_empty(self, client: AsyncClient, auth_headers: dict):
        """Test liste équipes vide."""
        response = await client.get("/api/v1/equipes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_equipes_with_data(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test liste équipes avec données."""
        # Crée des équipes
        equipe1 = Equipe(code="EQ1", name="Équipe 1")
        equipe2 = Equipe(code="EQ2", name="Équipe 2")
        db_session.add_all([equipe1, equipe2])
        await db_session.commit()

        response = await client.get("/api/v1/equipes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_equipes_search(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test recherche équipes."""
        equipe1 = Equipe(code="RECHERCHE", name="Équipe Recherche")
        equipe2 = Equipe(code="ADMIN", name="Équipe Admin")
        db_session.add_all([equipe1, equipe2])
        await db_session.commit()

        response = await client.get(
            "/api/v1/equipes?search=recherche", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "RECHERCHE"

    @pytest.mark.asyncio
    async def test_list_equipes_unauthorized(self, client: AsyncClient):
        """Test accès sans authentification."""
        response = await client.get("/api/v1/equipes")
        assert response.status_code == 401


class TestCreateEquipe:
    """Tests pour la création d'équipe."""

    @pytest.mark.asyncio
    async def test_create_equipe_success(self, client: AsyncClient, auth_headers: dict):
        """Test création équipe valide."""
        response = await client.post(
            "/api/v1/equipes",
            headers=auth_headers,
            json={
                "code": "NEW_TEAM",
                "name": "Nouvelle Équipe",
                "description": "Description de test",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "NEW_TEAM"
        assert data["name"] == "Nouvelle Équipe"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_equipe_duplicate_code(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test création équipe avec code existant."""
        equipe = Equipe(code="EXISTING", name="Existante")
        db_session.add(equipe)
        await db_session.commit()

        response = await client.post(
            "/api/v1/equipes",
            headers=auth_headers,
            json={"code": "EXISTING", "name": "Autre Équipe"},
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_equipe_invalid_data(self, client: AsyncClient, auth_headers: dict):
        """Test création équipe avec données invalides."""
        response = await client.post(
            "/api/v1/equipes",
            headers=auth_headers,
            json={"code": "", "name": ""},  # Code et nom vides
        )

        assert response.status_code == 422


class TestGetEquipe:
    """Tests pour récupérer une équipe."""

    @pytest.mark.asyncio
    async def test_get_equipe_success(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test récupération équipe existante."""
        equipe = Equipe(code="TEST", name="Test Équipe")
        db_session.add(equipe)
        await db_session.commit()
        await db_session.refresh(equipe)

        response = await client.get(
            f"/api/v1/equipes/{equipe.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "TEST"
        assert "members" in data
        assert "member_count" in data

    @pytest.mark.asyncio
    async def test_get_equipe_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test récupération équipe inexistante."""
        from uuid import uuid4

        response = await client.get(
            f"/api/v1/equipes/{uuid4()}", headers=auth_headers
        )

        assert response.status_code == 404


class TestUpdateEquipe:
    """Tests pour la mise à jour d'équipe."""

    @pytest.mark.asyncio
    async def test_update_equipe_success(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test mise à jour équipe."""
        equipe = Equipe(code="OLD_CODE", name="Old Name")
        db_session.add(equipe)
        await db_session.commit()
        await db_session.refresh(equipe)

        response = await client.put(
            f"/api/v1/equipes/{equipe.id}",
            headers=auth_headers,
            json={"name": "New Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["code"] == "OLD_CODE"  # Code non modifié


class TestDeleteEquipe:
    """Tests pour la suppression d'équipe."""

    @pytest.mark.asyncio
    async def test_delete_equipe_success(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test suppression équipe."""
        equipe = Equipe(code="TO_DELETE", name="À Supprimer")
        db_session.add(equipe)
        await db_session.commit()
        await db_session.refresh(equipe)

        response = await client.delete(
            f"/api/v1/equipes/{equipe.id}", headers=auth_headers
        )

        assert response.status_code == 200

        # Vérifie que l'équipe n'est plus accessible
        get_response = await client.get(
            f"/api/v1/equipes/{equipe.id}", headers=auth_headers
        )
        assert get_response.status_code == 404


class TestEquipeMembers:
    """Tests pour la gestion des membres d'équipe."""

    @pytest.mark.asyncio
    async def test_add_member_success(
        self, client: AsyncClient, auth_headers: dict, db_session, regular_user: User
    ):
        """Test ajout membre à équipe."""
        equipe = Equipe(code="TEAM", name="Team")
        db_session.add(equipe)
        await db_session.commit()
        await db_session.refresh(equipe)

        response = await client.post(
            f"/api/v1/equipes/{equipe.id}/members",
            headers=auth_headers,
            json={"user_id": str(regular_user.id)},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_add_member_already_in_team(
        self, client: AsyncClient, auth_headers: dict, db_session, regular_user: User
    ):
        """Test ajout membre déjà dans l'équipe."""
        equipe = Equipe(code="TEAM2", name="Team 2")
        db_session.add(equipe)
        await db_session.commit()
        await db_session.refresh(equipe)

        # Premier ajout
        regular_user.equipe_id = equipe.id
        await db_session.commit()

        # Deuxième ajout
        response = await client.post(
            f"/api/v1/equipes/{equipe.id}/members",
            headers=auth_headers,
            json={"user_id": str(regular_user.id)},
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_remove_member_success(
        self, client: AsyncClient, auth_headers: dict, db_session, regular_user: User
    ):
        """Test retrait membre d'équipe."""
        equipe = Equipe(code="TEAM3", name="Team 3")
        db_session.add(equipe)
        await db_session.commit()
        await db_session.refresh(equipe)

        regular_user.equipe_id = equipe.id
        await db_session.commit()

        response = await client.delete(
            f"/api/v1/equipes/{equipe.id}/members/{regular_user.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
