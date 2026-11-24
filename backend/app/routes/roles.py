"""Routes de gestion des rôles."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.database import get_db
from app.middleware.auth import PermissionChecker
from app.models import Permission, Role, User
from app.models.role import PermissionCodes
from app.schemas import (
    MessageResponse,
    PaginatedResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    RoleWithPermissions,
    UserMinimal,
)

router = APIRouter()

# Vérificateurs de permissions
can_read_roles = PermissionChecker([PermissionCodes.ROLES_READ])
can_create_roles = PermissionChecker([PermissionCodes.ROLES_CREATE])
can_update_roles = PermissionChecker([PermissionCodes.ROLES_UPDATE])
can_delete_roles = PermissionChecker([PermissionCodes.ROLES_DELETE])


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_roles)],
):
    """
    Liste tous les rôles.
    """
    stmt = select(Role).order_by(Role.name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=RoleWithPermissions, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_create_roles)],
):
    """
    Crée un nouveau rôle.
    """
    # Vérifie si le code existe déjà
    stmt = select(Role).where(Role.code == role_data.code)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un rôle avec ce code existe déjà",
        )

    # Récupère les permissions
    permissions = []
    if role_data.permission_ids:
        stmt = select(Permission).where(Permission.id.in_(role_data.permission_ids))
        result = await db.execute(stmt)
        permissions = list(result.scalars().all())

        if len(permissions) != len(role_data.permission_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Certaines permissions n'existent pas",
            )

    # Crée le rôle
    role = Role(
        code=role_data.code,
        name=role_data.name,
        description=role_data.description,
        permissions=permissions,
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return role


@router.get("/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_roles)],
):
    """
    Récupère un rôle par son ID avec ses permissions.
    """
    stmt = (
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    role = (await db.execute(stmt)).scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé",
        )

    return role


@router.put("/{role_id}", response_model=RoleWithPermissions)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_update_roles)],
):
    """
    Met à jour un rôle.
    """
    stmt = (
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    role = (await db.execute(stmt)).scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé",
        )

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les rôles système ne peuvent pas être modifiés",
        )

    # Met à jour les champs simples
    if role_data.name is not None:
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description

    # Met à jour les permissions si fournies
    if role_data.permission_ids is not None:
        stmt = select(Permission).where(Permission.id.in_(role_data.permission_ids))
        result = await db.execute(stmt)
        permissions = list(result.scalars().all())

        if len(permissions) != len(role_data.permission_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Certaines permissions n'existent pas",
            )

        role.permissions = permissions

    await db.commit()
    await db.refresh(role)

    return role


@router.delete("/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_delete_roles)],
):
    """
    Supprime un rôle.
    """
    stmt = select(Role).where(Role.id == role_id)
    role = (await db.execute(stmt)).scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé",
        )

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les rôles système ne peuvent pas être supprimés",
        )

    await db.delete(role)
    await db.commit()

    return MessageResponse(message="Rôle supprimé avec succès")


@router.post("/{role_id}/duplicate", response_model=RoleWithPermissions)
async def duplicate_role(
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_create_roles)],
    new_code: str = Query(..., min_length=1, max_length=50),
    new_name: str = Query(..., min_length=1, max_length=100),
):
    """
    Duplique un rôle existant avec un nouveau code et nom.
    """
    stmt = (
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permissions))
    )
    original_role = (await db.execute(stmt)).scalar_one_or_none()

    if not original_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé",
        )

    # Vérifie que le nouveau code n'existe pas
    stmt = select(Role).where(Role.code == new_code)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un rôle avec ce code existe déjà",
        )

    # Crée le nouveau rôle
    new_role = Role(
        code=new_code,
        name=new_name,
        description=original_role.description,
        permissions=list(original_role.permissions),
    )

    db.add(new_role)
    await db.commit()
    await db.refresh(new_role)

    return new_role


@router.get("/{role_id}/users", response_model=PaginatedResponse[UserMinimal])
async def get_role_users(
    role_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(can_read_roles)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Liste les utilisateurs ayant ce rôle.
    """
    # Vérifie que le rôle existe
    stmt = select(Role).where(Role.id == role_id)
    role = (await db.execute(stmt)).scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé",
        )

    # Récupère les utilisateurs
    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.id == role_id, User.deleted_at.is_(None))
    )

    # Compte total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.order_by(User.last_name, User.first_name)

    result = await db.execute(stmt)
    users = result.scalars().all()

    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
