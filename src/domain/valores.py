"""Value Objects: inmutables, validados al crearse (ver mapa de dominio U3)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from src.domain.errores import DatosInvalidos, ReglaNegocioViolada

CENTAVOS = Decimal("0.01")
ANTICIPO_MINIMO = Decimal("0.20")   # BRD levantamiento p.2: anticipo >= 20%


@dataclass(frozen=True)
class MontoMonetario:
    cantidad: Decimal
    moneda: str = "MXN"

    def __post_init__(self) -> None:
        if not isinstance(self.cantidad, Decimal):
            raise DatosInvalidos("El monto debe ser Decimal (no float/int)")
        if not self.cantidad.is_finite() or self.cantidad < 0:
            raise DatosInvalidos("Monto inválido: no se admiten negativos")

    @classmethod
    def de(cls, valor: str | int | Decimal) -> MontoMonetario:
        if isinstance(valor, float):
            raise DatosInvalidos("No se admite float para dinero")
        try:
            cantidad = Decimal(str(valor)).quantize(CENTAVOS, ROUND_HALF_UP)
        except Exception as exc:
            raise DatosInvalidos(f"Monto ilegible: {valor!r}") from exc
        return cls(cantidad)

    def sumar(self, otro: MontoMonetario) -> MontoMonetario:
        self._misma_moneda(otro)
        return MontoMonetario(self.cantidad + otro.cantidad, self.moneda)

    def restar(self, otro: MontoMonetario) -> MontoMonetario:
        self._misma_moneda(otro)
        return MontoMonetario(self.cantidad - otro.cantidad, self.moneda)

    def por(self, factor: Decimal) -> MontoMonetario:
        return MontoMonetario(
            (self.cantidad * factor).quantize(CENTAVOS, ROUND_HALF_UP),
            self.moneda)

    def _misma_moneda(self, otro: MontoMonetario) -> None:
        if self.moneda != otro.moneda:
            raise DatosInvalidos("Monedas distintas")

    def __str__(self) -> str:
        return f"{self.cantidad:.2f}"


@dataclass(frozen=True)
class SKU:
    valor: str

    def __post_init__(self) -> None:
        if not self.valor or not self.valor.strip():
            raise DatosInvalidos("SKU vacío")


@dataclass(frozen=True)
class NumeroSerie:
    """Alfanumérico (con guiones) de 5-30 caracteres; si es sólo dígitos debe
    ser un IMEI de 15 dígitos."""
    valor: str

    def __post_init__(self) -> None:
        v = self.valor
        if not re.fullmatch(r"[A-Za-z0-9-]{5,30}", v or ""):
            raise DatosInvalidos(f"Número de serie inválido: {v!r}")
        if v.isdigit() and len(v) != 15:
            raise DatosInvalidos("Un IMEI debe tener 15 dígitos")


@dataclass(frozen=True)
class SucursalId:
    valor: str

    def __post_init__(self) -> None:
        if not self.valor or not self.valor.strip():
            raise DatosInvalidos("Sucursal vacía")


@dataclass(frozen=True)
class PorcentajeAnticipo:
    """Fracción anticipo/total; sólo existe si cumple el mínimo del 20%."""
    fraccion: Decimal

    @staticmethod
    def cumple(anticipo: MontoMonetario, total: MontoMonetario) -> bool:
        return (anticipo.cantidad <= total.cantidad
                and anticipo.cantidad >= PorcentajeAnticipo.minimo(total).cantidad)

    @staticmethod
    def minimo(total: MontoMonetario) -> MontoMonetario:
        """20% del total, redondeado HACIA ARRIBA al centavo (nunca menos)."""
        return MontoMonetario(
            (total.cantidad * ANTICIPO_MINIMO).quantize(CENTAVOS, ROUND_CEILING),
            total.moneda)

    @classmethod
    def motivo_de_rechazo(cls, anticipo: MontoMonetario,
                          total: MontoMonetario) -> str:
        """US-03: el rechazo indica el monto mínimo y lo que falta."""
        minimo = cls.minimo(total)
        if anticipo.cantidad > total.cantidad:
            return f"el anticipo {anticipo} excede el total {total}"
        falta = minimo.restar(anticipo)
        return (f"el anticipo debe ser >= 20% del total "
                f"(mínimo {minimo}, faltan {falta})")

    @classmethod
    def de(cls, anticipo: MontoMonetario,
           total: MontoMonetario) -> PorcentajeAnticipo:
        if total.cantidad <= 0:
            raise DatosInvalidos("El total del apartado debe ser mayor a 0")
        if not cls.cumple(anticipo, total):
            raise ReglaNegocioViolada(
                "Anticipo rechazado: " + cls.motivo_de_rechazo(anticipo, total))
        return cls(anticipo.cantidad / total.cantidad)
