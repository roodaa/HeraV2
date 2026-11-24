"""Routes de gestion du matériel informatique."""

from datetime import UTC, datetime, date
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
from app.models.equipe import Equipe
from app.models.materiel import Materiel, StatutMateriel, TypeMateriel
from app.models.role import PermissionCodes
from app.schemas import MessageResponse, PaginatedResponse
from app.schemas.materiel import (
    MaterielCreate,
    MaterielResponse,
    MaterielUpdate,
    MaterielWithUser,
)
from app.services.co2_service import CO2Service

router = APIRouter()

# Vérificateurs de permissions
can_read_materiel = PermissionChecker([PermissionCodes.MATERIEL_READ])
can_create_materiel = PermissionChecker([PermissionCodes.MATERIEL_CREATE])
can_update_materiel = PermissionChecker([PermissionCodes.MATERIEL_UPDATE])
can_delete_materiel = PermissionChecker([PermissionCodes.MATERIEL_DELETE])


def _compute_materiel_properties(materiel: Materiel) -> dict:
    """Calcule les propriétés dérivées du matériel."""
    impact_total = materiel.impact_fabrication_kg + (
        materiel.impact_usage_annuel_kg * materiel.duree_vie_annees
    )
    impact_amorti = (
        materiel.impact_fabrication_kg / materiel.duree_vie_annees
    ) + materiel.impact_usage_annuel_kg

    return {
        "impact_total_kg": impact_total.quantize(Decimal("0.001")),
        "impact_amorti_annuel_kg": impact_amorti.quantize(Decimal("0.001")),
    }


@router.get("", response_model=PaginatedResponse[MaterielWithUser])
async def list_materiel(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_materiel)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    type_materiel: TypeMateriel | None = None,
    statut: StatutMateriel | None = None,
    equipe_id: UUID | None = None,
    user_id: UUID | None = None,
    date_acquisition_debut: str | None = None,
    date_acquisition_fin: str | None = None,
):
    """
    Liste le matériel avec pagination et filtres.

    - **search**: Recherche dans marque, modèle, numéro de série
    - **type_materiel**: Filtre par type
    - **statut**: Filtre par statut
    - **equipe_id**: Filtre par équipe
    - **user_id**: Filtre par utilisateur attribué
    """
    # Construction de la requête de base
    stmt = (
        select(Materiel)
        .where(Materiel.deleted_at.is_(None))
        .options(selectinload(Materiel.user))
    )

    # Filtres
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            (Materiel.marque.ilike(search_term))
            | (Materiel.modele.ilike(search_term))
            | (Materiel.numero_serie.ilike(search_term))
            | (Materiel.description.ilike(search_term))
        )

    if type_materiel:
        stmt = stmt.where(Materiel.type_materiel == type_materiel)

    if statut:
        stmt = stmt.where(Materiel.statut == statut)

    if equipe_id:
        stmt = stmt.where(Materiel.equipe_id == equipe_id)

    if user_id:
        stmt = stmt.where(Materiel.user_id == user_id)

    if date_acquisition_debut:
        stmt = stmt.where(Materiel.date_acquisition >= date_acquisition_debut)

    if date_acquisition_fin:
        stmt = stmt.where(Materiel.date_acquisition <= date_acquisition_fin)

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination et tri
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(Materiel.date_acquisition.desc())

    result = await db.execute(stmt)
    materiels = result.scalars().all()

    # Ajoute les propriétés calculées
    items = []
    for m in materiels:
        m_dict = {
            "id": m.id,
            "type_materiel": m.type_materiel,
            "marque": m.marque,
            "modele": m.modele,
            "numero_serie": m.numero_serie,
            "date_acquisition": m.date_acquisition,
            "date_fin_vie": m.date_fin_vie,
            "statut": m.statut,
            "description": m.description,
            "duree_vie_annees": m.duree_vie_annees,
            "impact_fabrication_kg": m.impact_fabrication_kg,
            "consommation_kwh_annuelle": m.consommation_kwh_annuelle,
            "impact_usage_annuel_kg": m.impact_usage_annuel_kg,
            "user_id": m.user_id,
            "equipe_id": m.equipe_id,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
            "user": m.user,
            **_compute_materiel_properties(m),
        }
        items.append(m_dict)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=MaterielResponse, status_code=status.HTTP_201_CREATED)
