"""Solo califica quien ya recibió el producto, y el promedio no duplica a la misma persona."""

from decimal import Decimal

import pytest

from app.models.order import Order, OrderItem, OrderStatus, PaymentMethod
from app.services import rating_service


def _pedido_entregado(db, usuario, producto):
    pedido = Order(
        user_id=usuario.id,
        reference=f"seizemb-nota-{usuario.id}-{producto.id}",
        status=OrderStatus.DELIVERED,
        payment_method=PaymentMethod.CASH,
        total_amount=Decimal("50000.00"),
    )
    db.add(pedido)
    db.flush()
    db.add(
        OrderItem(
            order_id=pedido.id,
            product_id=producto.id,
            product_name=producto.name,
            unit_price=Decimal("50000.00"),
            quantity=1,
        )
    )
    db.commit()


def test_sin_entrega_no_puede_calificar(db, crear_usuario, crear_producto):
    usuario = crear_usuario(email="sin-entrega@pruebas.seizemb.co")
    producto = crear_producto()
    with pytest.raises(rating_service.ProductNotDeliveredError):
        rating_service.rate(db, user=usuario, product_id=producto.id, stars=5, comment=None)


def test_el_promedio_usa_una_sola_nota_por_persona(db, crear_usuario, crear_producto):
    usuario = crear_usuario(email="nota@pruebas.seizemb.co")
    producto = crear_producto()
    _pedido_entregado(db, usuario, producto)

    rating_service.rate(db, user=usuario, product_id=producto.id, stars=2, comment="Llegó chico")
    rating_service.rate(db, user=usuario, product_id=producto.id, stars=4, comment="Al usarlo quedó bien")
    rating_service.attach(db, [producto])

    assert producto.rating_count == 1
    assert producto.rating_average == 4.0
