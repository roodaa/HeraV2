"""Tests pour l'API des achats."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models import User
from app.models.achat import Achat, CategorieAchat, StatutAchat
from app.models.facteur_emission import FacteurEmissionNACRES
from app.services.co2_service import CO2Service


@pytest.fixture
async def facteurs_nacres(db_session) -> list[FacteurEmissionNACRES]:
    """Crée les facteurs d'émission NACRES de test."""
    facteurs_data = [
        {"code": "A01", "description": "Produits chimiques", "facteur": Decimal("0.5")},
        {"code": "B02", "description": "Équipements de laboratoire", "facteur": Decimal("0.8")},
        {"code": "C03", "description": "Consommables", "facteur": Decimal("0.3")},
    ]

    facteurs = []
    for f in facteurs_data:
        facteur = FacteurEmissionNACRES(
            code_nacres=f["code"],
            description=f["description"],
            facteur_kg_par_euro=f["facteur"],
            source="Test ADEME",
            date_debut=date(2024, 1, 1),
            is_active=True,
        )
        db_session.add(facteur)
        facteurs.append(facteur)

    await db_session.commit()
    return facteurs


class TestListAchats:
    """Tests pour la liste des achats."""

    @pytest.mark.asyncio
    async def test_list_achats_empty(self, client: AsyncClient, auth_headers: dict):
        """Test liste achats vide."""
        response = await client.get("/api/v1/achats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_achats_with_data(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test liste achats avec données."""
        achat1 = Achat(
            date_achat=date(2024, 6, 1),
            description="Achat 1",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("50"),
        )
        achat2 = Achat(
            date_achat=date(2024, 6, 2),
            description="Achat 2",
            montant_euros=Decimal("300"),
            categorie=CategorieAchat.CONSOMMABLE,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("30"),
        )
        db_session.add_all([achat1, achat2])
        await db_session.commit()

        response = await client.get("/api/v1/achats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_list_achats_filter_categorie(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test filtre par catégorie."""
        achat1 = Achat(
            date_achat=date(2024, 6, 1),
            description="Équipement",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("50"),
        )
        achat2 = Achat(
            date_achat=date(2024, 6, 2),
            description="Consommable",
            montant_euros=Decimal("100"),
            categorie=CategorieAchat.CONSOMMABLE,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("10"),
        )
        db_session.add_all([achat1, achat2])
        await db_session.commit()

        response = await client.get(
            "/api/v1/achats?categorie=equipement", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["categorie"] == "equipement"

    @pytest.mark.asyncio
    async def test_list_achats_filter_date_range(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test filtre par plage de dates."""
        achat1 = Achat(
            date_achat=date(2024, 1, 15),
            description="Janvier",
            montant_euros=Decimal("100"),
            categorie=CategorieAchat.CONSOMMABLE,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("10"),
        )
        achat2 = Achat(
            date_achat=date(2024, 6, 15),
            description="Juin",
            montant_euros=Decimal("200"),
            categorie=CategorieAchat.CONSOMMABLE,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("20"),
        )
        db_session.add_all([achat1, achat2])
        await db_session.commit()

        response = await client.get(
            "/api/v1/achats?date_debut=2024-06-01&date_fin=2024-06-30",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["description"] == "Juin"


class TestCreateAchat:
    """Tests pour la création d'achat."""

    @pytest.mark.asyncio
    async def test_create_achat_success(
        self, client: AsyncClient, auth_headers: dict, facteurs_nacres
    ):
        """Test création achat avec calcul CO2."""
        CO2Service.clear_cache()

        response = await client.post(
            "/api/v1/achats",
            headers=auth_headers,
            json={
                "date_achat": "2024-06-01",
                "description": "Achat de produits chimiques",
                "montant_euros": 1000.0,
                "categorie": "consommable",
                "code_nacres": "A01",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "Achat de produits chimiques"
        assert float(data["montant_euros"]) == 1000.0
        assert data["code_nacres"] == "A01"
        # Impact CO2 = 1000 * 0.5 = 500 kg
        assert float(data["impact_co2_kg"]) == 500.0

    @pytest.mark.asyncio
    async def test_create_achat_without_nacres(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test création achat sans code NACRES."""
        response = await client.post(
            "/api/v1/achats",
            headers=auth_headers,
            json={
                "date_achat": "2024-06-01",
                "description": "Achat divers",
                "montant_euros": 500.0,
                "categorie": "service",
            },
        )

        assert response.status_code == 201
        data = response.json()
        # Sans code NACRES, impact peut être 0 ou calculé par défaut
        assert "impact_co2_kg" in data

    @pytest.mark.asyncio
    async def test_create_achat_invalid_data(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test création achat avec données invalides."""
        response = await client.post(
            "/api/v1/achats",
            headers=auth_headers,
            json={
                "date_achat": "2024-06-01",
                "description": "",  # Description vide
                "montant_euros": -100,  # Montant négatif
                "categorie": "invalid",  # Catégorie invalide
            },
        )

        assert response.status_code == 422


class TestGetAchat:
    """Tests pour récupérer un achat."""

    @pytest.mark.asyncio
    async def test_get_achat_success(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test récupération achat existant."""
        achat = Achat(
            date_achat=date(2024, 6, 1),
            description="Test achat",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(achat)
        await db_session.commit()
        await db_session.refresh(achat)

        response = await client.get(
            f"/api/v1/achats/{achat.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Test achat"
        assert float(data["montant_euros"]) == 500.0

    @pytest.mark.asyncio
    async def test_get_achat_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test récupération achat inexistant."""
        from uuid import uuid4

        response = await client.get(
            f"/api/v1/achats/{uuid4()}", headers=auth_headers
        )

        assert response.status_code == 404


class TestUpdateAchat:
    """Tests pour la mise à jour d'achat."""

    @pytest.mark.asyncio
    async def test_update_achat_success(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test mise à jour achat."""
        achat = Achat(
            date_achat=date(2024, 6, 1),
            description="Description originale",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            statut=StatutAchat.BROUILLON,
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(achat)
        await db_session.commit()
        await db_session.refresh(achat)

        response = await client.put(
            f"/api/v1/achats/{achat.id}",
            headers=auth_headers,
            json={
                "description": "Description modifiée",
                "montant_euros": 600.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Description modifiée"
        assert float(data["montant_euros"]) == 600.0

    @pytest.mark.asyncio
    async def test_update_achat_validated_forbidden(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test qu'on ne peut pas modifier un achat validé."""
        achat = Achat(
            date_achat=date(2024, 6, 1),
            description="Achat validé",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            statut=StatutAchat.VALIDE,
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(achat)
        await db_session.commit()
        await db_session.refresh(achat)

        response = await client.put(
            f"/api/v1/achats/{achat.id}",
            headers=auth_headers,
            json={"description": "Modification interdite"},
        )

        assert response.status_code == 400


class TestDeleteAchat:
    """Tests pour la suppression d'achat."""

    @pytest.mark.asyncio
    async def test_delete_achat_success(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test suppression achat (soft delete)."""
        achat = Achat(
            date_achat=date(2024, 6, 1),
            description="À supprimer",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            statut=StatutAchat.BROUILLON,
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(achat)
        await db_session.commit()
        await db_session.refresh(achat)

        response = await client.delete(
            f"/api/v1/achats/{achat.id}", headers=auth_headers
        )

        assert response.status_code == 200

        # Vérifie que l'achat n'est plus accessible
        get_response = await client.get(
            f"/api/v1/achats/{achat.id}", headers=auth_headers
        )
        assert get_response.status_code == 404


class TestAchatWorkflow:
    """Tests pour le workflow de validation des achats."""

    @pytest.mark.asyncio
    async def test_submit_achat(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test soumission achat."""
        achat = Achat(
            date_achat=date(2024, 6, 1),
            description="À soumettre",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            statut=StatutAchat.BROUILLON,
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(achat)
        await db_session.commit()
        await db_session.refresh(achat)

        response = await client.post(
            f"/api/v1/achats/{achat.id}/submit", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "soumis"

    @pytest.mark.asyncio
    async def test_validate_achat(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test validation achat."""
        achat = Achat(
            date_achat=date(2024, 6, 1),
            description="À valider",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            statut=StatutAchat.SOUMIS,
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(achat)
        await db_session.commit()
        await db_session.refresh(achat)

        response = await client.post(
            f"/api/v1/achats/{achat.id}/validate", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "valide"


class TestAchatStats:
    """Tests pour les statistiques achats."""

    @pytest.mark.asyncio
    async def test_stats_by_category(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test statistiques par catégorie."""
        achat1 = Achat(
            date_achat=date(2024, 6, 1),
            description="Équipement 1",
            montant_euros=Decimal("1000"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("100"),
        )
        achat2 = Achat(
            date_achat=date(2024, 6, 2),
            description="Équipement 2",
            montant_euros=Decimal("500"),
            categorie=CategorieAchat.EQUIPEMENT,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("50"),
        )
        achat3 = Achat(
            date_achat=date(2024, 6, 3),
            description="Consommable",
            montant_euros=Decimal("200"),
            categorie=CategorieAchat.CONSOMMABLE,
            user_id=admin_user.id,
            impact_co2_kg=Decimal("20"),
        )
        db_session.add_all([achat1, achat2, achat3])
        await db_session.commit()

        response = await client.get(
            "/api/v1/achats/stats/by-category", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Vérifie la structure des stats
        assert isinstance(data, list)
