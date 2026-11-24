"""Routes de gestion des permissions."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.middleware.auth import CurrentUser
from app.models import Permission
from app.schemas import PermissionResponse, PermissionsByModule

router = APIRouter()


@router.get("", response_model=list[PermissionResponse])
async def list_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
):
    """
    Liste toutes les permissions.
    """
    stmt = select(Permission).order_by(Permission.module, Permission.code)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/modules", response_model=list[PermissionsByModule])
async def list_permissions_by_module(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
):
    """
    Liste les permissions groupées par module.
    """
    stmt = select(Permission).order_by(Permission.module, Permission.code)
    result = await db.execute(stmt)
    permissions = result.scalars().all()

    # Groupe par module
    modules_dict: dict[str, list[Permission]] = {}
    for permission in permissions:
        if permission.module not in modules_dict:
            modules_dict[permission.module] = []
        modules_dict[permission.module].append(permission)

    return [
        PermissionsByModule(module=module, permissions=perms)
        for module, perms in modules_dict.items()
    ]
