"""Ejecuta pytest y llena la matriz con el RESULTADO REAL de cada caso.

Uso:  python tools/generar_matriz.py
Entrada: docs/matriz_pruebas_base.csv   Salida: docs/matriz_pruebas.csv
"""
import csv
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def ejecutar_pytest() -> dict[str, list[str]]:
    """funcion -> lista de resultados (passed/failed/skipped) de sus casos."""
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={xml}"], cwd=RAIZ, capture_output=True)
        resultados: dict[str, list[str]] = {}
        for caso in ET.parse(xml).getroot().iter("testcase"):
            nombre = caso.get("name").split("[")[0]
            estado = ("failed" if caso.find("failure") is not None
                      or caso.find("error") is not None
                      else "skipped" if caso.find("skipped") is not None else "passed")
            resultados.setdefault(nombre, []).append(estado)
        return resultados


def main() -> int:
    resultados = ejecutar_pytest()
    entrada = RAIZ / "docs" / "matriz_pruebas_base.csv"
    with entrada.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    for fila in filas:
        r = resultados.get(fila["funcion"], [])
        fila["casos_ejecutados"] = str(len(r))
        fila["resultado_real"] = ("NO ENCONTRADA" if not r else
                                  "PASSED" if set(r) == {"passed"} else "FAILED")
    salida = RAIZ / "docs" / "matriz_pruebas.csv"
    with salida.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    malos = [x["caso_id"] for x in filas if x["resultado_real"] != "PASSED"]
    por_tipo = {t: sum(1 for x in filas if x["tipo"] == t)
                for t in ("exito", "error", "limite")}
    print(f"{len(filas)} casos {por_tipo}; fallidos/no encontrados: {malos or 'ninguno'}")
    return 1 if malos else 0


if __name__ == "__main__":
    raise SystemExit(main())
