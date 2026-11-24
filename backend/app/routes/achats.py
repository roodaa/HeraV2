"""Routes de gestion des achats."""

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
from app.models.achat import Achat
from app.models.equipe import Equipe
from app.models.role import PermissionCodes
from app.schemas import MessageResponse, PaginatedResponse
from app.schemas.achat import (
    AchatCreate,
    AchatResponse,
    AchatUpdate,
    AchatWithUser,
)
from app.services.co2_service import CO2Service

router = APIRouter()

# Vérificateurs de permissions
can_read_achats = PermissionChecker([PermissionCodes.ACHATS_READ])
can_create_achats = PermissionChecker([PermissionCodes.ACHATS_CREATE])
can_update_achats = PermissionChecker([PermissionCodes.ACHATS_UPDATE])
can_delete_achats = PermissionChecker([PermissionCodes.ACHATS_DELETE])


@router.get("", response_model=PaginatedResponse[AchatWithUser])
async def list_achats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_achats)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    code_nacres: str | None = None,
    categorie: str | None = None,
    equipe_id: UUID | None = None,
    user_id: UUID | None = None,
    date_debut: str | None = None,
    date_fin: str | None = None,
    montant_min: float | None = None,
    montant_max: float | None = None,
):
    """
    Liste les achats avec pagination et filtres.

    - **search**: Recherche dans la description
    - **code_nacres**: Filtre par code NACRES
    - **categorie**: Filtre par catégorie
    - **equipe_id**: Filtre par équipe
    - **user_id**: Filtre par utilisateur
    - **date_debut/date_fin**: Filtre par période
    - **montant_min/montant_max**: Filtre par montant
    """
    # Construction de la requête de base
    stmt = (
        select(Achat)
        .where(Achat.deleted_at.is_(None))
        .options(selectinload(Achat.user))
    )

    # Filtres
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(Achat.description.ilike(search_term))

    if code_nacres:
        stmt = stmt.where(Achat.code_nacres == code_nacres)

    if categorie:
        stmt = stmt.where(Achat.categorie == categorie)

    if equipe_id:
        stmt = stmt.where(Achat.equipe_id == equipe_id)

    if user_id:
        stmt = stmt.where(Achat.user_id == user_id)

    if date_debut:
        stmt = stmt.where(Achat.date_achat >= date_debut)

    if date_fin:
        stmt = stmt.where(Achat.date_achat <= date_fin)

    if montant_min is not None:
        stmt = stmt.where(Achat.montant_euros >= montant_min)

    if montant_max is not None:
        stmt = stmt.where(Achat.montant_euros <= montant_max)

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination et tri
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(Achat.date_achat.desc())

    result = await db.execute(stmt)
    achats = result.scalars().all()

    return PaginatedResponse(
        items=achats,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=AchatResponse, status_code=status.HTTP_201_CREATED)
async def create_achat(
    achat_data: AchatCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(can_create_achats)],
):
    """
    Crée un nouvel achat.

    Le calcul de l'impact CO2 est automatique basé sur le code NACRES.
    """
    # Vérifie que l'équipe existe si spécifiée
    if achat_data.equipe_id:
        equipe_stmt = select(Equipe).where(
            Equipe.id == achat_data.equipe_id,
            Equipe.deleted_at.is_(None),
        )
        equipe = (await db.execute(equipe_stmt)).scalar_one_or_none()
        if not equipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Équipe non trouvée",
            )

    # Calcule l'impact CO2
    impact_co2, facteur = await CO2Service.calculer_impact_achat(
        db,
        achat_data.montant_euros,
        achat_data.code_nacres,
    )

    # Crée l'achat
    achat = Achat(
        date_achat=achat_data.date_achat,
        description=achat_data.description,
        montant_euros=achat_data.montant_euros,
        code_nacres=achat_data.code_nacres,
        categorie=achat_data.categorie,
        commentaire=achat_data.commentaire,
        user_id=current_user.id,
        equipe_id=achat_data.equipe_id,
        impact_co2_kg=impact_co2,
        facteur_emission=facteur,
    )

    db.add(achat)
    await db.commit()
    await db.refresh(achat)

    return achat


@router.get("/codes-nacres")
async def list_codes_nacres(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_achats)],
):
    """
    Liste tous les codes NACRES disponibles avec leurs facteurs d'émission.
    """
    codes = await CO2Service.get_all_codes_nacres(db)
    return {"codes_nacres": codes}


