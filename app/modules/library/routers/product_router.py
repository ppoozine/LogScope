import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.modules.library.services.product_service import ProductService

router = APIRouter()


async def get_product_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductService:
    return ProductService(ProductRepository(session), VendorRepository(session))


@router.get(
    "/vendors/{vendor_slug}/products",
    response_model=DataResponse[list[ProductRead]],
)
async def list_products(
    vendor_slug: str,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[ProductRead]]:
    products = await service.list_by_vendor_slug(vendor_slug)
    return DataResponse(data=[ProductRead.model_validate(p) for p in products])


@router.get(
    "/vendors/{vendor_slug}/products/{product_slug}",
    response_model=DataResponse[ProductRead],
)
async def get_product(
    vendor_slug: str,
    product_slug: str,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ProductRead]:
    product = await service.get_by_vendor_and_slug(vendor_slug, product_slug)
    return DataResponse(data=ProductRead.model_validate(product))


@router.post(
    "/vendors/{vendor_slug}/products",
    response_model=DataResponse[ProductRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    vendor_slug: str,
    body: ProductCreate,
    service: Annotated[ProductService, Depends(get_product_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[ProductRead]:
    product = await service.create(vendor_slug, body, current_user_id=user.id)
    return DataResponse(data=ProductRead.model_validate(product))


@router.patch(
    "/products/{product_id}",
    response_model=DataResponse[ProductRead],
)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ProductRead]:
    product = await service.update(product_id, body)
    return DataResponse(data=ProductRead.model_validate(product))


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(
    product_id: uuid.UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(product_id)
