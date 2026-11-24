"""Routes de gestion des missions."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.database import get_db
from app.middleware.auth import PermissionChecker
from app.models import User
from app.models.mission import Etape, Mission, ModeTransport, StatutMission, TypeMission
from app.models.role import PermissionCodes
from app.schemas import MessageResponse, PaginatedResponse
from app.schemas.mission import (
    EtapeCreate,
    EtapeResponse,
    EtapeUpdate,
    MissionCreate,
    MissionResponse,
    MissionUpdate,
    MissionValidate,
    MissionWithEtapes,
    MissionWithUser,
)
from app.services.co2_service import CO2Service

router = APIRouter()

# Vérificateurs de permissions
can_read_missions = PermissionChecker([PermissionCodes.MISSIONS_READ])
can_create_missions = PermissionChecker([PermissionCodes.MISSIONS_CREATE])
can_update_missions = PermissionChecker([PermissionCodes.MISSIONS_UPDATE])
can_delete_missions = PermissionChecker([PermissionCodes.MISSIONS_DELETE])
can_validate_missions = PermissionChecker([PermissionCodes.MISSIONS_VALIDATE])


# ==================== Routes Mission ====================


@router.get("", response_model=PaginatedResponse[MissionWithUser])
async def list_missions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(can_read_missions)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    statut: StatutMission | None = None,
    user_id: UUID | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
    mode_transport: ModeTransport | None = None,
    mes_missions: bool = False,
):
    """
    Liste les missions avec pagination et filtres.

    - **mes_missions**: Si True, filtre uniquement les missions de l'utilisateur connecté
    - **statut**: Filtre par statut (brouillon, soumise, validee, rejetee)
    - **user_id**: Filtre par utilisateur
    - **date_debut/date_fin**: Filtre par période
    - **mode_transport**: Filtre par mode de transport
    """
    # Construction de la requête de base
    stmt = (
        select(Mission)
        .where(Mission.deleted_at.is_(None))
        .options(selectinload(Mission.user))
    )

    # Filtre mes missions (pour les utilisateurs non-admin)
    if mes_missions:
        stmt = stmt.where(Mission.user_id == current_user.id)
    elif user_id:
        stmt = stmt.where(Mission.user_id == user_id)

    # Filtre par statut
    if statut:
        stmt = stmt.where(Mission.statut == statut)

    # Filtre par période
    if date_debut:
        stmt = stmt.where(Mission.date_depart >= date_debut)
    if date_fin:
        stmt = stmt.where(Mission.date_depart <= date_fin)

    # Filtre par recherche (motif)
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(Mission.motif.ilike(search_term))

    # Filtre par mode de transport (nécessite une jointure)
    if mode_transport:
        stmt = stmt.join(Etape).where(Etape.mode_transport == mode_transport).distinct()

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination et tri
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(Mission.date_depart.desc())

    result = await db.execute(stmt)
    missions = result.scalars().unique().all()

    return PaginatedResponse(
        items=missions,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=MissionWithEtapes, status_code=status.HTTP_201_CREATED)
async def create_mission(
    mission_data: MissionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(can_create_missions)],
):
    """
    Crée une nouvelle mission avec ses étapes.

    Le calcul de l'impact CO2 est automatique basé sur les facteurs d'émission ADEME.
    """
    # Prépare les données des étapes pour le calcul CO2
    etapes_data = [
        {
            "mode_transport": etape.mode_transport,
            "distance_km": etape.distance_km,
        }
        for etape in mission_data.etapes
    ]

    # Calcule l'impact CO2 total
    distance_totale, impact_total, impacts_par_etape = await CO2Service.calculer_impact_mission(
        db,
        etapes_data,
        mission_data.type_mission.value,
    )

    # Crée la mission
    mission = Mission(
        date_depart=mission_data.date_depart,
        date_retour=mission_data.date_retour,
        motif=mission_data.motif,
        type_mission=mission_data.type_mission,
        commentaire=mission_data.commentaire,
        user_id=current_user.id,
        distance_totale_km=distance_totale,
        impact_co2_kg=impact_total,
        statut=StatutMission.BROUILLON,
    )

    db.add(mission)
    await db.flush()  # Pour obtenir l'ID de la mission

    # Crée les étapes
    for i, etape_data in enumerate(mission_data.etapes):
        # Pour aller-retour, l'impact de chaque étape est doublé
        impact_etape = impacts_par_etape[i]

        etape = Etape(
            mission_id=mission.id,
            ordre=etape_data.ordre or (i + 1),
            ville_depart=etape_data.ville_depart,
            ville_arrivee=etape_data.ville_arrivee,
            mode_transport=etape_data.mode_transport,
            distance_km=etape_data.distance_km,
            classe_transport=etape_data.classe_transport,
            distance_auto=False,
            impact_co2_kg=impact_etape,
        )
        db.add(etape)

    await db.commit()

    # Recharge avec les relations
    stmt = (
        select(Mission)
        .where(Mission.id == mission.id)
        .options(selectinload(Mission.etapes), selectinload(Mission.user))
    )
    mission = (await db.execute(stmt)).scalar_one()

    return mission


@router.get("/{mission_id}", response_model=MissionWithEtapes)
async def get_mission(
    mission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_missions)],
):
    """
    Récupère une mission par son ID avec ses étapes.
    """
    stmt = (
        select(Mission)
        .where(Mission.id == mission_id, Mission.deleted_at.is_(None))
        .options(selectinload(Mission.etapes), selectinload(Mission.user))
    )
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    return mission


@router.put("/{mission_id}", response_model=MissionWithEtapes)
async def update_mission(
    mission_id: UUID,
    mission_data: MissionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(can_update_missions)],
):
    """
    Met à jour une mission.

    Seules les missions en brouillon ou rejetées peuvent être modifiées.
    """
    stmt = (
        select(Mission)
        .where(Mission.id == mission_id, Mission.deleted_at.is_(None))
        .options(selectinload(Mission.etapes), selectinload(Mission.user))
    )
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    # Vérifie que la mission peut être modifiée
    if mission.statut not in [StatutMission.BROUILLON, StatutMission.REJETEE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les missions en brouillon ou rejetées peuvent être modifiées",
        )

    # Met à jour les champs fournis
    update_data = mission_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mission, field, value)

    # Si rejetée, repasse en brouillon après modification
    if mission.statut == StatutMission.REJETEE:
        mission.statut = StatutMission.BROUILLON

    await db.commit()
    await db.refresh(mission)

    return mission


@router.delete("/{mission_id}", response_model=MessageResponse)
async def delete_mission(
    mission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_delete_missions)],
):
    """
    Supprime une mission (soft delete).
    """
    stmt = select(Mission).where(Mission.id == mission_id, Mission.deleted_at.is_(None))
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    # Soft delete
    mission.deleted_at = datetime.now(UTC)
    await db.commit()

    return MessageResponse(message="Mission supprimée avec succès")


# ==================== Workflow de validation ====================


@router.post("/{mission_id}/submit", response_model=MissionResponse)
async def submit_mission(
    mission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(can_create_missions)],
):
    """
    Soumet une mission pour validation.

    La mission doit être en brouillon et appartenir à l'utilisateur.
    """
    stmt = select(Mission).where(Mission.id == mission_id, Mission.deleted_at.is_(None))
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    # Vérifie que c'est bien la mission de l'utilisateur ou qu'il a les droits
    if mission.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez soumettre que vos propres missions",
        )

    if mission.statut != StatutMission.BROUILLON:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les missions en brouillon peuvent être soumises",
        )

    mission.statut = StatutMission.SOUMISE
    await db.commit()
    await db.refresh(mission)

    return mission


@router.post("/{mission_id}/validate", response_model=MissionResponse)
async def validate_mission(
    mission_id: UUID,
    validation_data: MissionValidate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_validate_missions)],
):
    """
    Valide une mission soumise.
    """
    stmt = select(Mission).where(Mission.id == mission_id, Mission.deleted_at.is_(None))
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    if mission.statut != StatutMission.SOUMISE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les missions soumises peuvent être validées",
        )

    mission.statut = StatutMission.VALIDEE
    if validation_data.commentaire:
        mission.commentaire = validation_data.commentaire

    await db.commit()
    await db.refresh(mission)

    return mission


@router.post("/{mission_id}/reject", response_model=MissionResponse)
async def reject_mission(
    mission_id: UUID,
    rejection_data: MissionValidate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_validate_missions)],
):
    """
    Rejette une mission soumise.
    """
    stmt = select(Mission).where(Mission.id == mission_id, Mission.deleted_at.is_(None))
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    if mission.statut != StatutMission.SOUMISE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les missions soumises peuvent être rejetées",
        )

    mission.statut = StatutMission.REJETEE
    if rejection_data.commentaire:
        mission.commentaire = rejection_data.commentaire

    await db.commit()
    await db.refresh(mission)

    return mission


# ==================== Routes Étapes ====================


@router.post("/{mission_id}/etapes", response_model=EtapeResponse, status_code=status.HTTP_201_CREATED)
async def add_etape(
    mission_id: UUID,
    etape_data: EtapeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_missions)],
):
    """
    Ajoute une étape à une mission existante.

    La mission doit être en brouillon ou rejetée.
    """
    stmt = (
        select(Mission)
        .where(Mission.id == mission_id, Mission.deleted_at.is_(None))
        .options(selectinload(Mission.etapes))
    )
    mission = (await db.execute(stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    if mission.statut not in [StatutMission.BROUILLON, StatutMission.REJETEE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'ajouter une étape à une mission soumise ou validée",
        )

    # Calcule l'impact CO2 de l'étape
    impact_etape = await CO2Service.calculer_impact_etape(
        db,
        etape_data.mode_transport,
        etape_data.distance_km,
    )

    # Pour aller-retour, double l'impact
    if mission.type_mission == TypeMission.ALLER_RETOUR:
        impact_etape *= 2

    # Détermine l'ordre
    max_ordre = max((e.ordre for e in mission.etapes), default=0)
    ordre = etape_data.ordre or (max_ordre + 1)

    # Crée l'étape
    etape = Etape(
        mission_id=mission.id,
        ordre=ordre,
        ville_depart=etape_data.ville_depart,
        ville_arrivee=etape_data.ville_arrivee,
        mode_transport=etape_data.mode_transport,
        distance_km=etape_data.distance_km,
        classe_transport=etape_data.classe_transport,
        distance_auto=False,
        impact_co2_kg=impact_etape,
    )
    db.add(etape)

    # Met à jour les totaux de la mission
    distance_ajout = etape_data.distance_km
    if mission.type_mission == TypeMission.ALLER_RETOUR:
        distance_ajout *= 2

    mission.distance_totale_km += distance_ajout
    mission.impact_co2_kg += impact_etape

    await db.commit()
    await db.refresh(etape)

    return etape


@router.put("/{mission_id}/etapes/{etape_id}", response_model=EtapeResponse)
async def update_etape(
    mission_id: UUID,
    etape_id: UUID,
    etape_data: EtapeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_missions)],
):
    """
    Met à jour une étape.

    La mission doit être en brouillon ou rejetée.
    """
    # Récupère la mission
    mission_stmt = select(Mission).where(
        Mission.id == mission_id, Mission.deleted_at.is_(None)
    )
    mission = (await db.execute(mission_stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    if mission.statut not in [StatutMission.BROUILLON, StatutMission.REJETEE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de modifier une étape d'une mission soumise ou validée",
        )

    # Récupère l'étape
    etape_stmt = select(Etape).where(
        Etape.id == etape_id, Etape.mission_id == mission_id
    )
    etape = (await db.execute(etape_stmt)).scalar_one_or_none()

    if not etape:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Étape non trouvée",
        )

    # Soustrait l'ancien impact des totaux
    mission.distance_totale_km -= etape.distance_km * (2 if mission.type_mission == TypeMission.ALLER_RETOUR else 1)
    mission.impact_co2_kg -= etape.impact_co2_kg

    # Met à jour les champs
    update_data = etape_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(etape, field, value)

    # Recalcule l'impact CO2
    new_impact = await CO2Service.calculer_impact_etape(
        db,
        etape.mode_transport,
        etape.distance_km,
    )
    if mission.type_mission == TypeMission.ALLER_RETOUR:
        new_impact *= 2

    etape.impact_co2_kg = new_impact

    # Ajoute le nouvel impact aux totaux
    mission.distance_totale_km += etape.distance_km * (2 if mission.type_mission == TypeMission.ALLER_RETOUR else 1)
    mission.impact_co2_kg += new_impact

    await db.commit()
    await db.refresh(etape)

    return etape


@router.delete("/{mission_id}/etapes/{etape_id}", response_model=MessageResponse)
async def delete_etape(
    mission_id: UUID,
    etape_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_missions)],
):
    """
    Supprime une étape.

    La mission doit être en brouillon ou rejetée et avoir plus d'une étape.
    """
    # Récupère la mission avec ses étapes
    mission_stmt = (
        select(Mission)
        .where(Mission.id == mission_id, Mission.deleted_at.is_(None))
        .options(selectinload(Mission.etapes))
    )
    mission = (await db.execute(mission_stmt)).scalar_one_or_none()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée",
        )

    if mission.statut not in [StatutMission.BROUILLON, StatutMission.REJETEE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer une étape d'une mission soumise ou validée",
        )

    if len(mission.etapes) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Une mission doit avoir au moins une étape",
        )

    # Trouve l'étape à supprimer
    etape = next((e for e in mission.etapes if e.id == etape_id), None)

    if not etape:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Étape non trouvée",
        )

    # Met à jour les totaux
    mission.distance_totale_km -= etape.distance_km * (2 if mission.type_mission == TypeMission.ALLER_RETOUR else 1)
    mission.impact_co2_kg -= etape.impact_co2_kg

    # Supprime l'étape
    await db.delete(etape)
    await db.commit()

    return MessageResponse(message="Étape supprimée avec succès")


# ==================== Statistiques ====================


@router.get("/stats/summary")
async def get_missions_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_missions)],
    year: int | None = None,
    user_id: UUID | None = None,
):
    """
    Retourne les statistiques des missions.
    """
    # Base query
    stmt = select(Mission).where(Mission.deleted_at.is_(None))

    if year:
        stmt = stmt.where(func.extract("year", Mission.date_depart) == year)

    if user_id:
        stmt = stmt.where(Mission.user_id == user_id)

    result = await db.execute(stmt)
    missions = result.scalars().all()

    # Calcul des statistiques
    total_missions = len(missions)
    total_distance = sum(m.distance_totale_km for m in missions)
    total_impact = sum(m.impact_co2_kg for m in missions)

    # Par statut
    missions_par_statut = {}
    for statut in StatutMission:
        missions_par_statut[statut.value] = sum(
            1 for m in missions if m.statut == statut
        )

    return {
        "total_missions": total_missions,
        "total_distance_km": float(total_distance),
        "total_impact_co2_kg": float(total_impact),
        "missions_par_statut": missions_par_statut,
    }
