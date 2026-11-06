"""La matriz de casos no puede referirse a pruebas que no existen."""
import csv
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_cada_caso_de_la_matriz_apunta_a_una_prueba_real():
    with (RAIZ / "docs" / "matriz_pruebas_base.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) >= 12
    for fila in filas:
        texto = (RAIZ / "tests" / fila["archivo"]).read_text(encoding="utf-8")
        assert re.search(rf"def {fila['funcion']}\(", texto), fila["caso_id"]


def test_la_matriz_cubre_exito_error_y_limite():
    with (RAIZ / "docs" / "matriz_pruebas_base.csv").open(encoding="utf-8") as f:
        tipos = [x["tipo"] for x in csv.DictReader(f)]
    assert tipos.count("exito") >= 5
    assert tipos.count("error") >= 4
    assert tipos.count("limite") >= 3
