"""Servicios de aplicación + infraestructura en memoria (integración)."""
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.application.dto import (
    ConsultarStockGlobalQuery,
    CrearApartadoCommand,
    LineaVentaCommand,
    PagoCommand,
    ProcesarDevolucionCommand,
    ProcesarVentaDirectaCommand,
    RegistrarAbonoCommand,
)
from src.domain.errores import (
    DatosInvalidos,
    NoAutorizado,
    RecursoNoEncontrado,
    ReglaNegocioViolada,
    TransicionInvalida,
)
from src.domain.item_serie import EstadoSerie
from src.domain.valores import MontoMonetario

HOY = date(2026, 11, 5)
D = Decimal


def apartar(c, cliente="TEC-C001", serie="SN-LAP-0001", anticipo="67.20", hoy=HOY):
    return c.apartados.crear_apartado(
        CrearApartadoCommand(cliente, serie, D(anticipo)), hoy)


def test_crear_apartado_reserva_la_serie_y_publica_eventos(c):
    dto = apartar(c)
    assert dto.estado == "ACTIVO" and dto.saldo == "268.80"
    assert c.almacen.items["SN-LAP-0001"].estado == EstadoSerie.RESERVADO
    assert [e.nombre for e in c.bus.publicados] == [
        "SerieBloqueadaEvent", "ApartadoCreadoEvent"]


def test_crear_apartado_rechazado_hace_rollback_y_no_publica(c):
    with pytest.raises(ReglaNegocioViolada):
        apartar(c, anticipo="67.19")
    assert c.almacen.items["SN-LAP-0001"].estado == EstadoSerie.DISPONIBLE
    assert c.bus.publicados == []


def test_rollback_deshace_cambios_si_falla_a_mitad_de_operacion(c):
    """El ItemSerie se bloquea ANTES de fallar Apartado.crear: debe revertirse."""
    p = c.almacen.productos["TEC-P001"]
    c.almacen.productos["TEC-P001"] = replace(p, precio=MontoMonetario.de("0"))
    with pytest.raises(DatosInvalidos):      # total 0: falla dentro de Apartado.crear
        apartar(c, anticipo="0.00")
    assert c.almacen.items["SN-LAP-0001"].estado == EstadoSerie.DISPONIBLE


@pytest.mark.parametrize("kw, exc", [
    (dict(cliente="NOPE"), RecursoNoEncontrado),
    (dict(serie="SN-NO-EXISTE"), RecursoNoEncontrado),
    (dict(cliente="TEC-C007", serie="SN-LAP-0003"), ReglaNegocioViolada),
    (dict(cliente="TEC-C004", serie="SN-LAP-0004"), ReglaNegocioViolada),
    (dict(serie="SN-LAP-0005", anticipo="124.00"), ReglaNegocioViolada),
])
def test_crear_apartado_rechazos(c, kw, exc):
    with pytest.raises(exc):
        apartar(c, **kw)


def test_cuarto_apartado_si_se_libera_uno(c):
    c.apartados.procesar_vencimientos(date(2026, 12, 5))     # vencen los 3 de C004
    dto = apartar(c, cliente="TEC-C004", serie="SN-LAP-0004", hoy=date(2026, 12, 5))
    assert dto.estado == "ACTIVO"


def test_mensaje_de_rechazo_lista_todas_las_reglas_incumplidas(c):
    with pytest.raises(ReglaNegocioViolada) as e:
        apartar(c, cliente="TEC-C007", serie="SN-LAP-0005", anticipo="1.00")
    msg = str(e.value)
    assert "inactivo" in msg and "20%" in msg and "no está DISPONIBLE" in msg


def test_abono_liquida_y_entrega_marca_serie_vendida(c):
    c.apartados.registrar_abono(RegistrarAbonoCommand("AP-0004", D("723.20")),
                                date(2026, 11, 3))
    dto = c.apartados.entregar_apartado("AP-0004")
    assert dto.estado == "ENTREGADO"
    assert c.almacen.items["SN-LAP-0008"].estado == EstadoSerie.VENDIDO


def test_entregar_sin_liquidar_hace_rollback(c):
    with pytest.raises(TransicionInvalida):
        c.apartados.entregar_apartado("AP-0004")
    assert c.almacen.items["SN-LAP-0008"].estado == EstadoSerie.RESERVADO


def test_abono_a_apartado_inexistente(c):
    with pytest.raises(RecursoNoEncontrado):
        c.apartados.registrar_abono(RegistrarAbonoCommand("AP-9999", D("1")), HOY)


def test_vencimiento_libera_serie_penaliza_y_notifica(c):
    r = c.apartados.procesar_vencimientos(date(2026, 11, 6))
    assert r.vencidos == ["AP-0005"] and r.saldo_a_favor_total == "162.72"
    assert c.almacen.items["SN-LAP-0009"].estado == EstadoSerie.DISPONIBLE
    assert "SMS/correo a TEC-C006" in c.notificaciones.notificaciones[0]


