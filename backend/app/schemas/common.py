"""Schémas communs partagés."""

from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Schéma de base avec configuration commune."""

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Réponse paginée générique."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginationParams(BaseModel):
    """Paramètres de pagination."""

    page: int = 1
    page_size: int = 20


class MessageResponse(BaseModel):
    """Réponse simple avec message."""

    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Réponse d'erreur."""

    detail: str
    error_code: str | None = None


class IDResponse(BaseModel):
    """Réponse avec ID."""

    id: UUID
