from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):  # noqa: UP046
    data: T


class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    data: list[T]
    total: int
    page: int
    page_size: int


class ErrorBody(BaseModel):
    code: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
