"""Acceso a datos de Product. Solo queries, sin reglas de negocio."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.product import Product


def get_by_id(db: Session, product_id: int) -> Product | None:
    return db.query(Product).filter(Product.id == product_id).first()


def get_by_id_for_update(db: Session, product_id: int) -> Product | None:
    """Igual que get_by_id, pero bloquea la fila (SELECT ... FOR UPDATE)
    hasta que la transacción actual termine (commit/rollback).

    Úsalo SOLO dentro de un flujo donde quien llama controla el commit
    final (subida de imágenes, por ejemplo).
    """
    return (
        db.query(Product)
        .filter(Product.id == product_id)
        .with_for_update()
        .first()
    )


def get_by_name_ci(db: Session, name: str) -> Product | None:
    """Para no duplicar un producto si se importa el mismo JSON otra vez."""
    return (
        db.query(Product)
        .filter(func.lower(Product.name) == name.strip().lower())
        .first()
    )


def list_all(
    db: Session,
    skip: int = 0,
    # El tope de negocio es product_service.MAX_PRODUCTS_LISTED; este
    # default solo cubre a quien llame el repositorio sin pasarlo.
    limit: int = 1000,
    category_id: int | None = None,
) -> list[Product]:
    query = db.query(Product)
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    return query.order_by(Product.id).offset(skip).limit(limit).all()


def create(
    db: Session,
    *,
    name: str,
    price,
    category_id: int,
    # Atributos físicos: todos opcionales, se pueden completar después
    # de crear el producto.
    height_cm=None,
    width_cm=None,
    compartments: int | None = None,
    material: str | None = None,
    cost=None,
    in_stock: bool = True,
) -> Product:
    product = Product(
        name=name,
        height_cm=height_cm,
        width_cm=width_cm,
        compartments=compartments,
        material=material,
        price=price,
        in_stock=in_stock,
        category_id=category_id,
        cost=cost,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update(db: Session, product: Product, **fields) -> Product:
    """Actualiza solo los campos que vengan en `fields` (no None)."""
    for key, value in fields.items():
        if value is not None:
            setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


def delete(db: Session, product: Product) -> None:
    db.delete(product)
    db.commit()
