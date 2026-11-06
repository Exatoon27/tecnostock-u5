"""Aggregate Root Venta (CU-01): serie obligatoria y cuadratura de pagos."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.domain.errores import DatosInvalidos, ReglaNegocioViolada, TransicionInvalida
from src.domain.eventos import RaizAgregada, VentaCompletadaEvent
from src.domain.valores import SKU, MontoMonetario, NumeroSerie


@dataclass(frozen=True)
class LineaVenta:
    sku: SKU
    precio: MontoMonetario
    requiere_serie: bool
    numero_serie: NumeroSerie | None = None


@dataclass(frozen=True)
class Pago:
    metodo: str
    monto: MontoMonetario


class Venta(RaizAgregada):
    def __init__(self, ticket_id: str, fecha: date, sucursal_id: str,
                 lineas: list[LineaVenta], pagos: list[Pago]) -> None:
        super().__init__()
        self.ticket_id = ticket_id
        self.fecha = fecha
        self.sucursal_id = sucursal_id
        self.lineas = lineas
        self.pagos = pagos
        self.series_devueltas: set[str] = set()

    @property
    def id_agregado(self) -> str:  # type: ignore[override]
        return self.ticket_id

    @property
    def total(self) -> MontoMonetario:
        t = MontoMonetario(Decimal("0.00"))
        for linea in self.lineas:
            t = t.sumar(linea.precio)
        return t

    @classmethod
    def cerrar(cls, ticket_id: str, fecha: date, sucursal_id: str,
               lineas: list[LineaVenta], pagos: list[Pago]) -> Venta:
        if not lineas:
            raise DatosInvalidos("La venta requiere al menos una línea")
        if any(x.requiere_serie and x.numero_serie is None for x in lineas):
            raise ReglaNegocioViolada(
                "Falta escanear la serie de un artículo que la requiere")
        series = [x.numero_serie.valor for x in lineas if x.numero_serie]
        if len(series) != len(set(series)):
            raise ReglaNegocioViolada("La venta contiene una serie repetida")
        venta = cls(ticket_id, fecha, sucursal_id, lineas, pagos)
        suma = MontoMonetario(Decimal("0.00"))
        for p in pagos:
            suma = suma.sumar(p.monto)
        if suma.cantidad != venta.total.cantidad:
            raise ReglaNegocioViolada(
                f"Los pagos ({suma}) deben igualar el total ({venta.total})")
        venta._emitir(VentaCompletadaEvent, total=str(venta.total))
        return venta

    def linea_de(self, numero_serie: NumeroSerie) -> LineaVenta:
        for linea in self.lineas:
            if linea.numero_serie == numero_serie:
                return linea
        raise DatosInvalidos(
            f"La serie {numero_serie.valor} no pertenece al ticket "
            f"{self.ticket_id}")

    def registrar_devolucion(self, numero_serie: NumeroSerie) -> MontoMonetario:
        linea = self.linea_de(numero_serie)
        if numero_serie.valor in self.series_devueltas:
            raise TransicionInvalida("Esa serie ya fue devuelta")
        self.series_devueltas.add(numero_serie.valor)
        return linea.precio
