"""Reproduce localmente los pasos de .github/workflows/ci.yml.

Uso:  python tools/ci_local.py [carpeta_del_proyecto]
Sale con código != 0 si algún paso falla (igual que el job de Actions).
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
PY = sys.executable
PASOS = [
    ("Lint (ruff)", [PY, "-m", "ruff", "check", "src", "tests"]),
    ("Pruebas + cobertura >= 80%", [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                    "--cov=src", "--cov-fail-under=80"]),
    ("Escenarios E01-E15", [PY, "ejecutar_escenarios.py"]),
    ("Compilar src/", [PY, "-m", "compileall", "-q", "src"]),
]

for nombre, cmd in PASOS:
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True,
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    ultimo = (r.stdout.strip().splitlines() or [""])[-1][:110]
    print(f"[{'OK' if r.returncode == 0 else 'FALLO'}] {nombre}: {ultimo}")
    if r.returncode:
        print("   ", *[x for x in r.stdout.splitlines() if x.startswith("FAILED")][:3],
              sep="\n    ")
        sys.exit(r.returncode)
print("PIPELINE VERDE")
