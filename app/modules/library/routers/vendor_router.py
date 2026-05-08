import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    VendorCreate,
    VendorRead,
    VendorStatus,
    VendorUpdate,
)
from app.modules.library.services.vendor_service import VendorService

router = APIRouter()


async def get_vendor_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorService:
    return VendorService(VendorRepository(session))


@router.get("", response_model=DataResponse[list[VendorRead]])
async def list_vendors(
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
    status_filter: VendorStatus | None = None,
) -> DataResponse[list[VendorRead]]:
    vendors = await service.list(status=status_filter)
    return DataResponse(data=[VendorRead.model_validate(v) for v in vendors])


@router.get("/{slug}", response_model=DataResponse[VendorRead])
async def get_vendor(
    slug: str,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[VendorRead]:
    vendor = await service.get_by_slug(slug)
    return DataResponse(data=VendorRead.model_validate(vendor))


@router.post("", response_model=DataResponse[VendorRead], status_code=status.HTTP_201_CREATED)
async def create_vendor(
    body: VendorCreate,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[VendorRead]:
    vendor = await service.create(body, current_user_id=user.id)
    return DataResponse(data=VendorRead.model_validate(vendor))


@router.patch("/{vendor_id}", response_model=DataResponse[VendorRead])
async def update_vendor(
    vendor_id: uuid.UUID,
    body: VendorUpdate,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[VendorRead]:
    vendor = await service.update(vendor_id, body)
    return DataResponse(data=VendorRead.model_validate(vendor))


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: uuid.UUID,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(vendor_id)
