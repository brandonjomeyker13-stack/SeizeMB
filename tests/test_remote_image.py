"""El importador no puede usarse como proxy hacia redes privadas."""

import pytest

from app.core.remote_image import RemoteImageError, download_public_image


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/foto.png",
        "http://127.0.0.1/foto.png",
        "http://10.0.0.8/foto.png",
        "not-a-url",
    ],
)
def test_rechaza_urls_que_no_son_publicas(url):
    with pytest.raises(RemoteImageError):
        download_public_image(url)
