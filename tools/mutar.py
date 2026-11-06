"""Mutation sanity check: cada mutante debe hacer fallar al menos una prueba."""
import pathlib
import subprocess
import sys

PY = sys.argv[1]
NL = "\n"
MUT = [
    ("vencimiento '<=' -> '<'", "src/domain/apartado.py",
     "hoy <= self.fecha_limite", "hoy < self.fecha_limite"),
    ("anticipo 20% -> 10%", "src/domain/valores.py",
     'ANTICIPO_MINIMO = Decimal("0.20")', 'ANTICIPO_MINIMO = Decimal("0.10")'),
    ("penalizacion 10% -> 5%", "src/domain/apartado.py",
     'PENALIZACION = Decimal("0.10")', 'PENALIZACION = Decimal("0.05")'),
    ("limite 3 -> 4 apartados", "src/domain/especificaciones.py",
     "MAX_APARTADOS_ACTIVOS = 3", "MAX_APARTADOS_ACTIVOS = 4"),
    ("plazo devolucion 15 -> 16", "src/domain/especificaciones.py",
     "PLAZO_DEVOLUCION_DIAS = 15", "PLAZO_DEVOLUCION_DIAS = 16"),
    ("devolucion sin clave de supervisor", "src/domain/devolucion.py",
     "if not clave_supervisor or not self.auth.validar(clave_supervisor):",
     "if False:"),
    ("pagos que no cuadran se aceptan", "src/domain/venta.py",
     "if suma.cantidad != venta.total.cantidad:", "if False:"),
    ("serie repetida en ticket se acepta", "src/domain/venta.py",
     "if len(series) != len(set(series)):", "if False:"),
    ("pasarela rechazada se ignora", "src/application/servicios.py",
     "if not aprobado:", "if False:"),
    ("rol ALMACEN puede vender", "src/domain/autorizacion.py",
     "_A.PROCESAR_VENTA: frozenset({_R.CAJERO, _R.SUPERVISOR})",
     "_A.PROCESAR_VENTA: frozenset({_R.CAJERO, _R.SUPERVISOR, _R.ALMACEN})"),
    ("memoria: sin rollback al salir sin commit", "src/infrastructure/memoria.py",
     "        if self._foto is not None:     # no hubo commit -> rollback"
     + NL + "            self.rollback()", "        pass"),
    ("SQL: salir sin commit confirma en vez de revertir",
     "src/infrastructure/sql.py",
     "self.session.rollback()          # no-op si ya hubo commit",
     "self.session.commit()"),
    ("SQL: eventos publicados antes del commit", "src/infrastructure/sql.py",
     "        self.session.commit()" + NL + "        for e in eventos:" + NL
     + "            self.bus.publicar(e)",
     "        for e in eventos:" + NL + "            self.bus.publicar(e)" + NL
     + "        self.session.commit()"),
    ("SQL: sin indice unico de apartado vigente", "src/infrastructure/sql.py",
     "unique=True,", "unique=False,"),
]
for nombre, arch, a, b in MUT:
    p = pathlib.Path(arch)
    txt = p.read_text(encoding="utf-8")
    if a not in txt:
        print(f"{nombre:52} NO APLICA (texto no encontrado)")
        continue
    p.write_text(txt.replace(a, b, 1), encoding="utf-8")
    r = subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                        "--no-header"], capture_output=True, text=True)
    p.write_text(txt, encoding="utf-8")
    fallos = [x for x in r.stdout.splitlines() if x.startswith("FAILED")]
    if r.returncode == 0:
        estado = "SOBREVIVIO (no detectado)"
    else:
        estado = "DETECTADO -> " + (fallos[0][7:].split(" - ")[0] if fallos else "error")
    print(f"{nombre:52} {estado}")
