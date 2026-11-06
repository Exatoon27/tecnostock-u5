"""PoliticaDevolucionDomainService (CU-05): elegibilidad + firma de Supervisor.

OCP (hallazgo U3): cada política es una clase que cumple IPoliticaDevolucion;
agregar una categoría nueva no obliga a editar el servicio.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.errores import NoAutorizado, ReglaNegocioViolada
from src.domain.especificaciones import REGLAS_DEVOLUCION, SolicitudDevolucion
from src.domain.eventos import DevolucionAutorizadaEvent
from src.domain.valores import MontoMonetario


class ISupervisorAuthDomainService(ABC):
    @abstractmethod
    def validar(self, clave: str) -> bool: ...


class IPoliticaDevolucion(ABC):
    @abstractmethod
    def motivos_de_rechazo(self, s: SolicitudDevolucion) -> list[str]: ...


class PoliticaDevolucionSerieStandard(IPoliticaDevolucion):
    """Equipos con serie: plazo 15 días, empaque completo, sin daño."""

    def motivos_de_rechazo(self, s: SolicitudDevolucion) -> list[str]:
        return [msg for msg, regla in REGLAS_DEVOLUCION
                if not regla.se_cumple(s)]


@dataclass(frozen=True)
class NotaCredito:
    ticket_id: str
    numero_serie: str
    monto: MontoMonetario
    autorizada_por: str


class PoliticaDevolucionDomainService:
    def __init__(self, auth: ISupervisorAuthDomainService,
                 politica: IPoliticaDevolucion | None = None) -> None:
        self.auth = auth
        self.politica = politica or PoliticaDevolucionSerieStandard()

    def autorizar(self, ticket_id: str, numero_serie: str, monto: MontoMonetario,
                  solicitud: SolicitudDevolucion, clave_supervisor: str,
                  ) -> tuple[NotaCredito, DevolucionAutorizadaEvent]:
        motivos = self.politica.motivos_de_rechazo(solicitud)
        if motivos:       # el rechazo por política no requiere Supervisor
            raise ReglaNegocioViolada("Devolución rechazada: "
                                      + "; ".join(motivos))
        if not clave_supervisor or not self.auth.validar(clave_supervisor):
            raise NoAutorizado("Se requiere la clave de un Supervisor válido")
        nota = NotaCredito(ticket_id, numero_serie, monto, clave_supervisor)
        return nota, DevolucionAutorizadaEvent(
            ticket_id, {"serie": numero_serie, "monto": str(monto),
                        "supervisor": clave_supervisor})
