"""Specification Pattern: reglas de negocio con nombre, combinables AND/OR/NOT.

Una Specification sólo EVALÚA; no modifica nada (ver manual U4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.domain.item_serie import EstadoSerie
from src.domain.valores import MontoMonetario, PorcentajeAnticipo

MAX_APARTADOS_ACTIVOS = 3    # BRD levantamiento p.9
PLAZO_DEVOLUCION_DIAS = 15   # BRD levantamiento p.5


class Especificacion:
    def se_cumple(self, candidato) -> bool:
        raise NotImplementedError

    def __and__(self, otra: Especificacion) -> Especificacion:
        return _Y(self, otra)

    def __or__(self, otra: Especificacion) -> Especificacion:
        return _O(self, otra)

    def __invert__(self) -> Especificacion:
        return _No(self)


class _Y(Especificacion):
    def __init__(self, a, b):
        self.a, self.b = a, b

    def se_cumple(self, c):
        return self.a.se_cumple(c) and self.b.se_cumple(c)


class _O(Especificacion):
    def __init__(self, a, b):
        self.a, self.b = a, b

    def se_cumple(self, c):
        return self.a.se_cumple(c) or self.b.se_cumple(c)


class _No(Especificacion):
    def __init__(self, a):
        self.a = a

    def se_cumple(self, c):
        return not self.a.se_cumple(c)


# ---------- Apartar (CU-02) ----------
@dataclass(frozen=True)
class SolicitudApartado:
    cliente_activo: bool
    total: MontoMonetario
    anticipo: MontoMonetario
    apartados_activos_cliente: int
    estado_serie: EstadoSerie


class ClienteActivoSpec(Especificacion):
    def se_cumple(self, s: SolicitudApartado) -> bool:
        return s.cliente_activo


class AnticipoMinimoSpec(Especificacion):
    """Anticipo >= 20% del total (y no mayor al total)."""
    def se_cumple(self, s: SolicitudApartado) -> bool:
        return PorcentajeAnticipo.cumple(s.anticipo, s.total)


class LimiteApartadosSpec(Especificacion):
    """Máximo 3 apartados activos: con 3 ya no puede abrir otro."""
    def se_cumple(self, s: SolicitudApartado) -> bool:
        return s.apartados_activos_cliente < MAX_APARTADOS_ACTIVOS


class SerieDisponibleSpec(Especificacion):
    def se_cumple(self, s: SolicitudApartado) -> bool:
        return s.estado_serie == EstadoSerie.DISPONIBLE


# (mensaje de rechazo | función que lo calcula, regla). Se informan TODAS las
# que fallen.
REGLAS_APARTAR = [
    ("el cliente está inactivo", ClienteActivoSpec()),
    (lambda s: PorcentajeAnticipo.motivo_de_rechazo(s.anticipo, s.total),
     AnticipoMinimoSpec()),
    ("el cliente ya tiene 3 apartados activos", LimiteApartadosSpec()),
    ("la serie no está DISPONIBLE", SerieDisponibleSpec()),
]
PUEDE_APARTAR = (ClienteActivoSpec() & AnticipoMinimoSpec()
                 & LimiteApartadosSpec() & SerieDisponibleSpec())


# ---------- Devolver (CU-05) ----------
@dataclass(frozen=True)
class SolicitudDevolucion:
    fecha_venta: date
    hoy: date
    empaque_original: bool
    accesorios_completos: bool
    dano_cliente: bool


class DentroDePlazoSpec(Especificacion):
    """<= 15 días naturales desde la venta (día 15 aún procede)."""
    def se_cumple(self, s: SolicitudDevolucion) -> bool:
        return 0 <= (s.hoy - s.fecha_venta).days <= PLAZO_DEVOLUCION_DIAS


class EmpaqueCompletoSpec(Especificacion):
    def se_cumple(self, s: SolicitudDevolucion) -> bool:
        return s.empaque_original and s.accesorios_completos


class DanoClienteSpec(Especificacion):
    def se_cumple(self, s: SolicitudDevolucion) -> bool:
        return s.dano_cliente


REGLAS_DEVOLUCION = [
    ("fuera del plazo de 15 días", DentroDePlazoSpec()),
    ("falta empaque original o accesorios", EmpaqueCompletoSpec()),
    ("daño imputable al cliente", ~DanoClienteSpec()),
]
DEVOLUCION_ELEGIBLE = (DentroDePlazoSpec() & EmpaqueCompletoSpec()
                       & ~DanoClienteSpec())
