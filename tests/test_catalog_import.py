"""POST /products/import copia el catálogo y re-sube las fotos al Storage
de SeizeMB. No se quedan las URLs de la otra tienda."""

from app.core.remote_image import RemoteImageError
from app.core.storage import UploadedImage
from app.services import catalog_import_service


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32

CATALOGO = {
    "source": "proyecto-leidy",
    "categories": [{"name": "Morrales"}],
    "products": [
        {
            "name": "Morral gris",
            "price": "120000.00",
            "cost": "70000.00",
            "height_cm": "43.0",
            "width_cm": "33.0",
            "compartments": 3,
            "material": "Lona satinada",
            "in_stock": True,
            "category": "Morrales",
            "colors": ["GRIS", "NEGRO"],
            "images": [
                {
                    "url": "https://cdn.origen.test/frente.webp",
                    "storage_path": "leidy/frente.webp",
                    "color": None,
                    "position": 0,
                },
                {
                    "url": "https://cdn.origen.test/negro.webp",
                    "storage_path": "leidy/negro.webp",
                    "color": "NEGRO",
                    "position": 0,
                },
            ],
        }
    ],
}


def _subidas_falsas(monkeypatch):
    bajadas: list[str] = []
    subidas: list[str] = []

    def bajar(url: str) -> bytes:
        bajadas.append(url)
        return PNG

    def subir(contents: bytes, product_id: int) -> UploadedImage:
        path = f"product-{product_id}-{len(subidas)}.png"
        subidas.append(path)
        return UploadedImage(
            url=f"https://supabase.seizemb.test/storage/v1/object/public/product-images/{path}",
            path=path,
        )

    monkeypatch.setattr(catalog_import_service, "download_public_image", bajar)
    monkeypatch.setattr(catalog_import_service, "upload_product_image_bytes", subir)
    return bajadas, subidas


def test_importar_exige_admin(client):
    respuesta = client.post("/api/v1/products/import", json=CATALOGO)

    assert respuesta.status_code == 401


def test_import_vacio_es_400(admin_client):
    respuesta = admin_client.post(
        "/api/v1/products/import", json={"products": [], "categories": []}
    )

    assert respuesta.status_code == 400
    assert "no trae" in respuesta.json()["detail"]


def test_importa_producto_y_reescribe_las_fotos_en_este_storage(
    admin_client, monkeypatch, db
):
    bajadas, subidas = _subidas_falsas(monkeypatch)

    respuesta = admin_client.post("/api/v1/products/import", json=CATALOGO)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["created_categories"] == 1
    assert cuerpo["created_products"] == 1
    assert cuerpo["skipped_products"] == 0
    assert cuerpo["images_copied"] == 2
    assert cuerpo["image_errors"] == []
    assert bajadas == [
        "https://cdn.origen.test/frente.webp",
        "https://cdn.origen.test/negro.webp",
    ]

    producto = admin_client.get("/api/v1/products/").json()[0]
    assert producto["name"] == "Morral gris"
    assert producto["price"] == "120000.00"
    assert producto["category"]["name"] == "Morrales"
    assert {c["value"] for c in producto["colors"]} == {"GRIS", "NEGRO"}
    urls = {img["image_url"] for img in producto["images"]}
    assert urls == {
        f"https://supabase.seizemb.test/storage/v1/object/public/product-images/{subidas[0]}",
        f"https://supabase.seizemb.test/storage/v1/object/public/product-images/{subidas[1]}",
    }
    assert all("cdn.origen.test" not in url for url in urls)
    negro = next(img for img in producto["images"] if img["color"] == "NEGRO")
    assert negro["position"] == 0
    detalle = admin_client.get(f"/api/v1/products/{producto['id']}/admin").json()
    assert detalle["cost"] == "70000.00"
    assert detalle["material"] == "Lona satinada"


def test_reimportar_el_mismo_nombre_no_duplica(admin_client, monkeypatch):
    _subidas_falsas(monkeypatch)
    admin_client.post("/api/v1/products/import", json=CATALOGO)

    otra = admin_client.post("/api/v1/products/import", json=CATALOGO)

    assert otra.status_code == 200
    cuerpo = otra.json()
    assert cuerpo["created_products"] == 0
    assert cuerpo["skipped_products"] == 1
    assert cuerpo["images_copied"] == 0
    assert len(admin_client.get("/api/v1/products/").json()) == 1


def test_si_una_foto_falla_el_producto_igual_se_crea(admin_client, monkeypatch):
    def bajar(url: str) -> bytes:
        if "negro" in url:
            raise RemoteImageError("La foto no se pudo bajar (HTTP 404).")
        return PNG

    def subir(contents: bytes, product_id: int) -> UploadedImage:
        return UploadedImage(
            url=f"https://supabase.seizemb.test/ok-{product_id}.png",
            path=f"product-{product_id}.png",
        )

    monkeypatch.setattr(catalog_import_service, "download_public_image", bajar)
    monkeypatch.setattr(catalog_import_service, "upload_product_image_bytes", subir)

    respuesta = admin_client.post("/api/v1/products/import", json=CATALOGO)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["created_products"] == 1
    assert cuerpo["images_copied"] == 1
    assert len(cuerpo["image_errors"]) == 1
    assert "negro.webp" in cuerpo["image_errors"][0]["url"]
    producto = admin_client.get("/api/v1/products/").json()[0]
    assert len(producto["images"]) == 1


def test_reusa_categoria_existente_sin_importar_mayusculas(
    admin_client, categoria, monkeypatch
):
    _subidas_falsas(monkeypatch)
    catalogo = {
        **CATALOGO,
        "categories": [{"name": "morrales"}],
        "products": [{**CATALOGO["products"][0], "category": "morrales"}],
    }

    respuesta = admin_client.post("/api/v1/products/import", json=catalogo)

    assert respuesta.status_code == 200
    assert respuesta.json()["created_categories"] == 0
    producto = admin_client.get("/api/v1/products/").json()[0]
    assert producto["category"]["id"] == categoria.id
    assert producto["category"]["name"] == "Morrales"
