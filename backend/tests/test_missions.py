"""Tests pour l'API des missions."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models import User
from app.models.mission import Mission, Etape, ModeTransport, StatutMission, TypeMission
from app.services.co2_service import CO2Service


class TestListMissions:
    """Tests pour la liste des missions."""

    @pytest.mark.asyncio
    async def test_list_missions_empty(self, client: AsyncClient, auth_headers: dict):
        """Test liste missions vide."""
        response = await client.get("/api/v1/missions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_missions_with_data(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test liste missions avec données."""
        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="Conférence",
            type_mission=TypeMission.ALLER_RETOUR,
            user_id=admin_user.id,
            distance_totale_km=Decimal("500"),
            impact_co2_kg=Decimal("50"),
        )
        db_session.add(mission)
        await db_session.commit()

        response = await client.get("/api/v1/missions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_missions_filter_statut(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test filtre par statut."""
        mission1 = Mission(
            date_depart=date(2024, 6, 1),
            motif="Mission 1",
            user_id=admin_user.id,
            statut=StatutMission.BROUILLON,
        )
        mission2 = Mission(
            date_depart=date(2024, 6, 2),
            motif="Mission 2",
            user_id=admin_user.id,
            statut=StatutMission.VALIDEE,
        )
        db_session.add_all([mission1, mission2])
        await db_session.commit()

        response = await client.get(
            "/api/v1/missions?statut=brouillon", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["statut"] == "brouillon"


class TestCreateMission:
    """Tests pour la création de mission."""

    @pytest.mark.asyncio
    async def test_create_mission_success(
        self, client: AsyncClient, auth_headers: dict, facteurs_transport
    ):
        """Test création mission avec étapes."""
        # Vide le cache pour forcer la lecture des facteurs
        CO2Service.clear_cache()

        response = await client.post(
            "/api/v1/missions",
            headers=auth_headers,
            json={
                "date_depart": "2024-06-01",
                "motif": "Conférence internationale",
                "type_mission": "aller_retour",
                "etapes": [
                    {
                        "ville_depart": "Paris",
                        "ville_arrivee": "Lyon",
                        "mode_transport": "tgv",
                        "distance_km": 450,
                    }
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["motif"] == "Conférence internationale"
        assert data["statut"] == "brouillon"
        assert len(data["etapes"]) == 1
        # Aller-retour = distance * 2
        assert float(data["distance_totale_km"]) == 900.0
        # Impact CO2 calculé automatiquement
        assert float(data["impact_co2_kg"]) > 0

    @pytest.mark.asyncio
    async def test_create_mission_aller_simple(
        self, client: AsyncClient, auth_headers: dict, facteurs_transport
    ):
        """Test création mission aller simple."""
        CO2Service.clear_cache()

        response = await client.post(
            "/api/v1/missions",
            headers=auth_headers,
            json={
                "date_depart": "2024-06-01",
                "motif": "Déménagement",
                "type_mission": "aller_simple",
                "etapes": [
                    {
                        "ville_depart": "Paris",
                        "ville_arrivee": "Marseille",
                        "mode_transport": "train",
                        "distance_km": 775,
                    }
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        # Aller simple = distance * 1
        assert float(data["distance_totale_km"]) == 775.0

    @pytest.mark.asyncio
    async def test_create_mission_multiple_etapes(
        self, client: AsyncClient, auth_headers: dict, facteurs_transport
    ):
        """Test création mission avec plusieurs étapes."""
        CO2Service.clear_cache()

        response = await client.post(
            "/api/v1/missions",
            headers=auth_headers,
            json={
                "date_depart": "2024-06-01",
                "motif": "Tournée",
                "type_mission": "aller_simple",
                "etapes": [
                    {
                        "ville_depart": "Paris",
                        "ville_arrivee": "Lyon",
                        "mode_transport": "tgv",
                        "distance_km": 450,
                        "ordre": 1,
                    },
                    {
                        "ville_depart": "Lyon",
                        "ville_arrivee": "Marseille",
                        "mode_transport": "voiture",
                        "distance_km": 315,
                        "ordre": 2,
                    },
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["etapes"]) == 2
        assert float(data["distance_totale_km"]) == 765.0

    @pytest.mark.asyncio
    async def test_create_mission_no_etapes(self, client: AsyncClient, auth_headers: dict):
        """Test création mission sans étapes (erreur)."""
        response = await client.post(
            "/api/v1/missions",
            headers=auth_headers,
            json={
                "date_depart": "2024-06-01",
                "motif": "Mission sans étape",
                "type_mission": "aller_retour",
                "etapes": [],
            },
        )

        assert response.status_code == 422


class TestMissionWorkflow:
    """Tests pour le workflow de validation."""

    @pytest.mark.asyncio
    async def test_submit_mission(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test soumission mission."""
        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="À soumettre",
            user_id=admin_user.id,
            statut=StatutMission.BROUILLON,
        )
        db_session.add(mission)
        await db_session.commit()
        await db_session.refresh(mission)

        response = await client.post(
            f"/api/v1/missions/{mission.id}/submit", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "soumise"

    @pytest.mark.asyncio
    async def test_validate_mission(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test validation mission."""
        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="À valider",
            user_id=admin_user.id,
            statut=StatutMission.SOUMISE,
        )
        db_session.add(mission)
        await db_session.commit()
        await db_session.refresh(mission)

        response = await client.post(
            f"/api/v1/missions/{mission.id}/validate",
            headers=auth_headers,
            json={"commentaire": "Validé"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "validee"

    @pytest.mark.asyncio
    async def test_reject_mission(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test rejet mission."""
        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="À rejeter",
            user_id=admin_user.id,
            statut=StatutMission.SOUMISE,
        )
        db_session.add(mission)
        await db_session.commit()
        await db_session.refresh(mission)

        response = await client.post(
            f"/api/v1/missions/{mission.id}/reject",
            headers=auth_headers,
            json={"commentaire": "Manque justificatif"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["statut"] == "rejetee"

    @pytest.mark.asyncio
    async def test_cannot_validate_brouillon(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test qu'on ne peut pas valider un brouillon."""
        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="Brouillon",
            user_id=admin_user.id,
            statut=StatutMission.BROUILLON,
        )
        db_session.add(mission)
        await db_session.commit()
        await db_session.refresh(mission)

        response = await client.post(
            f"/api/v1/missions/{mission.id}/validate",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 400


class TestMissionEtapes:
    """Tests pour la gestion des étapes."""

    @pytest.mark.asyncio
    async def test_add_etape(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User, facteurs_transport
    ):
        """Test ajout étape à une mission."""
        CO2Service.clear_cache()

        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="Mission",
            user_id=admin_user.id,
            type_mission=TypeMission.ALLER_SIMPLE,
            statut=StatutMission.BROUILLON,
            distance_totale_km=Decimal("0"),
            impact_co2_kg=Decimal("0"),
        )
        db_session.add(mission)
        await db_session.commit()
        await db_session.refresh(mission)

        response = await client.post(
            f"/api/v1/missions/{mission.id}/etapes",
            headers=auth_headers,
            json={
                "ville_depart": "Paris",
                "ville_arrivee": "Nice",
                "mode_transport": "avion",
                "distance_km": 686,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ville_depart"] == "Paris"
        assert float(data["impact_co2_kg"]) > 0

    @pytest.mark.asyncio
    async def test_delete_etape(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test suppression étape."""
        mission = Mission(
            date_depart=date(2024, 6, 1),
            motif="Mission",
            user_id=admin_user.id,
            statut=StatutMission.BROUILLON,
            distance_totale_km=Decimal("200"),
            impact_co2_kg=Decimal("20"),
        )
        db_session.add(mission)
        await db_session.flush()

        etape1 = Etape(
            mission_id=mission.id,
            ordre=1,
            ville_depart="Paris",
            ville_arrivee="Lyon",
            mode_transport=ModeTransport.TGV,
            distance_km=Decimal("100"),
            impact_co2_kg=Decimal("10"),
        )
        etape2 = Etape(
            mission_id=mission.id,
            ordre=2,
            ville_depart="Lyon",
            ville_arrivee="Marseille",
            mode_transport=ModeTransport.TGV,
            distance_km=Decimal("100"),
            impact_co2_kg=Decimal("10"),
        )
        db_session.add_all([etape1, etape2])
        await db_session.commit()
        await db_session.refresh(etape1)

        response = await client.delete(
            f"/api/v1/missions/{mission.id}/etapes/{etape1.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200


class TestMissionStats:
    """Tests pour les statistiques missions."""

    @pytest.mark.asyncio
    async def test_stats_summary(
        self, client: AsyncClient, auth_headers: dict, db_session, admin_user: User
    ):
        """Test statistiques missions."""
        mission1 = Mission(
            date_depart=date(2024, 6, 1),
            motif="Mission 1",
            user_id=admin_user.id,
            statut=StatutMission.VALIDEE,
            distance_totale_km=Decimal("500"),
            impact_co2_kg=Decimal("50"),
        )
        mission2 = Mission(
            date_depart=date(2024, 6, 15),
            motif="Mission 2",
            user_id=admin_user.id,
            statut=StatutMission.BROUILLON,
            distance_totale_km=Decimal("300"),
            impact_co2_kg=Decimal("30"),
        )
        db_session.add_all([mission1, mission2])
        await db_session.commit()

        response = await client.get(
            "/api/v1/missions/stats/summary", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_missions"] == 2
        assert data["total_distance_km"] == 800.0
        assert data["total_impact_co2_kg"] == 80.0
