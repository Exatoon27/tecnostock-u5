"""Pruebas unitarias de dominio (sin BD, sin API). Patrón Arrange-Act-Assert."""
from datetime import date
from decimal import Decimal

import pytest

from src.domain.apartado import Apartado, EstadoApartado
from src.domain.errores import DatosInvalidos, ReglaNegocioViolada, TransicionInvalida
from src.domain.item_serie import EstadoSerie, ItemSerie
from src.domain.valores import (
    SKU,
    MontoMonetario,
    NumeroSerie,
    PorcentajeAnticipo,
    SucursalId,
)
from src.domain.venta import LineaVenta, Pago, Venta

M = MontoMonetario.de
HOY = date(2026, 11, 1)


def apartado(total="1000.00", anticipo="200.00", hoy=HOY):
    return Apartado.crear("AP-1", "C1", NumeroSerie("SN-0001"),
                          SucursalId("SUC-01"), M(total), M(anticipo), hoy)


# ---------- Value Objects ----------
def test_monto_rechaza_negativo_y_float():
    with pytest.raises(DatosInvalidos):
        M("-1")
    with pytest.raises(DatosInvalidos):
        M(1.5)
    with pytest.raises(DatosInvalidos):
        MontoMonetario(Decimal("1"), "MXN").restar(MontoMonetario(Decimal("2")))


def test_monto_redondea_a_centavos():
    assert M("0.105").por(Decimal("1")).cantidad == Decimal("0.11")


@pytest.mark.parametrize("valor", ["AB", "12345", "SN 001", ""])
def test_numero_serie_invalido(valor):
    with pytest.raises(DatosInvalidos):
        NumeroSerie(valor)


def test_numero_serie_imei_15_digitos():
    assert NumeroSerie("356938035643809").valor == "356938035643809"


def test_porcentaje_anticipo_frontera():
    assert PorcentajeAnticipo.de(M("200.00"), M("1000.00")).fraccion == Decimal("0.2")
    with pytest.raises(ReglaNegocioViolada):
        PorcentajeAnticipo.de(M("199.99"), M("1000.00"))


# ---------- Apartado ----------
def test_apartado_exito_emite_evento_y_vigencia_30_dias():
    ap = apartado()
    assert ap.estado == EstadoApartado.ACTIVO
    assert ap.saldo == M("800.00")
    assert ap.fecha_limite == date(2026, 12, 1)
    assert [e.nombre for e in ap.eventos] == ["ApartadoCreadoEvent"]


def test_apartado_rechaza_anticipo_19_99_por_ciento():
    with pytest.raises(ReglaNegocioViolada):
        apartado(anticipo="199.99")


def test_apartado_anticipo_total_nace_liquidado():
    assert apartado(anticipo="1000.00").estado == EstadoApartado.LIQUIDADO


def test_abono_parcial_y_liquidacion():
    ap = apartado()
    ap.registrar_abono(M("300.00"), HOY)
    assert ap.estado == EstadoApartado.ACTIVO and ap.saldo == M("500.00")
    ap.registrar_abono(M("500.00"), HOY)
    assert ap.estado == EstadoApartado.LIQUIDADO
    assert ap.eventos[-1].nombre == "ApartadoLiquidadoEvent"


def test_abono_mayor_al_saldo_rechazado():
    ap = apartado()
    with pytest.raises(DatosInvalidos):
        ap.registrar_abono(M("800.01"), HOY)


def test_abono_cero_rechazado():
    with pytest.raises(DatosInvalidos):
        apartado().registrar_abono(M("0.00"), HOY)


def test_no_abono_a_liquidado():
    ap = apartado(anticipo="1000.00")
    with pytest.raises(TransicionInvalida):
        ap.registrar_abono(M("1.00"), HOY)


