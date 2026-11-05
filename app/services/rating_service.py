"""Estrellas de quien ya recibió el producto. El promedio sale de ahí."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.product_rating import ProductRating
from app.models.user import User


class ProductNotDeliveredError(Exception):
    pass


def attach(db: Session, products: list[Product]) -> list[Product]:
    if not products:
        return products
    ids = [product.id for product in products]
    rows = (
        db.query(
            ProductRating.product_id,
            func.avg(ProductRating.stars),
            func.count(ProductRating.id),
        )
        .filter(ProductRating.product_id.in_(ids))
        .group_by(ProductRating.product_id)
        .all()
    )
    stats = {
        product_id: (round(float(average), 1), int(count))
        for product_id, average, count in rows
    }
    for product in products:
        average, count = stats.get(product.id, (None, 0))
        product.rating_average = average
        product.rating_count = count
    return products


def received(db: Session, *, user_id: int, product_id: int) -> bool:
    row = (
        db.query(Order.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.user_id == user_id,
            Order.status == OrderStatus.DELIVERED,
            OrderItem.product_id == product_id,
        )
        .first()
    )
    return row is not None


def mine(db: Session, *, user_id: int, product_id: int) -> ProductRating | None:
    return (
        db.query(ProductRating)
        .filter(ProductRating.user_id == user_id, ProductRating.product_id == product_id)
        .first()
    )


def rate(
    db: Session,
    *,
    user: User,
    product_id: int,
    stars: int,
    comment: str | None,
) -> ProductRating:
    if comment is not None:
        comment = comment.strip() or None
    if not received(db, user_id=user.id, product_id=product_id):
        raise ProductNotDeliveredError(
            "Puedes calificar cuando el pedido te haya llegado."
        )
    row = mine(db, user_id=user.id, product_id=product_id)
    if row is None:
        row = ProductRating(user_id=user.id, product_id=product_id, stars=stars, comment=comment)
        db.add(row)
    else:
        row.stars = stars
        row.comment = comment
    db.commit()
    db.refresh(row)
    return row


def public_list(db: Session, product_id: int) -> list[dict]:
    rows = (
        db.query(ProductRating, User)
        .join(User, User.id == ProductRating.user_id)
        .filter(ProductRating.product_id == product_id, ProductRating.comment.isnot(None))
        .order_by(ProductRating.created_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for rating, user in rows:
        author = "Cliente"
        if user.is_active and user.name and user.name != "Cuenta eliminada":
            author = user.name.split()[0]
        result.append({"stars": rating.stars, "comment": rating.comment, "author": author})
    return result
