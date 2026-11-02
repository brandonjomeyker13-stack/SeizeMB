"""Borrar la cuenta quita los datos personales y conserva el id del pedido."""

import pytest

from app.services import user_service


def test_borrar_cuenta_anonimiza_los_datos(db, crear_usuario):
    user = crear_usuario(email="borrar@pruebas.seizemb.co")
    user.phone = "3001112233"
    user.address = "Calle 1"
    user.city = "Cali"
    user.google_id = "google-borrar"
    db.commit()

    user_service.delete_account(db, user=user)
    db.refresh(user)

    assert user.is_active is False
    assert user.name == "Cuenta eliminada"
    assert user.email == f"eliminada-{user.id}@invalid.seizemb"
    assert user.phone is None
    assert user.address is None
    assert user.city is None
    assert user.google_id is None
    assert user.password_hash is None


def test_no_borra_si_hay_un_pedido_en_curso(db, crear_usuario):
    from decimal import Decimal

    from app.models.order import Order, OrderStatus, PaymentMethod

    user = crear_usuario(email="conpedido@pruebas.seizemb.co")

    db.add(
        Order(
            user_id=user.id,
            reference="seizemb-borrar-1",
            status=OrderStatus.CONFIRMED,
            payment_method=PaymentMethod.CASH,
            total_amount=Decimal("50000.00"),
        )
    )
    db.commit()

    with pytest.raises(user_service.OpenOrdersBlockDeletionError):
        user_service.delete_account(db, user=user)
