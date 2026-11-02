"""Google Search Console lee el HTML de /. /health sigue siendo JSON."""


def test_la_raiz_incluye_la_verificacion_y_no_se_indexa(client):
    respuesta = client.get("/")

    assert respuesta.status_code == 200
    assert "google-site-verification" in respuesta.text
    assert "SzdNS0Niw2K97d-Q0aNWLM37x8_mmP2bifsOpBP8AyU" in respuesta.text
    assert "noindex" in respuesta.text
    assert "SeizeMB API está corriendo" in respuesta.text


def test_health_sigue_en_json(client):
    assert client.get("/health").json() == {"status": "ok"}
