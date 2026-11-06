"""Carga los CSV de datos/ en el dominio y arma el contenedor de dependencias."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from src.domain.apartado import Apartado
from src.domain.entidades import Cliente, Producto
from src.domain.item_serie import EstadoSerie, ItemSerie
from src.domain.valores import SKU, MontoMonetario, NumeroSerie, SucursalId
from src.domain.venta import LineaVenta, Pago, Venta
from src.infrastructure.memoria import (
    Almacen,
)

DATOS = Path(__file__).resolve().parents[2] / "datos"


def filas(nombre: str, base: Path = DATOS) -> list[dict]:
    with (base / nombre).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cargar_almacen(base: Path = DATOS) -> Almacen:
    a = Almacen()
    for r in filas("clientes.csv", base):
        a.clientes[r["cliente_id"]] = Cliente(
            r["cliente_id"], r["nombre"], r["telefono"], r["correo"],
            bool(int(r["activo"])))
    for r in filas("productos.csv", base):
        a.productos[r["sku"]] = Producto(
            SKU(r["sku"]), r["descripcion"], MontoMonetario.de(r["precio_mxn"]),
            bool(int(r["requiere_serie"])), bool(int(r["habilitado"])))
    for r in filas("series.csv", base):
        a.items[r["numero_serie"]] = ItemSerie(
            NumeroSerie(r["numero_serie"]), SKU(r["sku"]),
            SucursalId(r["sucursal_id"]), EstadoSerie(r["estado_inicial"]))
    for r in filas("supervisores.csv", base):
        a.supervisores[r["clave"]] = bool(int(r["activo"]))
    # Apartados históricos: se crean con las reglas del dominio.
    for r in filas("apartados.csv", base):
        item = a.items[r["numero_serie"]]
        precio = a.productos[item.sku.valor].precio
        item.bloquear_para_reserva()
        a.apartados[r["folio"]] = Apartado.crear(
            r["folio"], r["cliente_id"], item.numero_serie,
            SucursalId(r["sucursal_id"]), precio,
            MontoMonetario.de(r["anticipo_mxn"]),
            date.fromisoformat(r["fecha_creacion"]))
    # Ventas históricas
    for r in filas("ventas.csv", base):
        p = a.productos[r["sku"]]
        serie = NumeroSerie(r["numero_serie"])
        a.items[serie.valor].marcar_como_vendido()
        precio = MontoMonetario.de(r["precio_mxn"])
        a.ventas[r["ticket_id"]] = Venta.cerrar(
            r["ticket_id"], date.fromisoformat(r["fecha"]), r["sucursal_id"],
            [LineaVenta(p.sku, precio, p.requiere_serie, serie)],
            [Pago(r["metodo_pago"], precio)])
    # Los eventos de la carga no forman parte de la historia de los escenarios.
    for ag in [*a.items.values(), *a.apartados.values(), *a.ventas.values()]:
        ag.extraer_eventos()
    return a


def main() -> None:
    a = cargar_almacen()
    print(f"clientes={len(a.clientes)} productos={len(a.productos)} "
          f"series={len(a.items)} apartados={len(a.apartados)} "
          f"ventas={len(a.ventas)}")
    for ap in a.apartados.values():
        print(ap.folio, ap.estado.value, ap.cliente_id, ap.numero_serie.valor,
              "total", ap.total, "saldo", ap.saldo, "limite", ap.fecha_limite)


if __name__ == "__main__":
    main()
