"""
test_models.py – unit tests for ORM model constraints and monetary field types.

Covers:
  ✓ Decimal type is preserved for price fields
  ✓ StripeEvent records and unique constraint works
  ✓ OrderItem unit_price snapshot is immutable (not updated when product price changes)
"""
import pytest
from decimal import Decimal
from app import models


class TestDecimalMonetary:
    def test_product_price_is_decimal(self, db_session, product):
        db_session.refresh(product)
        assert isinstance(product.price, Decimal)

    def test_order_total_is_decimal(self, db_session, user, product):
        order = models.Order(
            user_id=user.id,
            total_amount=Decimal("99.99"),
            status="awaiting_payment",
            payment_status="pending",
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        assert isinstance(order.total_amount, Decimal)
        assert order.total_amount == Decimal("99.99")

    def test_order_item_unit_price_snapshot(self, db_session, user, product):
        """Changing product price after checkout must NOT change the order item unit_price."""
        original_price = product.price

        order = models.Order(
            user_id=user.id,
            total_amount=original_price,
            status="awaiting_payment",
            payment_status="pending",
        )
        db_session.add(order)
        db_session.flush()

        item = models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=original_price,
        )
        db_session.add(item)
        db_session.commit()

        # Update product price
        product.price = Decimal("999.99")
        db_session.commit()

        db_session.refresh(item)
        # Snapshot must still reflect the original price
        assert item.unit_price == original_price
        assert item.unit_price != product.price


class TestStripeEventIdempotency:
    def test_stripe_event_records_correctly(self, db_session):
        evt = models.StripeEvent(event_id="evt_unique_001", event_type="payment_intent.succeeded")
        db_session.add(evt)
        db_session.commit()
        db_session.refresh(evt)
        assert evt.event_id == "evt_unique_001"
        assert evt.id is not None

    def test_duplicate_stripe_event_raises(self, db_session):
        """Inserting the same event_id twice must violate the unique constraint."""
        from sqlalchemy.exc import IntegrityError

        db_session.add(models.StripeEvent(event_id="evt_dup", event_type="test"))
        db_session.commit()

        db_session.add(models.StripeEvent(event_id="evt_dup", event_type="test"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestOrderItemValidation:
    def test_order_item_quantity_must_be_positive(self):
        """quantity ≤ 0 is caught by Pydantic before hitting the DB."""
        from pydantic import ValidationError
        from app.schemas import CartItemAdd

        with pytest.raises(ValidationError):
            CartItemAdd(product_id=1, quantity=0)

    def test_product_price_must_be_positive(self):
        from pydantic import ValidationError
        from app.schemas import ProductCreate

        with pytest.raises(ValidationError):
            ProductCreate(name="Bad", price=Decimal("-1.00"), category="Test", stock=0)
