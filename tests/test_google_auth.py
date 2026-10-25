"""Registro y login con Google: sin contraseña al crear, mensajes claros."""

import pytest

from app.models.user import User
from app.schemas.user import UserRead
from app.services import user_service


def test_sin_cuenta_y_sin_terminos_dice_que_se_registre(db):
    with pytest.raises(user_service.TermsNotAcceptedError) as exc:
        user_service.authenticate_google(
            db,
            email="nueva@pruebas.seizemb.co",
            google_id="gid-1",
            name="Nueva",
            accepted_terms=False,
        )

    assert "Aún no tienes cuenta" in str(exc.value)
    assert "No necesitas contraseña" in str(exc.value)
    assert db.query(User).count() == 0


def test_con_terminos_crea_cuenta_sin_contrasena(db):
    user, is_new = user_service.authenticate_google(
        db,
        email="nueva@pruebas.seizemb.co",
        google_id="gid-2",
        name="Nueva",
        accepted_terms=True,
    )

    assert is_new is True
    assert user.has_password is False
    assert user.google_id == "gid-2"
    assert UserRead.model_validate(user).has_password is False


def test_si_ya_existe_entra_y_no_la_vuelve_a_crear(db):
    primero, _ = user_service.authenticate_google(
        db,
        email="ya@pruebas.seizemb.co",
        google_id="gid-3",
        name="Ya",
        accepted_terms=True,
    )

    otra, is_new = user_service.authenticate_google(
        db,
        email="ya@pruebas.seizemb.co",
        google_id="gid-3",
        name="Ya",
        accepted_terms=False,
    )

    assert is_new is False
    assert otra.id == primero.id
    assert db.query(User).count() == 1


def test_email_con_contrasena_se_liga_a_google_y_conserva_la_clave(db, crear_usuario):
    existente = crear_usuario(email="clave@pruebas.seizemb.co", password="Morral-Gris-2026")

    user, is_new = user_service.authenticate_google(
        db,
        email="clave@pruebas.seizemb.co",
        google_id="gid-4",
        name="Clave",
        accepted_terms=False,
    )

    assert is_new is False
    assert user.id == existente.id
    assert user.google_id == "gid-4"
    assert user.has_password is True


def test_google_sin_clave_puede_crear_contrasena_en_perfil(db):
    user, _ = user_service.authenticate_google(
        db,
        email="perfil@pruebas.seizemb.co",
        google_id="gid-5",
        name="Perfil",
        accepted_terms=True,
    )

    actualizado = user_service.set_password(
        db, user=user, current_password=None, new_password="Morral-Gris-2026"
    )

    assert actualizado.has_password is True
    assert user_service.authenticate(
        db, email="perfil@pruebas.seizemb.co", password="Morral-Gris-2026"
    ).id == user.id