def test_vencimiento_dia_30_no_vence_y_segunda_corrida_no_repite(c):
    assert c.apartados.procesar_vencimientos(date(2026, 11, 5)).vencidos == []
    c.apartados.procesar_vencimientos(date(2026, 11, 6))
    assert c.apartados.procesar_vencimientos(date(2026, 11, 7)).vencidos == []
    assert len(c.notificaciones.notificaciones) == 1


# ---------- ventas y devoluciones ----------
def vender(c, serie, hoy=HOY, monto=None, sku="TEC-P002"):
    precio = c.almacen.productos[sku].precio.cantidad
    return c.ventas.procesar_venta_directa(ProcesarVentaDirectaCommand(
        "SUC-05", [LineaVentaCommand(sku, serie)],
        [PagoCommand("EFECTIVO", monto or precio)]), hoy)


def test_venta_directa_marca_vendida_y_genera_ticket(c):
    t = vender(c, "SN-MON-0001")
    assert t.ticket_id == "V-0003" and t.total == "407.00"
    assert c.almacen.items["SN-MON-0001"].estado == EstadoSerie.VENDIDO


def test_venta_con_pago_incorrecto_no_vende_la_serie(c):
    with pytest.raises(ReglaNegocioViolada):
        vender(c, "SN-MON-0001", monto=D("1.00"))
    assert c.almacen.items["SN-MON-0001"].estado == EstadoSerie.DISPONIBLE


def test_venta_serie_que_no_corresponde_al_sku(c):
    with pytest.raises(DatosInvalidos):
        vender(c, "SN-MON-0001", sku="TEC-P006")


def test_venta_sku_inexistente_o_deshabilitado(c):
    with pytest.raises(RecursoNoEncontrado):
        vender(c, None, sku="TEC-P011")    # SSD deshabilitado en catálogo


def test_venta_sin_serie_requerida(c):
    with pytest.raises(ReglaNegocioViolada):
        vender(c, None)


def devolver(c, ticket="V-0001", serie="SN-LAP-0011", clave="SUP-001",
             hoy=HOY, **kw):
    return c.devoluciones.procesar_devolucion_especial(
        ProcesarDevolucionCommand(ticket, serie, clave, "x", **kw), hoy)


def test_devolucion_ok_reingresa_serie_y_emite_nota(c):
    nota = devolver(c)
    assert nota.monto == "1188.00" and nota.autorizada_por == "SUP-001"
    assert c.almacen.items["SN-LAP-0011"].estado == EstadoSerie.DISPONIBLE
    assert c.bus.publicados[-1].nombre == "DevolucionAutorizadaEvent"


def test_devolucion_dia_15_si_dia_16_no(c):
    assert devolver(c, hoy=date(2026, 10, 30))     # V-0001 es del 2026-10-28 (día 2)
    with pytest.raises(ReglaNegocioViolada):
        devolver(c, "V-0002", "SN-LAP-0012", hoy=date(2026, 11, 1))   # día 17
    assert devolver(c, "V-0002", "SN-LAP-0012", hoy=date(2026, 10, 30))  # día 15


@pytest.mark.parametrize("kw, exc", [
    (dict(clave="SUP-999"), NoAutorizado),
    (dict(clave="SUP-002"), NoAutorizado),         # supervisor inactivo
    (dict(clave=""), NoAutorizado),
    (dict(dano_cliente=True), ReglaNegocioViolada),
    (dict(empaque_original=False), ReglaNegocioViolada),
    (dict(accesorios_completos=False), ReglaNegocioViolada),
    (dict(ticket="V-9999"), RecursoNoEncontrado),
    (dict(serie="SN-LAP-0012"), DatosInvalidos),    # serie de otro ticket
])
def test_devolucion_rechazos_sin_cambiar_estado(c, kw, exc):
    with pytest.raises(exc):
        devolver(c, **kw)
    assert c.almacen.items["SN-LAP-0011"].estado == EstadoSerie.VENDIDO
    assert c.bus.publicados == []


def test_devolucion_no_se_repite(c):
    devolver(c)
    with pytest.raises(TransicionInvalida):
        devolver(c)


# ---------- CQRS: consulta ----------
def test_stock_global_agrupa_por_sku_y_sucursal(c):
    filas = c.stock.handle(ConsultarStockGlobalQuery(sku="TEC-P005"))
    assert [(f.sucursal_id, f.disponibles, f.reservados) for f in filas] == [
        ("SUC-01", 0, 2), ("SUC-03", 0, 1)]


def test_stock_global_filtra_por_sucursal_y_no_modifica(c):
    antes = [i.estado for i in c.almacen.items.values()]
    filas = c.stock.handle(ConsultarStockGlobalQuery(sucursal_id="SUC-05"))
    assert sum(f.disponibles for f in filas) == 2
    assert antes == [i.estado for i in c.almacen.items.values()]


def test_rechazo_de_anticipo_informa_minimo_y_faltante(c):    # TDD ciclo 1 (US-03)
    with pytest.raises(ReglaNegocioViolada) as e:
        apartar(c, anticipo="67.19")
    assert "mínimo 67.20" in str(e.value) and "faltan 0.01" in str(e.value)
