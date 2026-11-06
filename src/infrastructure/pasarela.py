"""Adaptador de pasarela SIMULADO: no hace llamadas de red ni cobros reales.

En producción se sustituye por un adaptador del proveedor real; el dominio y la
capa de aplicación sólo conocen IPasarelaPagos.
"""
from __future__ import annotations

from src.domain.puertos import IPasarelaPagos
from src.domain.valores import MontoMonetario


class PasarelaSimulada(IPasarelaPagos):
    def __init__(self) -> None:
        self.cobros: list[tuple[str, str]] = []

    def cobrar(self, monto: MontoMonetario, metodo: str,
               referencia: str) -> bool:
        self.cobros.append((referencia, str(monto)))
        return True
