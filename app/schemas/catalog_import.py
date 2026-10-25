"""JSON que sale de GET /products/export en proyecto-leidy (u otra tienda
hermana) y entra en POST /products/import de SeizeMB."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl

from app.models.color import Color


class CatalogImportImage(BaseModel):
    url: HttpUrl
    storage_path: str | None = None
    color: Color | None = None
    position: int = 0


class CatalogImportProduct(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    height_cm: Decimal | None = Field(default=None, gt=0, decimal_places=1)
    width_cm: Decimal | None = Field(default=None, gt=0, decimal_places=1)
    compartments: int | None = Field(default=None, ge=0)
    material: str | None = Field(default=None, min_length=2, max_length=100)
    in_stock: bool = True
    category: str = Field(..., min_length=2, max_length=100)
    colors: list[Color] = Field(default_factory=list)
    images: list[CatalogImportImage] = Field(default_factory=list)


class CatalogImportCategory(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class CatalogImport(BaseModel):
    exported_at: datetime | None = None
    source: str | None = None
    categories: list[CatalogImportCategory] = Field(default_factory=list)
    products: list[CatalogImportProduct] = Field(default_factory=list)


class CatalogImportImageError(BaseModel):
    product: str
    url: str
    detail: str


class CatalogImportProductResult(BaseModel):
    name: str
    id: int
    images_copied: int
    skipped: bool = False


class CatalogImportResult(BaseModel):
    created_categories: int
    created_products: int
    skipped_products: int
    images_copied: int
    products: list[CatalogImportProductResult]
    image_errors: list[CatalogImportImageError]