async def create_materiel(
    materiel_data: MaterielCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_create_materiel)],
):
    """
    Crée un nouveau matériel.

    Si l'impact fabrication ou la consommation ne sont pas fournis,
    les valeurs standards ADEME sont utilisées.
    """
    # Vérifie le numéro de série unique
    if materiel_data.numero_serie:
        stmt = select(Materiel).where(Materiel.numero_serie == materiel_data.numero_serie)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un matériel avec ce numéro de série existe déjà",
            )

    # Vérifie l'utilisateur si spécifié
    if materiel_data.user_id:
        user_stmt = select(User).where(
            User.id == materiel_data.user_id,
            User.deleted_at.is_(None),
        )
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé",
            )

    # Vérifie l'équipe si spécifiée
    if materiel_data.equipe_id:
        equipe_stmt = select(Equipe).where(
            Equipe.id == materiel_data.equipe_id,
            Equipe.deleted_at.is_(None),
        )
        equipe = (await db.execute(equipe_stmt)).scalar_one_or_none()
        if not equipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Équipe non trouvée",
            )

    # Calcule l'impact CO2
    impact_fab, conso_kwh, impact_usage = await CO2Service.calculer_impact_materiel(
        db,
        materiel_data.type_materiel,
        materiel_data.consommation_kwh_annuelle,
        materiel_data.impact_fabrication_kg,
    )

    # Crée le matériel
    materiel = Materiel(
        type_materiel=materiel_data.type_materiel,
        marque=materiel_data.marque,
        modele=materiel_data.modele,
        numero_serie=materiel_data.numero_serie,
        date_acquisition=materiel_data.date_acquisition,
        date_fin_vie=materiel_data.date_fin_vie,
        statut=materiel_data.statut,
        description=materiel_data.description,
        duree_vie_annees=materiel_data.duree_vie_annees,
        user_id=materiel_data.user_id,
        equipe_id=materiel_data.equipe_id,
        impact_fabrication_kg=impact_fab,
        consommation_kwh_annuelle=conso_kwh,
        impact_usage_annuel_kg=impact_usage,
    )

    db.add(materiel)
    await db.commit()
    await db.refresh(materiel)

    # Retourne avec propriétés calculées
    response = MaterielResponse(
        **materiel.__dict__,
        **_compute_materiel_properties(materiel),
    )
    return response


@router.get("/types")
async def list_types_materiel(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_materiel)],
):
    """
    Liste tous les types de matériel avec leurs facteurs d'émission standards.
    """
    types = await CO2Service.get_all_types_materiel(db)
    return {"types_materiel": types}


@router.get("/statuts")
async def list_statuts_materiel(
    _user: Annotated[User, Depends(can_read_materiel)],
):
    """
    Liste tous les statuts de matériel possibles.
    """
    return {
        "statuts": [
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in StatutMateriel
        ]
    }


@router.get("/stats/summary")
async def get_materiel_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_materiel)],
    equipe_id: UUID | None = None,
    statut: StatutMateriel | None = None,
):
    """
    Retourne les statistiques du parc matériel.
    """
    # Base query
    stmt = select(Materiel).where(Materiel.deleted_at.is_(None))

    if equipe_id:
        stmt = stmt.where(Materiel.equipe_id == equipe_id)

    if statut:
        stmt = stmt.where(Materiel.statut == statut)

    result = await db.execute(stmt)
    materiels = result.scalars().all()

    # Calcul des statistiques
    total_materiels = len(materiels)

    if total_materiels == 0:
        return {
            "total_materiels": 0,
            "total_impact_fabrication_kg": 0,
            "total_impact_usage_annuel_kg": 0,
            "total_impact_amorti_annuel_kg": 0,
            "materiels_par_type": {},
            "materiels_par_statut": {},
            "age_moyen_annees": 0,
        }

    total_impact_fab = sum(m.impact_fabrication_kg for m in materiels)
    total_impact_usage = sum(m.impact_usage_annuel_kg for m in materiels)

    # Impact amorti annuel total
    total_impact_amorti = sum(
        (m.impact_fabrication_kg / m.duree_vie_annees) + m.impact_usage_annuel_kg
        for m in materiels
    )

    # Par type
    materiels_par_type: dict[str, int] = {}
    for m in materiels:
        type_str = m.type_materiel.value if hasattr(m.type_materiel, 'value') else m.type_materiel
        materiels_par_type[type_str] = materiels_par_type.get(type_str, 0) + 1

    # Par statut
    materiels_par_statut: dict[str, int] = {}
    for m in materiels:
        statut_str = m.statut.value if hasattr(m.statut, 'value') else m.statut
        materiels_par_statut[statut_str] = materiels_par_statut.get(statut_str, 0) + 1

    # Âge moyen
    today = date.today()
    ages = [(today - m.date_acquisition).days / 365.25 for m in materiels]
    age_moyen = sum(ages) / len(ages) if ages else 0

    return {
        "total_materiels": total_materiels,
        "total_impact_fabrication_kg": float(total_impact_fab),
        "total_impact_usage_annuel_kg": float(total_impact_usage),
        "total_impact_amorti_annuel_kg": float(total_impact_amorti),
        "materiels_par_type": materiels_par_type,
        "materiels_par_statut": materiels_par_statut,
        "age_moyen_annees": round(age_moyen, 1),
    }


