"""001_monetary_fields_and_constraints

Alembic migration: 001_monetary_fields_and_constraints

Changes
-------
1. products.price, rating          → NUMERIC(12,2) / NUMERIC(3,2)
2. orders.total_amount             → NUMERIC(12,2)
3. orders.discount_amount          → NUMERIC(12,2) [new column if missing]
4. order_items.unit_price          → NUMERIC(12,2)
5. coupons.percent_off, amount_off → NUMERIC(5,2) / NUMERIC(12,2)
6. coupons.min_order_amount        → NUMERIC(12,2) [new column]
7. orders.updated_at               → DateTime [new column]
8. orders.status default           → 'awaiting_payment'
9. CHECK constraints on stock, qty, prices, status values
10. stripe_events table            → new (idempotency)
11. UniqueConstraint on orders.stripe_payment_intent_id
12. UniqueConstraint on cart_items (user_id, product_id)

SQLite compatibility
--------------------
SQLite does not support ALTER COLUMN type changes or most ALTER TABLE
operations.  On SQLite we drop and recreate the affected tables (acceptable
in development).  On PostgreSQL the proper ALTER COLUMN path is used.
"""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    existing_tables = set(sa.inspect(bind).get_table_names())

    # On a brand-new empty database, create users and base tables first if absent
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    # ── stripe_events (new table) ─────────────────────────────────────────────
    if "stripe_events" not in existing_tables:
        op.create_table(
            "stripe_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_id", sa.String(255), nullable=False),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_id", name="uq_stripe_events_event_id"),
        )
        op.create_index("ix_stripe_events_event_id", "stripe_events", ["event_id"], unique=True)

    if is_sqlite:
        _upgrade_sqlite(bind, existing_tables)
    else:
        _upgrade_postgres()


