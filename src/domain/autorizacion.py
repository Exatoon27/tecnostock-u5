"""Autorización por política (rol -> acción). Autenticación != autorización.

Fuente: BRD y levantamiento (p.11, p.12): el Cajero sólo selecciona método de pago,
escanea series y captura facturación; descuentos excepcionales, cancelaciones y
devoluciones son del Supervisor; Almacén no modifica precios.
SUPUESTO a validar: Almacén puede entregar un apartado liquidado (despacho).
"""
from __future__ import annotations

from enum import Enum

from src.domain.errores import NoAutenticado, NoAutorizado


class Rol(str, Enum):
    CLIENTE = "CLIENTE"
    VENDEDOR = "VENDEDOR"
    CAJERO = "CAJERO"
    SUPERVISOR = "SUPERVISOR"
    ALMACEN = "ALMACEN"
    ADMINISTRADOR = "ADMINISTRADOR"
    SISTEMA = "SISTEMA"        # proceso nocturno


class Accion(str, Enum):
    CONSULTAR_STOCK = "CONSULTAR_STOCK"
    CONSULTAR_APARTADO = "CONSULTAR_APARTADO"
    CREAR_APARTADO = "CREAR_APARTADO"
    REGISTRAR_ABONO = "REGISTRAR_ABONO"
    ENTREGAR_APARTADO = "ENTREGAR_APARTADO"
    PROCESAR_VENTA = "PROCESAR_VENTA"
    PROCESAR_DEVOLUCION = "PROCESAR_DEVOLUCION"
    PROCESAR_VENCIMIENTOS = "PROCESAR_VENCIMIENTOS"


_R, _A = Rol, Accion
PERMISOS: dict[Accion, frozenset[Rol]] = {
    _A.CONSULTAR_STOCK: frozenset({_R.VENDEDOR, _R.CAJERO, _R.SUPERVISOR,
                                   _R.ALMACEN, _R.ADMINISTRADOR}),
    _A.CONSULTAR_APARTADO: frozenset({_R.VENDEDOR, _R.CAJERO, _R.SUPERVISOR,
                                      _R.ADMINISTRADOR}),
    _A.CREAR_APARTADO: frozenset({_R.VENDEDOR, _R.CAJERO, _R.SUPERVISOR}),
    _A.REGISTRAR_ABONO: frozenset({_R.CAJERO, _R.SUPERVISOR}),
    _A.ENTREGAR_APARTADO: frozenset({_R.CAJERO, _R.ALMACEN, _R.SUPERVISOR}),
    _A.PROCESAR_VENTA: frozenset({_R.CAJERO, _R.SUPERVISOR}),
    # El Cajero inicia el trámite; la clave del Supervisor sigue siendo
    # obligatoria en el dominio (PoliticaDevolucionDomainService).
    _A.PROCESAR_DEVOLUCION: frozenset({_R.CAJERO, _R.SUPERVISOR}),
    _A.PROCESAR_VENCIMIENTOS: frozenset({_R.SISTEMA, _R.SUPERVISOR,
                                         _R.ADMINISTRADOR}),
}


def puede(rol: Rol, accion: Accion) -> bool:
    return rol in PERMISOS[accion]


def exigir(rol_texto: str | None, accion: Accion) -> Rol:
    """401 si no hay rol reconocible; 403 si el rol no tiene permiso."""
    try:
        rol = Rol(rol_texto or "")
    except ValueError:
        raise NoAutenticado("Se requiere el encabezado X-Rol con un rol válido") from None
    if not puede(rol, accion):
        raise NoAutorizado(f"El rol {rol.value} no puede {accion.value}")
    return rol
