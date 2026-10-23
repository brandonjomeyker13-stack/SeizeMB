"""Fallos que se cazaron combinando colores, contra entrega y carrito.

Quedan acá para que no vuelvan. El stock ya no existe: quitar un color
no pierde inventario, y pedir no reserva unidades.
"""

import pytest

from app.models.color import Color
from app.models.order import OrderStatus, PaymentMethod
from app.services import cart_service, order_service, product_service

COLORES = [Color.GRIS, Color.NEGRO]


@pytest.fixture
def bolso(crear_producto):
    return crear_producto(colores=COLORES)


def test_mandar_stock_en_el_producto_se_ignora(admin_client, bolso, db):
    """Ya no hay campo `stock`. Si alguien lo manda, no pisa nada."""
    respuesta = admin_client.put(f"/api/v1/products/{bolso.id}", json={"stock": 999})

    assert respuesta.status_code == 200
    assert "stock" not in respuesta.json()
    db.refresh(bolso)
    assert not hasattr(bolso, "stock") or getattr(bolso, "stock", None) is None


def test_el_admin_puede_apagar_un_producto(admin_client, crear_producto):
    producto = crear_producto()

    respuesta = admin_client.put(
        f"/api/v1/products/{producto.id}", json={"in_stock": False}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["in_stock"] is False


def test_el_carrito_se_limpia_tras_un_contra_entrega(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )

    order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    assert cart_service.get_cart(db, usuario.id) == []


def test_con_wompi_el_carrito_se_conserva_hasta_que_paguen(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )

    order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    assert len(cart_service.get_cart(db, usuario.id)) == 1


def test_se_puede_quitar_un_color_sin_ponerlo_en_cero(admin_client, bolso):
    """Sin inventario no hay nada que perder al desmarcar un círculo."""
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors", json={"colors": ["GRIS"]}
    )

    assert respuesta.status_code == 200
    assert [c["value"] for c in respuesta.json()["colors"]] == ["GRIS"]


def test_hay_un_tope_de_pedidos_contra_entrega_abiertos(db, usuario, crear_producto):
    producto = crear_producto(colores=[Color.GRIS])
    tope = order_service.MAX_PEDIDOS_CONTRA_ENTREGA_ABIERTOS

    for cantidad in range(1, tope + 1):
        cart_service.add_to_cart(
            db,
            user_id=usuario.id,
            product_id=producto.id,
            quantity=cantidad,
            color=Color.GRIS,
        )
        order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.CASH
        )

    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=producto.id, quantity=9, color=Color.GRIS
    )
    with pytest.raises(order_service.TooManyOpenOrdersError):
        order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.CASH
        )


def test_cancelar_uno_libera_el_cupo(db, usuario, crear_producto):
    producto = crear_producto(colores=[Color.GRIS])
    tope = order_service.MAX_PEDIDOS_CONTRA_ENTREGA_ABIERTOS
    primero = None

    for cantidad in range(1, tope + 1):
        cart_service.add_to_cart(
            db,
            user_id=usuario.id,
            product_id=producto.id,
            quantity=cantidad,
            color=Color.GRIS,
        )
        pedido = order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.CASH
        )
        primero = primero or pedido

    order_service.cancel_order(db, primero.id, usuario.id)

    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=producto.id, quantity=9, color=Color.GRIS
    )
    nuevo = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    assert nuevo.status == OrderStatus.CONFIRMED


def test_el_tope_no_aplica_a_wompi(db, usuario, crear_producto):
    producto = crear_producto()

    for cantidad in range(1, order_service.MAX_PEDIDOS_CONTRA_ENTREGA_ABIERTOS + 3):
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=producto.id, quantity=cantidad
        )
        pedido = order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
        )
        pedido.status = OrderStatus.PENDING
        db.commit()

    assert product_service.get_product_or_raise(db, producto.id) is not None
