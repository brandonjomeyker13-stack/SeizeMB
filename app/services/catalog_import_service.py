"""Trae un catálogo exportado (Leidy u otra tienda) a SeizeMB.

Las fotos NO se copian como URL: se bajan y se suben al bucket de esta
tienda. Después el origen puede apagarse sin romper el catálogo.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.remote_image import RemoteImageError, download_public_image
from app.core.storage import upload_product_image_bytes
from app.models.color import Color
from app.repositories import category_repository, product_repository
from app.schemas.catalog_import import (
    CatalogImport,
    CatalogImportImageError,
    CatalogImportProduct,
    CatalogImportProductResult,
    CatalogImportResult,
)
from app.services import category_service, product_service

logger = logging.getLogger("seizemb.catalog_import")


def _asegurar_categoria(db: Session, nombre: str) -> tuple[int, bool]:
    """Devuelve (id, creada). Reusa si ya existe, sin importar mayúsculas."""
    existente = category_repository.get_by_name_ci(db, nombre)
    if existente is not None:
        return existente.id, False
    creada = category_service.create_category(db, name=nombre.strip())
    return creada.id, True


def _copiar_imagen(
    url: str, product_id: int
) -> tuple[str, str] | CatalogImportImageError:
    """Baja la URL y la sube al Storage de SeizeMB. Devuelve (url, path)
    o el error para reportarlo sin abortar el resto del producto."""
    try:
        contents = download_public_image(url)
        subida = upload_product_image_bytes(contents, product_id)
        return subida.url, subida.path
    except RemoteImageError as exc:
        return CatalogImportImageError(product="", url=url, detail=str(exc))
    except HTTPException as exc:
        detalle = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return CatalogImportImageError(product="", url=url, detail=detalle)
    except Exception:
        logger.exception("Falló al copiar la foto %s al producto %s", url, product_id)
        return CatalogImportImageError(
            product="",
            url=url,
            detail="No se pudo copiar esta foto al storage de SeizeMB.",
        )


def _importar_producto(
    db: Session,
    item: CatalogImportProduct,
    category_id: int,
) -> tuple[CatalogImportProductResult, list[CatalogImportImageError]]:
    existente = product_repository.get_by_name_ci(db, item.name)
    if existente is not None:
        return (
            CatalogImportProductResult(
                name=existente.name,
                id=existente.id,
                images_copied=0,
                skipped=True,
            ),
            [],
        )

    producto = product_service.create_product(
        db,
        name=item.name,
        price=item.price,
        category_id=category_id,
        height_cm=item.height_cm,
        width_cm=item.width_cm,
        compartments=item.compartments,
        material=item.material,
        cost=item.cost,
        in_stock=item.in_stock,
    )
    if item.colors:
        producto = product_service.set_product_colors(db, producto.id, item.colors)

    por_color: dict[Color | None, list] = defaultdict(list)
    for imagen in sorted(item.images, key=lambda i: i.position):
        por_color[imagen.color].append(imagen)

    copiadas = 0
    errores: list[CatalogImportImageError] = []
    for color, grupo in por_color.items():
        destinos: list[tuple[str, str | None]] = []
        for imagen in grupo[: product_service.MAX_PRODUCT_IMAGES]:
            resultado = _copiar_imagen(str(imagen.url), producto.id)
            if isinstance(resultado, CatalogImportImageError):
                resultado.product = producto.name
                errores.append(resultado)
                continue
            destinos.append(resultado)
        if destinos:
            product_service.add_product_images(db, producto.id, destinos, color)
            copiadas += len(destinos)
        extras = grupo[product_service.MAX_PRODUCT_IMAGES :]
        for extra in extras:
            errores.append(
                CatalogImportImageError(
                    product=producto.name,
                    url=str(extra.url),
                    detail=(
                        f"Este color ya tiene el tope de "
                        f"{product_service.MAX_PRODUCT_IMAGES} fotos."
                    ),
                )
            )

    return (
        CatalogImportProductResult(
            name=producto.name,
            id=producto.id,
            images_copied=copiadas,
        ),
        errores,
    )


def import_catalog(db: Session, catalogo: CatalogImport) -> CatalogImportResult:
    creadas = 0
    for categoria in catalogo.categories:
        _, nueva = _asegurar_categoria(db, categoria.name)
        if nueva:
            creadas += 1

    resultados: list[CatalogImportProductResult] = []
    errores: list[CatalogImportImageError] = []
    for item in catalogo.products:
        category_id, nueva = _asegurar_categoria(db, item.category)
        if nueva:
            creadas += 1
        resultado, fallos = _importar_producto(db, item, category_id)
        resultados.append(resultado)
        errores.extend(fallos)

    return CatalogImportResult(
        created_categories=creadas,
        created_products=sum(1 for r in resultados if not r.skipped),
        skipped_products=sum(1 for r in resultados if r.skipped),
        images_copied=sum(r.images_copied for r in resultados),
        products=resultados,
        image_errors=errores,
    )
