"""quitar stock: los productos son por pedido, sin inventario

Revision ID: c1a8e4f70b23
Revises: a4d71e6b0c38
Create Date: 2026-10-23 10:20:00.000000

SeizeMB no maneja inventario. En la tienda anterior se cargaba 999 para
fingir que "siempre hay"; acá no hay unidades que contar: un producto
marcado como disponible (`in_stock`) se puede pedir en cualquier
cantidad. `in_stock` se conserva para poder dejar de ofrecerlo sin
borrarlo.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1a8e4f70b23"
down_revision: str | Sequence[str] | None = "a4d71e6b0c38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("product_colors", "stock")
    op.drop_column("products", "stock")


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "product_colors",
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("products", "stock", server_default=None)
    op.alter_column("product_colors", "stock", server_default=None)
