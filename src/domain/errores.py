"""Excepciones de dominio. La API las traduce a HTTP (ver src/api/main.py)."""


class ErrorDominio(Exception):
    pass


class DatosInvalidos(ErrorDominio):
    """Dato mal formado (monto negativo, serie con formato inválido...). -> 422"""


class ReglaNegocioViolada(ErrorDominio):
    """Una regla del negocio impide la operación (anticipo < 20%...). -> 422"""


class TransicionInvalida(ErrorDominio):
    """El estado actual no permite la operación. -> 409"""


class NoAutorizado(ErrorDominio):
    """Falta o es inválida la autorización del Supervisor. -> 403"""


class RecursoNoEncontrado(ErrorDominio):
    """El agregado solicitado no existe. -> 404"""


class PagoRechazado(ErrorDominio):
    """La pasarela de pagos rechazó el cobro con tarjeta. -> 402"""


class ServicioNoDisponible(ErrorDominio):
    """Un servicio externo no respondió (timeout). -> 503"""


class NoAutenticado(ErrorDominio):
    """No se identificó al usuario (falta o es desconocido su rol). -> 401"""
