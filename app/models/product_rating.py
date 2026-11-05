"""Calificación de quien ya recibió el producto.

Una fila por persona y producto. Si cambia de opinión, se actualiza
la misma fila: el promedio no cuenta dos veces a la misma clienta.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ProductRating(Base):
    __tablename__ = "product_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_rating_user_product"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    stars = Column(SmallInteger, nullable=False)
    comment = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    product = relationship("Product")
