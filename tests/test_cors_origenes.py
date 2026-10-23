"""Qué orígenes son de confianza, y cuáles dejan de serlo en producción.

El comodín `*.lovable.app` no distingue nuestro proyecto de los demás:
acepta CUALQUIER subdominio de Lovable. Con la cookie del refresh token
en SameSite=None y allow_credentials activo, eso alcanza para que una
página ajena llame a /auth/refresh con la cookie de un cliente nuestro y
lea su access_token. Por eso en producción va apagado, y estos tests lo
fijan para que nadie lo reabra sin darse cuenta.
"""

import importlib

import pytest

from app.core import cors as cors_module
from app.core.config import settings

PREVIEW_AJENO = "https://proyecto-de-otra-persona.lovable.app"
DOMINIO_PROPIO = "https://seizemb.com"


@pytest.fixture
def cors_con(monkeypatch):
    """Recarga app.core.cors con otro entorno.

    Hace falta recargar porque ALLOWED_ORIGINS / ALLOWED_ORIGIN_REGEX se
    resuelven al importar el módulo, no en cada llamada.
    """
    originales = (
        settings.ENVIRONMENT,
        settings.ALLOW_LOVABLE_PREVIEW,
        settings.FRONTEND_ORIGINS,
    )

    def _cargar(*, environment: str, allow_preview: bool, frontend_origins: str = ""):
        monkeypatch.setattr(settings, "ENVIRONMENT", environment)
        monkeypatch.setattr(settings, "ALLOW_LOVABLE_PREVIEW", allow_preview)
        monkeypatch.setattr(settings, "FRONTEND_ORIGINS", frontend_origins)
        return importlib.reload(cors_module)

    yield _cargar

    # Dejar el módulo como estaba para no contaminar los demás tests.
    (
        settings.ENVIRONMENT,
        settings.ALLOW_LOVABLE_PREVIEW,
        settings.FRONTEND_ORIGINS,
    ) = originales
    importlib.reload(cors_module)


@pytest.mark.parametrize(
    "origen",
    ["http://localhost:5173", "http://127.0.0.1:3000"],
)
def test_localhost_siempre_es_de_confianza(cors_con, origen):
    cors = cors_con(environment="production", allow_preview=False)

    assert cors.is_trusted_origin(origen)


def test_un_dominio_extra_del_env_es_de_confianza(cors_con):
    cors = cors_con(
        environment="production",
        allow_preview=False,
        frontend_origins=DOMINIO_PROPIO,
    )

    assert cors.is_trusted_origin(DOMINIO_PROPIO)


def test_en_produccion_un_lovable_ajeno_no_es_de_confianza(cors_con):
    cors = cors_con(environment="production", allow_preview=False)

    assert not cors.is_trusted_origin(PREVIEW_AJENO)
    # Sin regex, el middleware de CORS tampoco lo deja pasar.
    assert cors.ALLOWED_ORIGIN_REGEX is None


def test_en_local_el_preview_si_pasa(cors_con):
    """El subdominio de preview cambia por sesión: en desarrollo no queda
    otra que aceptarlo por patrón."""
    cors = cors_con(environment="local", allow_preview=False)

    assert cors.is_trusted_origin(PREVIEW_AJENO)


def test_se_puede_reabrir_a_mano_mientras_se_construye(cors_con):
    cors = cors_con(environment="production", allow_preview=True)

    assert cors.is_trusted_origin(PREVIEW_AJENO)


@pytest.mark.parametrize(
    "origen",
    [
        "https://seizemb.com.atacante.com",
        "https://seizemb.com:8443",
        "http://seizemb.com",
        "https://lovable.app.atacante.com",
        "https://sitio-cualquiera.com",
    ],
)
def test_lo_que_no_es_nuestro_nunca_pasa(cors_con, origen):
    cors = cors_con(
        environment="local",
        allow_preview=True,
        frontend_origins=DOMINIO_PROPIO,
    )

    assert not cors.is_trusted_origin(origen)
