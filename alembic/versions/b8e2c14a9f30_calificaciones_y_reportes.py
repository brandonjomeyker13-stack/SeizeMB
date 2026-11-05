"""calificaciones de productos y reportes de errores del sitio

Revision ID: b8e2c14a9f30
Revises: c1a8e4f70b23
Create Date: 2026-11-05 17:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8e2c14a9f30"
down_revision: str | Sequence[str] | None = "c1a8e4f70b23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ISSUE_STATUS = sa.Enum("OPEN", "SOLVED", name="issuestatus")


def upgrade() -> None:
    op.create_table(
        "product_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("stars", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_rating_user_product"),
    )
    op.create_index("ix_product_ratings_product_id", "product_ratings", ["product_id"])
    op.create_index("ix_product_ratings_user_id", "product_ratings", ["user_id"])

    _ISSUE_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "site_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("status", _ISSUE_STATUS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_issues_user_id", "site_issues", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_site_issues_user_id", table_name="site_issues")
    op.drop_table("site_issues")
    _ISSUE_STATUS.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_product_ratings_user_id", table_name="product_ratings")
    op.drop_index("ix_product_ratings_product_id", table_name="product_ratings")
    op.drop_table("product_ratings")