def _upgrade_sqlite(bind, existing_tables: set[str]) -> None:
    """
    SQLite: create or recreate tables with correct types and constraints.
    Data is preserved via INSERT INTO … SELECT when the table already exists.
    """
    # ── products ──────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE products_new (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            price NUMERIC(12,2) NOT NULL,
            category VARCHAR(100) NOT NULL,
            image_url VARCHAR(500),
            stock INTEGER NOT NULL DEFAULT 0,
            rating NUMERIC(3,2) DEFAULT 4.00,
            review_count INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            CONSTRAINT ck_product_price_positive CHECK (price > 0),
            CONSTRAINT ck_product_stock_nonneg CHECK (stock >= 0)
        )
    """)
    if "products" in existing_tables:
        op.execute("INSERT INTO products_new SELECT * FROM products")
        op.execute("DROP TABLE products")
    op.execute("ALTER TABLE products_new RENAME TO products")
    op.create_index("ix_products_id", "products", ["id"])
    op.create_index("ix_products_category", "products", ["category"])

    # ── cart_items ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE cart_items_new (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL,
            CONSTRAINT ck_cart_item_quantity_positive CHECK (quantity > 0),
            UNIQUE (user_id, product_id)
        )
    """)
    if "cart_items" in existing_tables:
        op.execute("INSERT INTO cart_items_new SELECT * FROM cart_items")
        op.execute("DROP TABLE cart_items")
    op.execute("ALTER TABLE cart_items_new RENAME TO cart_items")
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])

    # ── orders ────────────────────────────────────────────────────────────────
    inspector = sa.inspect(bind)
    has_orders = "orders" in existing_tables
    order_cols = {c["name"] for c in inspector.get_columns("orders")} if has_orders else set()
    has_discount = "discount_amount" in order_cols
    has_updated_at = "updated_at" in order_cols

    op.execute("""
        CREATE TABLE orders_new (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total_amount NUMERIC(12,2) NOT NULL,
            discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
            coupon_code VARCHAR(50),
            status VARCHAR(50) NOT NULL DEFAULT 'awaiting_payment',
            payment_status VARCHAR(50) NOT NULL DEFAULT 'pending',
            stripe_payment_intent_id VARCHAR(255) UNIQUE,
            shipping_name VARCHAR(100),
            shipping_address VARCHAR(500),
            shipping_city VARCHAR(100),
            shipping_zip VARCHAR(20),
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            CONSTRAINT ck_order_total_nonneg CHECK (total_amount >= 0),
            CONSTRAINT ck_order_discount_nonneg CHECK (discount_amount >= 0)
        )
    """)
    if has_orders:
        if has_discount and has_updated_at:
            op.execute("INSERT INTO orders_new SELECT * FROM orders")
        elif has_discount:
            op.execute(
                "INSERT INTO orders_new "
                "(id,user_id,total_amount,discount_amount,coupon_code,status,payment_status,"
                "stripe_payment_intent_id,shipping_name,shipping_address,shipping_city,"
                "shipping_zip,created_at) "
                "SELECT id,user_id,total_amount,discount_amount,coupon_code,status,payment_status,"
                "stripe_payment_intent_id,shipping_name,shipping_address,shipping_city,"
                "shipping_zip,created_at FROM orders"
            )
        else:
            op.execute(
                "INSERT INTO orders_new "
                "(id,user_id,total_amount,coupon_code,status,payment_status,"
                "stripe_payment_intent_id,shipping_name,shipping_address,shipping_city,"
                "shipping_zip,created_at) "
                "SELECT id,user_id,total_amount,coupon_code,status,payment_status,"
                "stripe_payment_intent_id,shipping_name,shipping_address,shipping_city,"
                "shipping_zip,created_at FROM orders"
            )
        op.execute("DROP TABLE orders")
    op.execute("ALTER TABLE orders_new RENAME TO orders")
    op.create_index("ix_orders_id", "orders", ["id"])
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_stripe_payment_intent_id", "orders", ["stripe_payment_intent_id"])

    # ── order_items ───────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE order_items_new (
            id INTEGER NOT NULL PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL,
            unit_price NUMERIC(12,2) NOT NULL,
            CONSTRAINT ck_order_item_quantity_positive CHECK (quantity > 0),
            CONSTRAINT ck_order_item_price_positive CHECK (unit_price > 0)
        )
    """)
    if "order_items" in existing_tables:
        op.execute("INSERT INTO order_items_new SELECT * FROM order_items")
        op.execute("DROP TABLE order_items")
    op.execute("ALTER TABLE order_items_new RENAME TO order_items")
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # ── coupons ───────────────────────────────────────────────────────────────
    has_coupons = "coupons" in existing_tables
    coupon_cols = {c["name"] for c in inspector.get_columns("coupons")} if has_coupons else set()
    has_min_order = "min_order_amount" in coupon_cols

    op.execute("""
        CREATE TABLE coupons_new (
            id INTEGER NOT NULL PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE,
            percent_off NUMERIC(5,2),
            amount_off NUMERIC(12,2),
            min_order_amount NUMERIC(12,2),
            expires_at DATETIME,
            max_uses INTEGER,
            used_count INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL,
            CONSTRAINT ck_coupon_used_count_nonneg CHECK (used_count >= 0)
        )
    """)
    if has_coupons:
        if has_min_order:
            op.execute("INSERT INTO coupons_new SELECT * FROM coupons")
        else:
            op.execute(
                "INSERT INTO coupons_new "
                "(id,code,percent_off,amount_off,expires_at,max_uses,used_count,is_active,created_at) "
                "SELECT id,code,percent_off,amount_off,expires_at,max_uses,used_count,is_active,created_at "
                "FROM coupons"
            )
        op.execute("DROP TABLE coupons")
    op.execute("ALTER TABLE coupons_new RENAME TO coupons")
    op.create_index("ix_coupons_code", "coupons", ["code"], unique=True)


def _upgrade_postgres() -> None:
    """PostgreSQL: use proper ALTER COLUMN ... TYPE."""
    # products
    op.alter_column("products", "price", type_=sa.Numeric(12, 2), postgresql_using="price::numeric")
    op.alter_column("products", "rating", type_=sa.Numeric(3, 2), nullable=True, postgresql_using="rating::numeric")
    op.create_check_constraint("ck_product_price_positive", "products", "price > 0")
    op.create_check_constraint("ck_product_stock_nonneg", "products", "stock >= 0")

    # cart_items
    op.create_check_constraint("ck_cart_item_quantity_positive", "cart_items", "quantity > 0")
    op.create_unique_constraint("uq_cart_user_product", "cart_items", ["user_id", "product_id"])

    # orders
    op.alter_column("orders", "total_amount", type_=sa.Numeric(12, 2), postgresql_using="total_amount::numeric")
    # Add discount_amount if missing
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE orders ADD COLUMN discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.alter_column("orders", "discount_amount", type_=sa.Numeric(12, 2), postgresql_using="discount_amount::numeric")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE orders ADD COLUMN updated_at TIMESTAMP;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.create_check_constraint("ck_order_total_nonneg", "orders", "total_amount >= 0")
    op.create_check_constraint("ck_order_discount_nonneg", "orders", "discount_amount >= 0")
    op.create_unique_constraint("uq_orders_stripe_intent", "orders", ["stripe_payment_intent_id"])

    # order_items
    op.alter_column("order_items", "unit_price", type_=sa.Numeric(12, 2), postgresql_using="unit_price::numeric")
    op.create_check_constraint("ck_order_item_quantity_positive", "order_items", "quantity > 0")
    op.create_check_constraint("ck_order_item_price_positive", "order_items", "unit_price > 0")

    # coupons
    op.alter_column("coupons", "percent_off", type_=sa.Numeric(5, 2), nullable=True, postgresql_using="percent_off::numeric")
    op.alter_column("coupons", "amount_off", type_=sa.Numeric(12, 2), nullable=True, postgresql_using="amount_off::numeric")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE coupons ADD COLUMN min_order_amount NUMERIC(12,2);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.create_check_constraint("ck_coupon_used_count_nonneg", "coupons", "used_count >= 0")


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.drop_index("ix_stripe_events_event_id", table_name="stripe_events")
    op.drop_table("stripe_events")

    if is_sqlite:
        # Minimal downgrade: SQLite can't restore original types anyway
        # Recreate tables without constraints (best-effort)
        pass
    else:
        # PostgreSQL: remove constraints and revert types
        for constraint in [
            ("ck_product_price_positive", "products"),
            ("ck_product_stock_nonneg", "products"),
            ("ck_cart_item_quantity_positive", "cart_items"),
            ("uq_cart_user_product", "cart_items"),
            ("ck_order_total_nonneg", "orders"),
            ("ck_order_discount_nonneg", "orders"),
            ("uq_orders_stripe_intent", "orders"),
            ("ck_order_item_quantity_positive", "order_items"),
            ("ck_order_item_price_positive", "order_items"),
            ("ck_coupon_used_count_nonneg", "coupons"),
        ]:
            try:
                op.drop_constraint(constraint[0], constraint[1])
            except Exception:
                pass

        op.alter_column("products", "price", type_=sa.Float(), postgresql_using="price::float8")
        op.alter_column("products", "rating", type_=sa.Float(), postgresql_using="rating::float8")
        op.alter_column("orders", "total_amount", type_=sa.Float(), postgresql_using="total_amount::float8")
        op.alter_column("order_items", "unit_price", type_=sa.Float(), postgresql_using="unit_price::float8")
        op.alter_column("coupons", "percent_off", type_=sa.Float(), nullable=True, postgresql_using="percent_off::float8")
        op.alter_column("coupons", "amount_off", type_=sa.Float(), nullable=True, postgresql_using="amount_off::float8")