@router.get("/stats/renouvellement")
async def get_materiel_renouvellement(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_materiel)],
    annees_projection: int = Query(3, ge=1, le=10),
):
    """
    Retourne les projections de renouvellement du parc.
    """
    stmt = select(Materiel).where(
        Materiel.deleted_at.is_(None),
        Materiel.statut == StatutMateriel.EN_SERVICE,
    )
    result = await db.execute(stmt)
    materiels = result.scalars().all()

    today = date.today()
    projections = {}

    for year_offset in range(annees_projection + 1):
        year = today.year + year_offset
        count = 0
        impact = Decimal("0")

        for m in materiels:
            # Date de fin de vie prévue
            fin_vie = m.date_fin_vie or date(
                m.date_acquisition.year + m.duree_vie_annees,
                m.date_acquisition.month,
                m.date_acquisition.day,
            )
            if fin_vie.year == year:
                count += 1
                impact += m.impact_fabrication_kg

        projections[str(year)] = {
            "materiels_a_renouveler": count,
            "impact_renouvellement_kg": float(impact),
        }

    return {"projections": projections}


@router.get("/{materiel_id}", response_model=MaterielWithUser)
async def get_materiel(
    materiel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_materiel)],
):
    """
    Récupère un matériel par son ID.
    """
    stmt = (
        select(Materiel)
        .where(Materiel.id == materiel_id, Materiel.deleted_at.is_(None))
        .options(selectinload(Materiel.user))
    )
    materiel = (await db.execute(stmt)).scalar_one_or_none()

    if not materiel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matériel non trouvé",
        )

    # Retourne avec propriétés calculées
    return {
        **materiel.__dict__,
        **_compute_materiel_properties(materiel),
        "user": materiel.user,
    }


@router.put("/{materiel_id}", response_model=MaterielResponse)
async def update_materiel(
    materiel_id: UUID,
    materiel_data: MaterielUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_materiel)],
):
    """
    Met à jour un matériel.

    Si le type, la consommation ou l'impact fabrication changent,
    l'impact usage est recalculé.
    """
    stmt = select(Materiel).where(Materiel.id == materiel_id, Materiel.deleted_at.is_(None))
    materiel = (await db.execute(stmt)).scalar_one_or_none()

    if not materiel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matériel non trouvé",
        )

    update_data = materiel_data.model_dump(exclude_unset=True)

    # Vérifie le numéro de série unique si modifié
    if "numero_serie" in update_data and update_data["numero_serie"]:
        if update_data["numero_serie"] != materiel.numero_serie:
            ns_stmt = select(Materiel).where(
                Materiel.numero_serie == update_data["numero_serie"]
            )
            existing = (await db.execute(ns_stmt)).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Un matériel avec ce numéro de série existe déjà",
                )

    # Vérifie l'utilisateur si modifié
    if "user_id" in update_data and update_data["user_id"]:
        user_stmt = select(User).where(
            User.id == update_data["user_id"],
            User.deleted_at.is_(None),
        )
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé",
            )

    # Vérifie l'équipe si modifiée
    if "equipe_id" in update_data and update_data["equipe_id"]:
        equipe_stmt = select(Equipe).where(
            Equipe.id == update_data["equipe_id"],
            Equipe.deleted_at.is_(None),
        )
        equipe = (await db.execute(equipe_stmt)).scalar_one_or_none()
        if not equipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Équipe non trouvée",
            )

    # Met à jour les champs
    for field, value in update_data.items():
        setattr(materiel, field, value)

    # Recalcule l'impact si nécessaire
    if any(k in update_data for k in ["type_materiel", "consommation_kwh_annuelle", "impact_fabrication_kg"]):
        impact_fab, conso_kwh, impact_usage = await CO2Service.calculer_impact_materiel(
            db,
            materiel.type_materiel,
            materiel.consommation_kwh_annuelle,
            materiel.impact_fabrication_kg,
        )
        materiel.impact_usage_annuel_kg = impact_usage

    await db.commit()
    await db.refresh(materiel)

    return MaterielResponse(
        **materiel.__dict__,
        **_compute_materiel_properties(materiel),
    )


@router.delete("/{materiel_id}", response_model=MessageResponse)
async def delete_materiel(
    materiel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_delete_materiel)],
):
    """
    Supprime un matériel (soft delete).
    """
    stmt = select(Materiel).where(Materiel.id == materiel_id, Materiel.deleted_at.is_(None))
    materiel = (await db.execute(stmt)).scalar_one_or_none()

    if not materiel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matériel non trouvé",
        )

    # Soft delete
    materiel.deleted_at = datetime.now(UTC)
    await db.commit()

    return MessageResponse(message="Matériel supprimé avec succès")


@router.post("/{materiel_id}/mettre-au-rebut", response_model=MaterielResponse)
async def mettre_au_rebut(
    materiel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_materiel)],
):
    """
    Met un matériel au rebut (change son statut et définit la date de fin de vie).
    """
    stmt = select(Materiel).where(Materiel.id == materiel_id, Materiel.deleted_at.is_(None))
    materiel = (await db.execute(stmt)).scalar_one_or_none()

    if not materiel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matériel non trouvé",
        )

    if materiel.statut == StatutMateriel.MIS_AU_REBUT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce matériel est déjà mis au rebut",
        )

    materiel.statut = StatutMateriel.MIS_AU_REBUT
    materiel.date_fin_vie = date.today()
    materiel.user_id = None  # Détache l'utilisateur

    await db.commit()
    await db.refresh(materiel)

    return MaterielResponse(
        **materiel.__dict__,
        **_compute_materiel_properties(materiel),
    )
