"""Servicio externo (pasarela de pagos) sustituido por Mock: no hay cobros reales."""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.application.dto import (
    LineaVentaCommand,
    PagoCommand,
    ProcesarVentaDirectaCommand,
)
from src.domain.errores import PagoRechazado, ServicioNoDisponible
from src.domain.item_serie import EstadoSerie
from src.domain.puertos import IPasarelaPagos
from src.domain.valores import MontoMonetario
from src.infrastructure.contenedor import construir

HOY = date(2026, 11, 5)


def contenedor(**config):
    pasarela = Mock(spec=IPasarelaPagos)
    pasarela.cobrar.configure_mock(**config)
    return construir(pasarela=pasarela), pasarela


def venta(c, pagos):
    return c.ventas.procesar_venta_directa(ProcesarVentaDirectaCommand(
        "SUC-05", [LineaVentaCommand("TEC-P002", "SN-MON-0001")], pagos), HOY)


def test_pago_aprobado_cobra_una_vez_con_ticket_como_referencia():
    c, pasarela = contenedor(return_value=True)
    t = venta(c, [PagoCommand("TARJETA", Decimal("407.00"))])
    pasarela.cobrar.assert_called_once_with(
        MontoMonetario.de("407.00"), "TARJETA", t.ticket_id)
    assert c.almacen.items["SN-MON-0001"].estado == EstadoSerie.VENDIDO


def test_pago_rechazado_lanza_error_y_no_vende_la_serie():
    c, pasarela = contenedor(return_value=False)
    with pytest.raises(PagoRechazado):
        venta(c, [PagoCommand("TARJETA", Decimal("407.00"))])
    pasarela.cobrar.assert_called_once()
    assert c.almacen.items["SN-MON-0001"].estado == EstadoSerie.DISPONIBLE
    assert "V-0003" not in c.almacen.ventas and c.bus.publicados == []


def test_timeout_de_pasarela_es_servicio_no_disponible_y_hace_rollback():
    c, _ = contenedor(side_effect=TimeoutError)
    with pytest.raises(ServicioNoDisponible):
        venta(c, [PagoCommand("TARJETA", Decimal("407.00"))])
    assert c.almacen.items["SN-MON-0001"].estado == EstadoSerie.DISPONIBLE


def test_efectivo_no_invoca_la_pasarela():
    c, pasarela = contenedor(return_value=True)
    venta(c, [PagoCommand("EFECTIVO", Decimal("407.00"))])
    pasarela.cobrar.assert_not_called()


def test_pago_combinado_solo_cobra_la_parte_de_tarjeta():
    c, pasarela = contenedor(return_value=True)
    venta(c, [PagoCommand("EFECTIVO", Decimal("107.00")),
              PagoCommand("TARJETA", Decimal("300.00"))])
    pasarela.cobrar.assert_called_once_with(
        MontoMonetario.de("300.00"), "TARJETA", "V-0003")


def test_pagos_descuadrados_no_llegan_a_la_pasarela():
    c, pasarela = contenedor(return_value=True)
    with pytest.raises(Exception):
        venta(c, [PagoCommand("TARJETA", Decimal("1.00"))])
    pasarela.cobrar.assert_not_called()


@pytest.mark.parametrize("config, status", [
    (dict(return_value=False), 402), (dict(side_effect=TimeoutError), 503)])
def test_api_traduce_fallos_de_pasarela(config, status):
    c, _ = contenedor(**config)
    r = TestClient(crear_app(c), headers={"X-Rol": "CAJERO"}).post("/ventas", json={
        "sucursal_id": "SUC-05", "fecha": "2026-11-05",
        "lineas": [{"sku": "TEC-P002", "numero_serie": "SN-MON-0001"}],
        "pagos": [{"metodo": "TARJETA", "monto": "407.00"}]})
    assert r.status_code == status


def test_pasarela_simulada_por_defecto_no_hace_cobros_reales():
    c = construir()
    venta(c, [PagoCommand("TARJETA", Decimal("407.00"))])
    assert c.ventas.pasarela.cobros == [("V-0003", "407.00")]   # sólo bitácora local
