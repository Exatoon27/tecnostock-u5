"""Puertos hacia servicios externos (Ports & Adapters)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.valores import MontoMonetario


class IPasarelaPagos(ABC):
    @abstractmethod
    def cobrar(self, monto: MontoMonetario, metodo: str,
               referencia: str) -> bool:
        """True = aprobado, False = rechazado. Puede lanzar TimeoutError."""