def test_vencimiento_limite_dia_30_vigente_dia_31_vence():
    ap = apartado()
    assert ap.evaluar_vencimiento(date(2026, 12, 1)) is False   # día 30
    assert ap.evaluar_vencimiento(date(2026, 12, 2)) is True    # día 31
    assert ap.estado == EstadoApartado.VENCIDO


def test_penalizacion_10_por_ciento_calculada_en_el_dominio():
    ap = apartado(anticipo="250.50")
    ap.evaluar_vencimiento(date(2027, 1, 1))
    assert ap.saldo_a_favor == M("225.45")       # 250.50 - 25.05


def test_vencimiento_es_idempotente():
    ap = apartado()
    assert ap.evaluar_vencimiento(date(2027, 1, 1))
    assert not ap.evaluar_vencimiento(date(2027, 1, 2))
    assert [e.nombre for e in ap.eventos].count("ApartadoVencidoEvent") == 1


def test_abono_fuera_de_plazo_aunque_proceso_nocturno_no_corrio():
    with pytest.raises(TransicionInvalida):
        apartado().registrar_abono(M("10.00"), date(2026, 12, 2))


def test_entregar_requiere_liquidado():
    ap = apartado()
    with pytest.raises(TransicionInvalida):
        ap.entregar()
    ap.registrar_abono(M("800.00"), HOY)
    ap.entregar()
    assert ap.estado == EstadoApartado.ENTREGADO


# ---------- ItemSerie (máquina de estados) ----------
def serie(estado=EstadoSerie.DISPONIBLE):
    return ItemSerie(NumeroSerie("SN-0001"), SKU("P1"), SucursalId("SUC-01"), estado)


def test_item_flujo_valido():
    it = serie()
    it.bloquear_para_reserva()
    assert it.estado == EstadoSerie.RESERVADO
    it.liberar()
    it.marcar_como_vendido()
    it.reingresar()
    assert it.estado == EstadoSerie.DISPONIBLE
    assert [e.nombre for e in it.eventos] == [
        "SerieBloqueadaEvent", "SerieLiberadaEvent", "SerieVendidaEvent",
        "SerieLiberadaEvent"]


def test_item_reservado_no_se_vende_directo_ni_se_reserva_dos_veces():
    it = serie(EstadoSerie.RESERVADO)
    with pytest.raises(TransicionInvalida):
        it.marcar_como_vendido()
    with pytest.raises(TransicionInvalida):
        it.bloquear_para_reserva()


def test_item_reservado_si_se_vende_desde_su_apartado():
    it = serie(EstadoSerie.RESERVADO)
    it.marcar_como_vendido(desde_apartado=True)
    assert it.estado == EstadoSerie.VENDIDO


@pytest.mark.parametrize("estado, accion", [
    (EstadoSerie.DISPONIBLE, "liberar"), (EstadoSerie.DISPONIBLE, "reingresar"),
    (EstadoSerie.VENDIDO, "liberar"), (EstadoSerie.EN_TRANSITO, "marcar_como_vendido"),
])
def test_item_transiciones_invalidas(estado, accion):
    with pytest.raises(TransicionInvalida):
        getattr(serie(estado), accion)()


# ---------- Venta ----------
def linea(serie_=None, precio="100.00", requiere=True):
    return LineaVenta(SKU("P1"), M(precio), requiere,
                      NumeroSerie(serie_) if serie_ else None)


def test_venta_exito_pagos_combinados():
    v = Venta.cerrar("V-1", HOY, "SUC-01", [linea("SN-0001", "10000.00")],
                     [Pago("EFECTIVO", M("4000.00")), Pago("TARJETA", M("6000.00"))])
    assert v.total == M("10000.00")
    assert v.eventos[0].nombre == "VentaCompletadaEvent"


def test_venta_pagos_no_cuadran():
    with pytest.raises(ReglaNegocioViolada):
        Venta.cerrar("V-1", HOY, "SUC-01", [linea("SN-0001")],
                     [Pago("EFECTIVO", M("99.99"))])


