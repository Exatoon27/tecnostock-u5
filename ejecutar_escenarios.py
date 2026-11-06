"""Ejecuta E01-E15 (datos/escenarios.csv) sobre datos recién cargados y
genera bitacora.md con precondiciones, operación, resultado, evento y prueba."""
from datetime import date
from decimal import Decimal

from src.application.dto import (
    CrearApartadoCommand,
    LineaVentaCommand,
    PagoCommand,
    ProcesarDevolucionCommand,
    ProcesarVentaDirectaCommand,
    RegistrarAbonoCommand,
)
from src.domain.valores import NumeroSerie
from src.infrastructure.carga_csv import filas
from src.infrastructure.contenedor import construir

# Prueba automatizada que cubre cada escenario (tests/test_escenarios.py).
PRUEBA = "tests/test_escenarios.py::test_escenario[{}-memoria o sql]"


def parametros(texto: str) -> dict:
    return dict(p.split("=", 1) for p in texto.split(";"))


def estado_de(c, clave: str) -> str:
    """Estado de un apartado (folio) o de una serie, leído vía repositorio."""
    with c.uow_factory() as uow:
        ag = (uow.apartados.find_by_id(clave)
              or uow.items.find_by_serie(NumeroSerie(clave)))
        return ag.estado.value


def ejecutar(caso: dict, c=None):
    c = c or construir()
    p, hoy = parametros(caso["parametros"]), date.fromisoformat(caso["fecha"])
    accion = caso["accion"]
    pasos: list[str] = []

    def op(texto, fn):
        pasos.append(texto)
        try:
            return "OK", fn()
        except Exception as exc:   # el rechazo ES el resultado esperado
            return f"RECHAZO {type(exc).__name__}: {exc}", None

    if accion == "crear_apartado":
        res, _ = op(f"crear_apartado({p['cliente']}, {p['serie']}, "
                    f"anticipo {p['anticipo']})",
                    lambda: c.apartados.crear_apartado(CrearApartadoCommand(
                        p["cliente"], p["serie"], Decimal(p["anticipo"])), hoy))
    elif accion == "registrar_abono":
        res, _ = op(f"registrar_abono({p['folio']}, {p['monto']})",
                    lambda: c.apartados.registrar_abono(RegistrarAbonoCommand(
                        p["folio"], Decimal(p["monto"])), hoy))
    elif accion == "procesar_vencimientos":
        res, _ = op(f"procesar_vencimientos({hoy})",
                    lambda: c.apartados.procesar_vencimientos(hoy))
    elif accion == "abono_tras_vencimiento":
        c.apartados.procesar_vencimientos(hoy)
        pasos.append(f"procesar_vencimientos({hoy})")
        res, _ = op(f"registrar_abono({p['folio']}, {p['monto']})",
                    lambda: c.apartados.registrar_abono(RegistrarAbonoCommand(
                        p["folio"], Decimal(p["monto"])), hoy))
    elif accion == "entregar_apartado":
        c.apartados.registrar_abono(RegistrarAbonoCommand(
            p["folio"], Decimal(p["monto"])), hoy)
        pasos.append(f"registrar_abono({p['folio']}, {p['monto']})")
        res, _ = op(f"entregar_apartado({p['folio']})",
                    lambda: c.apartados.entregar_apartado(p["folio"]))
    elif accion == "venta_directa":
        with c.uow_factory() as uow:
            item = uow.items.find_by_serie(NumeroSerie(p["serie"]))
            sku = item.sku.valor
            precio = uow.productos.find_by_sku(item.sku).precio.cantidad
        res, _ = op(f"venta_directa({p['serie']})",
                    lambda: c.ventas.procesar_venta_directa(
                        ProcesarVentaDirectaCommand(
                            "SUC-01", [LineaVentaCommand(sku, p["serie"])],
                            [PagoCommand(p["metodo"], precio)]), hoy))
    elif accion == "devolucion":
        res, _ = op(f"devolucion({p['ticket']}, {p['serie']}, {p['clave']})",
                    lambda: c.devoluciones.procesar_devolucion_especial(
                        ProcesarDevolucionCommand(
                            p["ticket"], p["serie"], p["clave"], "prueba"), hoy))
    else:
        raise ValueError(accion)
    eventos = [e.nombre for e in c.bus.publicados] or ["Ninguno"]
    return c, p, pasos, res, eventos


def estado_final(c, p) -> str:
    return ", ".join(f"{p[k]}={estado_de(c, p[k])}"
                     for k in ("folio", "serie") if k in p)


def main() -> None:
    lineas = ["# Bitácora de escenarios E01-E15 (TecnoStock)\n",
              "| Caso | Precondiciones (datos) | Operación | Resultado real | "
              "Evento(s) | Estado final | Prueba |",
              "|---|---|---|---|---|---|---|"]
    for caso in filas("escenarios.csv"):
        c, p, pasos, res, eventos = ejecutar(caso)
        lineas.append(
            f"| {caso['caso_id']} | {caso['parametros']} ({caso['fecha']}) | "
            f"{' → '.join(pasos)} | {res} | {', '.join(eventos)} | "
            f"{estado_final(c, p)} | {PRUEBA.format(caso['caso_id'])} |")
        print(caso["caso_id"], res, "|", ", ".join(eventos))
    with open("bitacora.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print("bitacora.md generada")


if __name__ == "__main__":
    main()
