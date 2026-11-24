"""Routes de gestion des équipes."""

from datetime import UTC, datetime
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
from app.models.role import PermissionCodes
from app.schemas import MessageResponse, PaginatedResponse, UserMinimal
from app.schemas.equipe import (
    AffectUserToEquipe,
    EquipeCreate,
    EquipeResponse,
    EquipeUpdate,
    EquipeWithMembers,
)

router = APIRouter()

# Vérificateurs de permissions
can_read_equipes = PermissionChecker([PermissionCodes.EQUIPES_READ])
can_create_equipes = PermissionChecker([PermissionCodes.EQUIPES_CREATE])
can_update_equipes = PermissionChecker([PermissionCodes.EQUIPES_UPDATE])
can_delete_equipes = PermissionChecker([PermissionCodes.EQUIPES_DELETE])


@router.get("", response_model=PaginatedResponse[EquipeResponse])
async def list_equipes(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_equipes)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
):
    """
    Liste les équipes avec pagination et filtres.
    """
    # Construction de la requête de base
    stmt = select(Equipe).where(Equipe.deleted_at.is_(None))

    # Filtre de recherche
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            (Equipe.code.ilike(search_term))
            | (Equipe.name.ilike(search_term))
            | (Equipe.description.ilike(search_term))
        )

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination et tri
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(Equipe.name.asc())

    result = await db.execute(stmt)
    equipes = result.scalars().all()

    return PaginatedResponse(
        items=equipes,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=EquipeResponse, status_code=status.HTTP_201_CREATED)
async def create_equipe(
    equipe_data: EquipeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_create_equipes)],
):
    """
    Crée une nouvelle équipe.
    """
    # Vérifie si le code existe déjà
    stmt = select(Equipe).where(Equipe.code == equipe_data.code)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une équipe avec ce code existe déjà",
        )

    # Crée l'équipe
    equipe = Equipe(
        code=equipe_data.code,
        name=equipe_data.name,
        description=equipe_data.description,
    )

    db.add(equipe)
    await db.commit()
    await db.refresh(equipe)

    return equipe


@router.get("/{equipe_id}", response_model=EquipeWithMembers)
async def get_equipe(
    equipe_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_equipes)],
):
    """
    Récupère une équipe par son ID avec ses membres.
    """
    stmt = (
        select(Equipe)
        .where(Equipe.id == equipe_id, Equipe.deleted_at.is_(None))
        .options(selectinload(Equipe.members))
    )
    equipe = (await db.execute(stmt)).scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipe non trouvée",
        )

    # Filtre les membres actifs (non supprimés)
    active_members = [m for m in equipe.members if m.deleted_at is None]

    return EquipeWithMembers(
        id=equipe.id,
        code=equipe.code,
        name=equipe.name,
        description=equipe.description,
        created_at=equipe.created_at,
        updated_at=equipe.updated_at,
        members=active_members,
        member_count=len(active_members),
    )


@router.put("/{equipe_id}", response_model=EquipeResponse)
async def update_equipe(
    equipe_id: UUID,
    equipe_data: EquipeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_equipes)],
):
    """
    Met à jour une équipe.
    """
    stmt = select(Equipe).where(Equipe.id == equipe_id, Equipe.deleted_at.is_(None))
    equipe = (await db.execute(stmt)).scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipe non trouvée",
        )

    # Met à jour les champs fournis
    update_data = equipe_data.model_dump(exclude_unset=True)

    # Vérifie si le nouveau code n'est pas déjà utilisé
    if "code" in update_data and update_data["code"] != equipe.code:
        code_stmt = select(Equipe).where(Equipe.code == update_data["code"])
        existing = (await db.execute(code_stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Une équipe avec ce code existe déjà",
            )

    for field, value in update_data.items():
        setattr(equipe, field, value)

    await db.commit()
    await db.refresh(equipe)

    return equipe


@router.delete("/{equipe_id}", response_model=MessageResponse)
async def delete_equipe(
    equipe_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_delete_equipes)],
):
    """
    Supprime une équipe (soft delete).
    Les membres sont automatiquement détachés.
    """
    stmt = (
        select(Equipe)
        .where(Equipe.id == equipe_id, Equipe.deleted_at.is_(None))
        .options(selectinload(Equipe.members))
    )
    equipe = (await db.execute(stmt)).scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipe non trouvée",
        )

    # Détache tous les membres de l'équipe
    for member in equipe.members:
        member.equipe_id = None

    # Soft delete
    equipe.deleted_at = datetime.now(UTC)

    await db.commit()

    return MessageResponse(message="Équipe supprimée avec succès")


@router.post("/{equipe_id}/members", response_model=MessageResponse)
async def add_member(
    equipe_id: UUID,
    member_data: AffectUserToEquipe,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_equipes)],
):
    """
    Ajoute un utilisateur à une équipe.
    """
    # Vérifie que l'équipe existe
    equipe_stmt = select(Equipe).where(
        Equipe.id == equipe_id, Equipe.deleted_at.is_(None)
    )
    equipe = (await db.execute(equipe_stmt)).scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipe non trouvée",
        )

    # Vérifie que l'utilisateur existe
    user_stmt = select(User).where(
        User.id == member_data.user_id, User.deleted_at.is_(None)
    )
    user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    # Vérifie si l'utilisateur est déjà dans cette équipe
    if user.equipe_id == equipe_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="L'utilisateur est déjà membre de cette équipe",
        )

    # Affecte l'utilisateur à l'équipe
    user.equipe_id = equipe_id
    await db.commit()

    return MessageResponse(
        message=f"Utilisateur '{user.full_name}' ajouté à l'équipe '{equipe.name}'"
    )


@router.delete("/{equipe_id}/members/{user_id}", response_model=MessageResponse)
async def remove_member(
    equipe_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_equipes)],
):
    """
    Retire un utilisateur d'une équipe.
    """
    # Vérifie que l'équipe existe
    equipe_stmt = select(Equipe).where(
        Equipe.id == equipe_id, Equipe.deleted_at.is_(None)
    )
    equipe = (await db.execute(equipe_stmt)).scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipe non trouvée",
        )

    # Vérifie que l'utilisateur existe et appartient à cette équipe
    user_stmt = select(User).where(
        User.id == user_id,
        User.deleted_at.is_(None),
        User.equipe_id == equipe_id,
    )
    user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé ou non membre de cette équipe",
        )

    # Retire l'utilisateur de l'équipe
    user.equipe_id = None
    await db.commit()

    return MessageResponse(
        message=f"Utilisateur '{user.full_name}' retiré de l'équipe '{equipe.name}'"
    )


@router.get("/{equipe_id}/members", response_model=PaginatedResponse[UserMinimal])
async def list_equipe_members(
    equipe_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_equipes)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Liste les membres d'une équipe avec pagination.
    """
    # Vérifie que l'équipe existe
    equipe_stmt = select(Equipe).where(
        Equipe.id == equipe_id, Equipe.deleted_at.is_(None)
    )
    equipe = (await db.execute(equipe_stmt)).scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Équipe non trouvée",
        )

    # Requête pour les membres
    stmt = select(User).where(
        User.equipe_id == equipe_id,
        User.deleted_at.is_(None),
    )

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination et tri
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(User.last_name.asc(), User.first_name.asc())

    result = await db.execute(stmt)
    members = result.scalars().all()

    return PaginatedResponse(
        items=members,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
