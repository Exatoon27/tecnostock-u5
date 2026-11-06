"""E01-E15 de datos/escenarios.csv con su resultado esperado (oráculo)."""
import pytest

from ejecutar_escenarios import ejecutar, estado_de
from src.infrastructure.carga_csv import filas
from src.infrastructure.contenedor import construir, construir_sql

# caso -> (prefijo del resultado, {identificador: estado final esperado})
ESPERADO = {
    "E01": ("OK", {"SN-LAP-0001": "RESERVADO"}),
    "E02": ("RECHAZO ReglaNegocioViolada", {"SN-LAP-0002": "DISPONIBLE"}),
    "E03": ("RECHAZO ReglaNegocioViolada", {"SN-LAP-0003": "DISPONIBLE"}),
    "E04": ("RECHAZO ReglaNegocioViolada", {"SN-LAP-0004": "DISPONIBLE"}),
    "E05": ("RECHAZO ReglaNegocioViolada", {"SN-LAP-0005": "RESERVADO"}),
    "E06": ("OK", {"AP-0004": "ACTIVO"}),
    "E07": ("OK", {"AP-0004": "LIQUIDADO"}),
    "E08": ("RECHAZO DatosInvalidos", {"AP-0004": "ACTIVO"}),
    "E09": ("OK", {"AP-0005": "ACTIVO"}),
    "E10": ("OK", {"AP-0005": "VENCIDO"}),
    "E11": ("RECHAZO TransicionInvalida", {"AP-0005": "VENCIDO"}),
    "E12": ("OK", {"AP-0004": "ENTREGADO"}),
    "E13": ("RECHAZO TransicionInvalida", {"SN-LAP-0005": "RESERVADO"}),
    "E14": ("OK", {"SN-LAP-0011": "DISPONIBLE"}),
    "E15": ("RECHAZO ReglaNegocioViolada", {"SN-LAP-0012": "VENDIDO"}),
}


@pytest.mark.parametrize("backend", ["memoria", "sql"])
@pytest.mark.parametrize("caso", filas("escenarios.csv"),
                         ids=lambda x: x["caso_id"])
def test_escenario(caso, backend):
    """Mismo oráculo para ambas persistencias (prueba de contrato)."""
    c = construir_sql() if backend == "sql" else construir()
    c, _, _, resultado, _ = ejecutar(caso, c)
    prefijo, finales = ESPERADO[caso["caso_id"]]
    assert resultado.startswith(prefijo), resultado
    for clave, estado in finales.items():
        assert estado_de(c, clave) == estado


def test_hay_15_escenarios_y_todos_tienen_oraculo():
    assert {x["caso_id"] for x in filas("escenarios.csv")} == set(ESPERADO)
    assert len(ESPERADO) == 15
