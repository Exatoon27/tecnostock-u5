"""Domain Events (hechos ya ocurridos) y base de los Aggregate Roots."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EventoDominio:
    agregado_id: str
    datos: dict[str, Any] = field(default_factory=dict)
    ocurrido_en: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))

    @property
    def nombre(self) -> str:
        return type(self).__name__


# Nombres tomados del informe U3 (ficha de cada Aggregate).
class ApartadoCreadoEvent(EventoDominio): ...
class AbonoRegistradoEvent(EventoDominio): ...
class ApartadoLiquidadoEvent(EventoDominio): ...
class ApartadoVencidoEvent(EventoDominio): ...
class ApartadoEntregadoEvent(EventoDominio): ...
class SerieBloqueadaEvent(EventoDominio): ...
class SerieLiberadaEvent(EventoDominio): ...
class SerieVendidaEvent(EventoDominio): ...
class VentaCompletadaEvent(EventoDominio): ...
class DevolucionAutorizadaEvent(EventoDominio): ...


class RaizAgregada:
    """Acumula eventos; la capa de aplicación los publica tras el commit."""

    id_agregado: str

    def __init__(self) -> None:
        self.eventos: list[EventoDominio] = []

    def _emitir(self, tipo: type[EventoDominio], **datos: Any) -> None:
        self.eventos.append(tipo(self.id_agregado, datos))

    def extraer_eventos(self) -> list[EventoDominio]:
        eventos, self.eventos = self.eventos, []
        return eventos
