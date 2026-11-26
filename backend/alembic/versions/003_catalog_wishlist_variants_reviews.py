"""003_catalog_wishlist_variants_reviews

Add is_active and low_stock_threshold to products, plus product_variants,
reviews, and wishlist_items tables.
"""

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("products", sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("products", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_products_is_active", "products", ["is_active"])

    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sku", sa.String(64), unique=True, nullable=True),
        sa.Column("price_delta", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("stock >= 0", name="ck_variant_stock_nonneg"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        sa.UniqueConstraint("product_id", "user_id", name="uq_review_product_user"),
    )

    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
    )


def downgrade() -> None:
    op.drop_table("wishlist_items")
    op.drop_table("reviews")
    op.drop_table("product_variants")
    op.drop_index("ix_products_is_active", table_name="products")
    op.drop_column("products", "is_active")
    op.drop_column("products", "low_stock_threshold")
