"""Ciclo de vida de un pedido, sin inventario.

SeizeMB vende por encargo: no se reserva ni se libera stock. Estos tests
fijan lo que SÍ tiene que seguir pasando: congelar precio y costo,
reusar un checkout duplicado, cancelar una sola vez, expirar un PENDING
de Wompi y no saltarse estados de entrega.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.order import Order, OrderStatus, PaymentMethod
from app.repositories import cart_repository
from app.services import order_service


def test_crear_pedido_congela_precio_y_costo(db, usuario, crear_producto):
    producto = crear_producto(precio="50000.00", costo="30000.00")
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=3)

    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    assert pedido.status == OrderStatus.PENDING
    assert float(pedido.total_amount) == 150000.0
    item = pedido.items[0]
    assert float(item.unit_price) == 50000.0
    assert float(item.unit_cost) == 30000.0

    # El histórico no se mueve aunque el producto cambie de precio después.
    producto.price = 99999
    db.commit()
    db.refresh(item)
    assert float(item.unit_price) == 50000.0


def test_un_producto_apagado_no_deja_armar_el_pedido(db, usuario, crear_producto):
    disponible = crear_producto(nombre="Morral")
    apagado = crear_producto(nombre="Pantaloneta", disponible=False)
    cart_repository.create(db, user_id=usuario.id, product_id=disponible.id, quantity=2)
    cart_repository.create(db, user_id=usuario.id, product_id=apagado.id, quantity=5)

    with pytest.raises(order_service.ProductUnavailableError):
        order_service.create_order_from_cart(db, user_id=usuario.id)

    db.rollback()
    assert db.query(Order).count() == 0


def test_se_puede_pedir_cualquier_cantidad(db, usuario, crear_producto):
    """Ya no hay tope de 999 ni de unidades cargadas: se pide a demanda."""
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=2000)

    pedido = order_service.create_order_from_cart(db, user_id=usuario.id)

    assert pedido.items[0].quantity == 2000
    assert pedido.status == OrderStatus.CONFIRMED


def test_carrito_vacio_no_crea_pedido(db, usuario):
    with pytest.raises(order_service.EmptyCartError):
        order_service.create_order_from_cart(db, user_id=usuario.id)


def test_checkout_dos_veces_con_el_mismo_carrito_reusa_el_pedido(db, usuario, crear_producto):
    """Doble clic en "Pedir" no debe crear dos pedidos."""
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=2)

    primero = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )
    segundo = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    assert primero.id == segundo.id
    assert db.query(Order).count() == 1


def test_cancelar_una_sola_vez(db, usuario, crear_producto):
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=4)
    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    order_service.cancel_order(db, pedido.id, usuario.id)

    assert pedido.status == OrderStatus.CANCELLED

    with pytest.raises(order_service.InvalidStatusTransitionError):
        order_service.cancel_order(db, pedido.id, usuario.id)


def test_no_se_puede_cancelar_el_pedido_de_otra_persona(db, usuario, crear_usuario, crear_producto):
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=1)
    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )
    intruso = crear_usuario(email="intruso@pruebas.seizemb.co")

    with pytest.raises(order_service.OrderNotFoundError):
        order_service.cancel_order(db, pedido.id, intruso.id)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.PENDING


def test_pedido_abandonado_expira(db, usuario, crear_producto):
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=6)
    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    pedido.created_at = datetime.now(timezone.utc) - timedelta(
        hours=order_service.PENDING_ORDER_TTL_HOURS + 1
    )
    db.commit()

    assert order_service.expire_stale_orders(db) == 1

    db.refresh(pedido)
    assert pedido.status == OrderStatus.EXPIRED
    assert order_service.expire_stale_orders(db) == 0


def test_la_duena_puede_cerrar_un_pedido_que_nadie_confirmo(db, usuario, crear_producto):
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=1)
    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )
    pedido.status = OrderStatus.AWAITING_CONFIRMATION
    db.commit()

    order_service.update_delivery_status(db, pedido.id, OrderStatus.DELIVERED)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.DELIVERED
    assert pedido.delivery_confirmed_at is not None


def test_el_admin_no_puede_saltarse_estados_de_entrega(db, usuario, crear_producto):
    producto = crear_producto()
    cart_repository.create(db, user_id=usuario.id, product_id=producto.id, quantity=1)
    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    # PENDING -> IN_TRANSIT no existe: primero tiene que estar pago.
    with pytest.raises(order_service.InvalidStatusTransitionError):
        order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)

    pedido.status = OrderStatus.APPROVED
    db.commit()
    with pytest.raises(order_service.InvalidStatusTransitionError):
        order_service.update_delivery_status(db, pedido.id, OrderStatus.DELIVERED)

    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)
    db.refresh(pedido)
    assert pedido.status == OrderStatus.IN_TRANSIT