@router.get("/categories")
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_achats)],
):
    """
    Liste toutes les catégories d'achats existantes.
    """
    stmt = (
        select(Achat.categorie)
        .where(Achat.deleted_at.is_(None), Achat.categorie.isnot(None))
        .distinct()
        .order_by(Achat.categorie)
    )
    result = await db.execute(stmt)
    categories = [row[0] for row in result.all()]

    return {"categories": categories}


@router.get("/stats/summary")
async def get_achats_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_achats)],
    year: int | None = None,
    equipe_id: UUID | None = None,
):
    """
    Retourne les statistiques des achats.
    """
    # Base query
    stmt = select(Achat).where(Achat.deleted_at.is_(None))

    if year:
        stmt = stmt.where(func.extract("year", Achat.date_achat) == year)

    if equipe_id:
        stmt = stmt.where(Achat.equipe_id == equipe_id)

    result = await db.execute(stmt)
    achats = result.scalars().all()

    # Calcul des statistiques
    total_achats = len(achats)
    total_montant = sum(a.montant_euros for a in achats)
    total_impact = sum(a.impact_co2_kg for a in achats)

    # Par catégorie
    achats_par_categorie: dict[str, int] = {}
    impact_par_categorie: dict[str, Decimal] = {}

    for achat in achats:
        cat = achat.categorie or "Non catégorisé"
        achats_par_categorie[cat] = achats_par_categorie.get(cat, 0) + 1
        impact_par_categorie[cat] = impact_par_categorie.get(cat, Decimal("0")) + achat.impact_co2_kg

    # Par code NACRES
    achats_par_nacres: dict[str, int] = {}
    impact_par_nacres: dict[str, Decimal] = {}

    for achat in achats:
        code = achat.code_nacres or "Sans code"
        achats_par_nacres[code] = achats_par_nacres.get(code, 0) + 1
        impact_par_nacres[code] = impact_par_nacres.get(code, Decimal("0")) + achat.impact_co2_kg

    return {
        "total_achats": total_achats,
        "total_montant_euros": float(total_montant),
        "total_impact_co2_kg": float(total_impact),
        "achats_par_categorie": achats_par_categorie,
        "impact_par_categorie": {k: float(v) for k, v in impact_par_categorie.items()},
        "achats_par_nacres": achats_par_nacres,
        "impact_par_nacres": {k: float(v) for k, v in impact_par_nacres.items()},
    }


@router.get("/{achat_id}", response_model=AchatWithUser)
async def get_achat(
    achat_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_achats)],
):
    """
    Récupère un achat par son ID.
    """
    stmt = (
        select(Achat)
        .where(Achat.id == achat_id, Achat.deleted_at.is_(None))
        .options(selectinload(Achat.user))
    )
    achat = (await db.execute(stmt)).scalar_one_or_none()

    if not achat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achat non trouvé",
        )

    return achat


@router.put("/{achat_id}", response_model=AchatResponse)
async def update_achat(
    achat_id: UUID,
    achat_data: AchatUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_achats)],
):
    """
    Met à jour un achat.

    Si le montant ou le code NACRES change, l'impact CO2 est recalculé.
    """
    stmt = select(Achat).where(Achat.id == achat_id, Achat.deleted_at.is_(None))
    achat = (await db.execute(stmt)).scalar_one_or_none()

    if not achat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achat non trouvé",
        )

    # Vérifie l'équipe si modifiée
    update_data = achat_data.model_dump(exclude_unset=True)

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
        setattr(achat, field, value)

    # Recalcule l'impact CO2 si nécessaire
    if "montant_euros" in update_data or "code_nacres" in update_data:
        impact_co2, facteur = await CO2Service.calculer_impact_achat(
            db,
            achat.montant_euros,
            achat.code_nacres,
        )
        achat.impact_co2_kg = impact_co2
        achat.facteur_emission = facteur

    await db.commit()
    await db.refresh(achat)

    return achat


@router.delete("/{achat_id}", response_model=MessageResponse)
async def delete_achat(
    achat_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_delete_achats)],
):
    """
    Supprime un achat (soft delete).
    """
    stmt = select(Achat).where(Achat.id == achat_id, Achat.deleted_at.is_(None))
    achat = (await db.execute(stmt)).scalar_one_or_none()

    if not achat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achat non trouvé",
        )

    # Soft delete
    achat.deleted_at = datetime.now(UTC)
    await db.commit()

    return MessageResponse(message="Achat supprimé avec succès")
