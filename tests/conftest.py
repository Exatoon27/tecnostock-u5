import pytest

from src.infrastructure.contenedor import construir


@pytest.fixture
def c():
    """Contenedor nuevo con los CSV recién cargados (nada persiste entre tests)."""
    return construir()
