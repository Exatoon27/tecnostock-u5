"""Commands, Queries y DTOs de lectura (CQRS básico, ADR-02)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


# ---------- Commands (cambian estado) ----------
@dataclass(frozen=True)
class CrearApartadoCommand:
    cliente_id: str
    numero_serie: str
    anticipo: Decimal
    sucursal_id: str | None = None   # default: sucursal de la serie


@dataclass(frozen=True)
class RegistrarAbonoCommand:
    folio: str
    monto: Decimal


@dataclass(frozen=True)
class LineaVentaCommand:
    sku: str
    numero_serie: str | None = None


@dataclass(frozen=True)
class PagoCommand:
    metodo: str
    monto: Decimal


@dataclass(frozen=True)
class ProcesarVentaDirectaCommand:
    sucursal_id: str
    lineas: list[LineaVentaCommand]
    pagos: list[PagoCommand]


@dataclass(frozen=True)
class ProcesarDevolucionCommand:
    ticket_id: str
    numero_serie: str
    clave_supervisor: str
    motivo: str
    empaque_original: bool = True
    accesorios_completos: bool = True
    dano_cliente: bool = False


# ---------- Queries ----------
@dataclass(frozen=True)
class ConsultarStockGlobalQuery:
    sku: str | None = None
    sucursal_id: str | None = None


# ---------- DTOs de salida ----------
@dataclass(frozen=True)
class ApartadoDTO:
    folio: str
    cliente_id: str
    numero_serie: str
    sucursal_id: str
    estado: str
    total: str
    pagado: str
    saldo: str
    fecha_limite: date
    saldo_a_favor: str | None
    eventos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResumenProcesoVencimientoDTO:
    vencidos: list[str]
    saldo_a_favor_total: str


@dataclass(frozen=True)
class TicketConfirmacionDTO:
    ticket_id: str
    total: str
    series: list[str]


@dataclass(frozen=True)
class NotaCreditoDTO:
    ticket_id: str
    numero_serie: str
    monto: str
    autorizada_por: str


@dataclass(frozen=True)
class StockGlobalDTO:
    sku: str
    sucursal_id: str
    disponibles: int
    reservados: int
    vendidos: int
