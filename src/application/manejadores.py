"""Reacciones a Domain Events, desacopladas del dominio (hallazgo SOLID-S, U3)."""
from __future__ import annotations

from src.domain.eventos import EventoDominio


class ApartadoVencidoEventHandler:
    """Simula el aviso SMS/correo al cliente cuando un apartado vence."""

    def __init__(self) -> None:
        self.notificaciones: list[str] = []

    def __call__(self, evento: EventoDominio) -> None:
        self.notificaciones.append(
            f"SMS/correo a {evento.datos['cliente']}: apartado "
            f"{evento.agregado_id} vencido; saldo a favor "
            f"{evento.datos['saldo_a_favor']} MXN")
