"""Colores al comprar: elegir uno es obligatorio, y el pedido lo recuerda.

No hay stock por color. Un color marcado está disponible en cualquier
cantidad. Lo que estos tests fijan:

1. Si el producto viene en colores, elegir uno es OBLIGATORIO.
2. El mismo artículo en dos colores son dos líneas del carrito.
3. El pedido congela el color pedido.
"""

import pytest

from app.models.color import Color
from app.models.order import PaymentMethod
from app.repositories import cart_repository
from app.services import cart_service, order_service
from app.services.product_service import ProductUnavailableError

COLORES = [Color.GRIS, Color.NEGRO]


@pytest.fixture
def bolso(crear_producto):
    return crear_producto(colores=COLORES)


@pytest.fixture
def bolso_sin_colores(crear_producto):
    return crear_producto()


def test_la_ficha_muestra_cada_color_sin_unidades(client, bolso):
    ficha = client.get(f"/api/v1/products/{bolso.id}").json()

    assert {c["value"] for c in ficha["colors"]} == {"GRIS", "NEGRO"}
    assert all("stock" not in c for c in ficha["colors"])


def test_sin_color_no_se_puede_agregar_al_carrito(db, usuario, bolso):
    with pytest.raises(cart_service.ColorRequiredError):
        cart_service.add_to_cart(db, user_id=usuario.id, product_id=bolso.id, quantity=1)


def test_un_color_que_el_producto_no_tiene_se_rechaza(db, usuario, bolso):
    with pytest.raises(cart_service.ColorNotAvailableError):
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.ROJO
        )


def test_un_producto_sin_colores_no_acepta_color(db, usuario, bolso_sin_colores):
    with pytest.raises(cart_service.ColorNotAvailableError):
        cart_service.add_to_cart(
            db,
            user_id=usuario.id,
            product_id=bolso_sin_colores.id,
            quantity=1,
            color=Color.GRIS,
        )


def test_un_producto_sin_colores_se_agrega_sin_color(db, usuario, bolso_sin_colores):
    item = cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso_sin_colores.id, quantity=2
    )

    assert item.color is None


def test_se_puede_pedir_cualquier_cantidad_de_un_color(db, usuario, bolso):
    item = cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=50, color=Color.NEGRO
    )

    assert item.quantity == 50


def test_un_producto_apagado_no_entra_al_carrito(db, usuario, crear_producto):
    producto = crear_producto(colores=COLORES, disponible=False)

    with pytest.raises(ProductUnavailableError):
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=producto.id, quantity=1, color=Color.GRIS
        )


def test_el_mismo_bolso_en_dos_colores_son_dos_lineas(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.NEGRO
    )

    lineas = cart_repository.list_by_user(db, usuario.id)
    assert len(lineas) == 2
    assert {linea.color for linea in lineas} == {Color.GRIS, Color.NEGRO}


def test_agregar_el_mismo_color_dos_veces_suma_en_la_misma_linea(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=2, color=Color.GRIS
    )

    lineas = cart_repository.list_by_user(db, usuario.id)
    assert len(lineas) == 1
    assert lineas[0].quantity == 3


def test_el_pedido_recuerda_que_color_pidio(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=2, color=Color.NEGRO
    )

    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    assert [item.color for item in pedido.items] == [Color.NEGRO]


def test_el_endpoint_de_stock_por_color_ya_no_existe(admin_client, bolso):
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors/NEGRO/stock", json={"stock": 12}
    )

    assert respuesta.status_code == 404