def test_venta_falta_serie_obligatoria():
    with pytest.raises(ReglaNegocioViolada):
        Venta.cerrar("V-1", HOY, "SUC-01", [linea(None)],
                     [Pago("EFECTIVO", M("100.00"))])


def test_venta_sin_lineas():
    with pytest.raises(DatosInvalidos):
        Venta.cerrar("V-1", HOY, "SUC-01", [], [])


def test_venta_producto_sin_serie_no_exige_serie():
    v = Venta.cerrar("V-1", HOY, "SUC-01", [linea(None, requiere=False)],
                     [Pago("EFECTIVO", M("100.00"))])
    assert v.total == M("100.00")


def test_venta_no_se_devuelve_dos_veces_la_misma_serie():
    v = Venta.cerrar("V-1", HOY, "SUC-01", [linea("SN-0001")],
                     [Pago("EFECTIVO", M("100.00"))])
    v.registrar_devolucion(NumeroSerie("SN-0001"))
    with pytest.raises(TransicionInvalida):
        v.registrar_devolucion(NumeroSerie("SN-0001"))


def test_venta_serie_ajena_al_ticket():
    v = Venta.cerrar("V-1", HOY, "SUC-01", [linea("SN-0001")],
                     [Pago("EFECTIVO", M("100.00"))])
    with pytest.raises(DatosInvalidos):
        v.registrar_devolucion(NumeroSerie("SN-9999"))


# ---------- TDD (U5, ciclo 1): US-03 "indicando el monto mínimo faltante" ----------
def test_anticipo_insuficiente_indica_minimo_y_faltante():
    with pytest.raises(ReglaNegocioViolada) as e:
        apartado(total="1000.00", anticipo="150.00")
    assert "mínimo 200.00" in str(e.value) and "faltan 50.00" in str(e.value)


# ---------- TDD (U5, ciclo 2): US-02 una serie no puede repetirse en un ticket ----------
def test_venta_rechaza_la_misma_serie_dos_veces():
    with pytest.raises(ReglaNegocioViolada, match="serie repetida"):
        Venta.cerrar("V-1", HOY, "SUC-01",
                     [linea("SN-0001"), linea("SN-0001")],
                     [Pago("EFECTIVO", M("200.00"))])


def test_minimo_de_anticipo_se_redondea_hacia_arriba_al_centavo():
    # 20% de 100.02 = 20.004 -> el mínimo exigible es 20.01, no 20.00
    assert PorcentajeAnticipo.minimo(M("100.02")) == M("20.01")
    with pytest.raises(ReglaNegocioViolada, match="faltan 0.01"):
        PorcentajeAnticipo.de(M("20.00"), M("100.02"))
    assert PorcentajeAnticipo.de(M("20.01"), M("100.02"))


# ---------- ramas de validación (cobertura U5) ----------
def test_anticipo_mayor_al_total_se_rechaza_con_mensaje_claro():
    with pytest.raises(ReglaNegocioViolada, match="excede el total"):
        apartado(total="1000.00", anticipo="1000.01")


def test_value_objects_rechazan_valores_vacios_o_ilegibles():
    with pytest.raises(DatosInvalidos):
        SKU("  ")
    with pytest.raises(DatosInvalidos):
        SucursalId("")
    with pytest.raises(DatosInvalidos):
        M("abc")
    with pytest.raises(DatosInvalidos):
        MontoMonetario(10)                       # int, no Decimal
    with pytest.raises(DatosInvalidos):
        MontoMonetario(Decimal("1")).sumar(MontoMonetario(Decimal("1"), "USD"))


def test_cliente_exige_nombre_telefono_y_correo():
    from src.domain.entidades import Cliente
    with pytest.raises(DatosInvalidos):
        Cliente("C1", "Ana", "", "ana@ejemplo.mx")
    assert Cliente("C1", "Ana", "8100000000", "ana@ejemplo.mx").activo
