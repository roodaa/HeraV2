"""Routes de gestion des utilisateurs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.database import get_db
from app.middleware.auth import CurrentUser, PermissionChecker, require_permission
from app.models import Role, User
from app.models.role import PermissionCodes
from app.schemas import (
    MessageResponse,
    PaginatedResponse,
    RoleAssign,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithRoles,
)
from app.services.auth_service import AuthService

router = APIRouter()

# Vérificateurs de permissions
can_read_users = PermissionChecker([PermissionCodes.USERS_READ])
can_create_users = PermissionChecker([PermissionCodes.USERS_CREATE])
can_update_users = PermissionChecker([PermissionCodes.USERS_UPDATE])
can_delete_users = PermissionChecker([PermissionCodes.USERS_DELETE])
can_manage_roles = PermissionChecker([PermissionCodes.USERS_MANAGE_ROLES])


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_users)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    is_active: bool | None = None,
    equipe_id: UUID | None = None,
):
    """
    Liste les utilisateurs avec pagination et filtres.
    """
    # Construction de la requête de base
    stmt = select(User).where(User.deleted_at.is_(None))

    # Filtres
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            (User.email.ilike(search_term))
            | (User.first_name.ilike(search_term))
            | (User.last_name.ilike(search_term))
        )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    if equipe_id:
        stmt = stmt.where(User.equipe_id == equipe_id)

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(User.created_at.desc())

    result = await db.execute(stmt)
    users = result.scalars().all()

    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_create_users)],
):
    """
    Crée un nouvel utilisateur (authentification locale).
    """
    # Vérifie si l'email existe déjà
    stmt = select(User).where(User.email == user_data.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur avec cet email existe déjà",
        )

    # Crée l'utilisateur
    user = User(
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        hashed_password=AuthService.hash_password(user_data.password),
        auth_provider="local",
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_users)],
):
    """
    Récupère un utilisateur par son ID.
    """
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.roles))
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_users)],
):
    """
    Met à jour un utilisateur.
    """
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    # Met à jour les champs fournis
    update_data = user_data.model_dump(exclude_unset=True)

    # Vérifie si le nouvel email n'est pas déjà utilisé
    if "email" in update_data and update_data["email"] != user.email:
        stmt = select(User).where(User.email == update_data["email"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un utilisateur avec cet email existe déjà",
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_delete_users)],
):
    """
    Désactive un utilisateur (soft delete).
    """
    from datetime import UTC, datetime

    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    # Soft delete
    user.deleted_at = datetime.now(UTC)
    user.is_active = False

    await db.commit()

    return MessageResponse(message="Utilisateur désactivé avec succès")


@router.post("/{user_id}/roles", response_model=MessageResponse)
async def assign_role(
    user_id: UUID,
    role_data: RoleAssign,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_manage_roles)],
):
    """
    Attribue un rôle à un utilisateur.
    """
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.roles))
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    # Vérifie que le rôle existe
    role_stmt = select(Role).where(Role.id == role_data.role_id)
    role = (await db.execute(role_stmt)).scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé",
        )

    # Vérifie si le rôle est déjà attribué
    if role in user.roles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce rôle est déjà attribué à l'utilisateur",
        )

    user.roles.append(role)
    await db.commit()

    return MessageResponse(message=f"Rôle '{role.name}' attribué avec succès")


@router.delete("/{user_id}/roles/{role_id}", response_model=MessageResponse)
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_manage_roles)],
):
    """
    Retire un rôle à un utilisateur.
    """
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(selectinload(User.roles))
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé",
        )

    # Trouve le rôle dans la liste de l'utilisateur
    role_to_remove = None
    for role in user.roles:
        if role.id == role_id:
            role_to_remove = role
            break

    if not role_to_remove:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ce rôle n'est pas attribué à l'utilisateur",
        )

    user.roles.remove(role_to_remove)
    await db.commit()

    return MessageResponse(message=f"Rôle '{role_to_remove.name}' retiré avec succès")
