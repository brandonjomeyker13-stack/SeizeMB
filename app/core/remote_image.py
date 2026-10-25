"""Baja una foto pública para re-subirla al bucket de esta tienda.

El importador no reutiliza la URL de la otra tienda: descarga los bytes y
los guarda en el Storage de SeizeMB. Si el origen se apaga, las fotos
siguen acá.

Se rechazan URLs locales o de red privada para no convertir el servidor
en un proxy hacia localhost / metadata de la nube.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import requests

from app.core.storage import MAX_FILE_SIZE_BYTES, _detect_real_content_type

DOWNLOAD_TIMEOUT_SECONDS = 20


class RemoteImageError(Exception):
    pass


def _hostname_es_publico(hostname: str) -> None:
    if hostname.lower() in {"localhost", "metadata.google.internal"}:
        raise RemoteImageError("No se puede bajar una foto desde una dirección local.")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise RemoteImageError(f"No se resolvió el host de la foto: {hostname}.") from exc
    if not infos:
        raise RemoteImageError(f"No se resolvió el host de la foto: {hostname}.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise RemoteImageError(
                "No se puede bajar una foto desde una dirección privada o local."
            )


def _url_es_http_publica(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteImageError("La URL de la foto tiene que ser http o https.")
    if not parsed.hostname:
        raise RemoteImageError("La URL de la foto no tiene host.")
    _hostname_es_publico(parsed.hostname)
    return url


def download_public_image(url: str) -> bytes:
    """Descarga bytes de una URL pública y comprueba que sean JPG/PNG/WEBP."""
    _url_es_http_publica(url)
    try:
        respuesta = requests.get(
            url,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
            allow_redirects=True,
            stream=True,
        )
    except requests.RequestException as exc:
        raise RemoteImageError(f"No se pudo bajar la foto: {exc}") from exc

    if respuesta.status_code != 200:
        raise RemoteImageError(
            f"La foto no se pudo bajar (HTTP {respuesta.status_code})."
        )

    # Tras redirecciones, el host final también tiene que ser público.
    _url_es_http_publica(respuesta.url)

    chunks: list[bytes] = []
    leido = 0
    for chunk in respuesta.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        leido += len(chunk)
        if leido > MAX_FILE_SIZE_BYTES:
            raise RemoteImageError("La imagen no puede pesar más de 5 MB.")
        chunks.append(chunk)
    contents = b"".join(chunks)

    if _detect_real_content_type(contents) is None:
        raise RemoteImageError("El archivo no es una imagen JPG, PNG o WEBP válida.")
    return contents
