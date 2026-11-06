"""Integración con SQLAlchemy (SQLite en memoria): commit, rollback, unicidad.

Cada test crea su propia base: no se toca ningún dato 'de producción'.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.application.dto import (
    ConsultarStockGlobalQuery,
    CrearApartadoCommand,
    ProcesarDevolucionCommand,
    RegistrarAbonoCommand,
)
from src.domain.apartado import Apartado, EstadoApartado
from src.domain.errores import ReglaNegocioViolada, TransicionInvalida
from src.domain.item_serie import EstadoSerie
from src.domain.valores import SKU, MontoMonetario, NumeroSerie, SucursalId
from src.infrastructure.contenedor import construir_sql
from src.infrastructure.sql import ApartadoRow, ItemSerieRow, UnidadDeTrabajoSql

HOY = date(2026, 11, 5)
M = MontoMonetario.de


@pytest.fixture
def sc():
    return construir_sql()


def estado_serie(sc, serie):
    with sc.uow_factory() as uow:
        return uow.items.find_by_serie(NumeroSerie(serie)).estado


def apartar(sc, serie="SN-LAP-0001", anticipo="67.20", cliente="TEC-C001"):
    return sc.apartados.crear_apartado(
        CrearApartadoCommand(cliente, serie, Decimal(anticipo)), HOY)


def apartado_nuevo(folio, cliente, serie, total, estado="ACTIVO"):
    return ApartadoRow(folio=folio, cliente_id=cliente, numero_serie=serie,
                       sucursal_id="SUC-01", total=Decimal(total),
                       fecha_creacion=HOY, estado=estado)


# ---------- siembra y lectura ----------
def test_los_csv_se_siembran_en_la_base(sc):
    with sc.uow_factory() as uow:
        assert uow.apartados.find_by_id("AP-0005").estado == EstadoApartado.ACTIVO
        assert uow.ventas.find_by_id("V-0001").total == M("1188.00")
        assert len(uow.items.listar()) == 14
        assert uow.clientes.find_by_id("TEC-C007").activo is False
        assert not uow.productos.find_by_sku(SKU("TEC-P011")).habilitado


def test_sembrar_no_duplica_si_la_base_ya_tiene_datos(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'tecnostock.db'}"
    construir_sql(url)
    c2 = construir_sql(url)                    # segunda apertura: no resiembra
    with c2.uow_factory() as uow:
        assert len(uow.items.listar()) == 14


def test_los_datos_persisten_entre_unidades_de_trabajo_y_reinicios(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'tecnostock.db'}"
    apartar(construir_sql(url))
    reabierta = construir_sql(url)             # 'reinicio' de la aplicación
    dto = reabierta.apartados.consultar("AP-0006")
    assert dto.estado == "ACTIVO" and dto.pagado == "67.20"
    assert estado_serie(reabierta, "SN-LAP-0001") == EstadoSerie.RESERVADO


# ---------- commit ----------
def test_commit_hace_visible_el_apartado_con_sus_abonos(sc):
    folio = apartar(sc).folio
    sc.apartados.registrar_abono(RegistrarAbonoCommand(folio, Decimal("100.00")), HOY)
    with sc.uow_factory() as uow:              # otra sesión distinta
        ap = uow.apartados.find_by_id(folio)
    assert [str(a.monto) for a in ap.abonos] == ["67.20", "100.00"]
    assert ap.saldo == M("168.80")


def test_commit_publica_eventos_una_sola_vez(sc):
    apartar(sc)
    assert [e.nombre for e in sc.bus.publicados] == [
        "SerieBloqueadaEvent", "ApartadoCreadoEvent"]


# ---------- rollback ----------
def test_salir_sin_commit_descarta_los_cambios(sc):
    with sc.uow_factory() as uow:
        item = uow.items.find_by_serie(NumeroSerie("SN-LAP-0001"))
        item.bloquear_para_reserva()
        uow.items.save(item)
        uow.session.flush()                    # ya está en la transacción...
    assert estado_serie(sc, "SN-LAP-0001") == EstadoSerie.DISPONIBLE   # ...pero no en la BD


def test_rollback_explicito_descarta_y_no_publica(sc):
    with sc.uow_factory() as uow:
        item = uow.items.find_by_serie(NumeroSerie("SN-LAP-0001"))
        item.bloquear_para_reserva()
        uow.items.save(item)
        uow.rollback()
    assert estado_serie(sc, "SN-LAP-0001") == EstadoSerie.DISPONIBLE
    assert sc.bus.publicados == []


def test_rechazo_de_regla_no_deja_rastro_en_la_base(sc):
    with pytest.raises(ReglaNegocioViolada):
        apartar(sc, anticipo="67.19")
    assert estado_serie(sc, "SN-LAP-0001") == EstadoSerie.DISPONIBLE
    with sc.uow_factory() as uow:
        assert uow.apartados.find_by_id("AP-0006") is None
    assert sc.bus.publicados == []


def test_falla_a_mitad_de_operacion_revierte_la_serie_ya_bloqueada(sc):
    """La serie se bloquea y se guarda ANTES de que Apartado.crear falle."""
    with sc.sesiones() as s:
        s.execute(text("UPDATE productos SET precio = '0.00' WHERE sku = 'TEC-P001'"))
        s.commit()
    with pytest.raises(Exception):
        apartar(sc, anticipo="0.00")
    assert estado_serie(sc, "SN-LAP-0001") == EstadoSerie.DISPONIBLE


def test_entrega_invalida_hace_rollback_del_estado_de_la_serie(sc):
    with pytest.raises(TransicionInvalida):
        sc.apartados.entregar_apartado("AP-0004")          # no está LIQUIDADO
    assert estado_serie(sc, "SN-LAP-0008") == EstadoSerie.RESERVADO


def test_devolucion_rechazada_no_marca_la_serie_como_devuelta(sc):
    malo = ProcesarDevolucionCommand("V-0001", "SN-LAP-0011", "SUP-001", "x",
                                     dano_cliente=True)
    with pytest.raises(ReglaNegocioViolada):
        sc.devoluciones.procesar_devolucion_especial(malo, HOY)
    assert estado_serie(sc, "SN-LAP-0011") == EstadoSerie.VENDIDO
    ok = sc.devoluciones.procesar_devolucion_especial(
        ProcesarDevolucionCommand("V-0001", "SN-LAP-0011", "SUP-001", "x"), HOY)
    assert ok.monto == "1188.00"
    assert estado_serie(sc, "SN-LAP-0011") == EstadoSerie.DISPONIBLE


# ---------- restricciones de unicidad ----------
def test_pk_impide_dos_items_con_el_mismo_numero_de_serie(sc):
    with sc.sesiones() as s:
        s.add(ItemSerieRow(numero_serie="SN-LAP-0001", sku="X", sucursal_id="S",
                           estado="DISPONIBLE"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_la_base_impide_dos_apartados_vigentes_de_la_misma_serie(sc):
    assert apartar(sc).folio == "AP-0006"
    with sc.sesiones() as s:
        s.add(apartado_nuevo("AP-9999", "TEC-C002", "SN-LAP-0001", "336.00"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_serie_vencida_si_admite_un_apartado_nuevo(sc):
    """El índice parcial sólo cubre apartados ACTIVO/LIQUIDADO."""
    sc.apartados.procesar_vencimientos(date(2026, 11, 6))      # vence AP-0005
    with sc.sesiones() as s:
        s.add(apartado_nuevo("AP-9999", "TEC-C002", "SN-LAP-0009", "904.00"))
        s.commit()


# ---------- dinero exacto ----------
def test_el_dinero_se_guarda_como_texto_decimal_sin_float(sc):
    apartar(sc, anticipo="67.20")
    with sc.sesiones() as s:
        fila = s.execute(text(
            "SELECT typeof(total), total FROM apartados WHERE folio = 'AP-0006'")).one()
    assert tuple(fila) == ("text", "336.00")


def test_roundtrip_de_centavos_no_pierde_precision(sc):
    with sc.uow_factory() as uow:
        item = uow.items.find_by_serie(NumeroSerie("SN-LAP-0002"))
        item.bloquear_para_reserva()
        uow.items.save(item)
        uow.apartados.save(Apartado.crear(
            "AP-7777", "TEC-C002", item.numero_serie, SucursalId("SUC-01"),
            M("100.03"), M("20.01"), HOY))
        uow.commit()
    with sc.uow_factory() as uow:
        leido = uow.apartados.find_by_id("AP-7777")
    assert leido.total.cantidad == Decimal("100.03")
    assert leido.saldo.cantidad == Decimal("80.02")


# ---------- flujos completos sobre SQL ----------
def test_vencimiento_sobre_sql_libera_serie_y_calcula_saldo_a_favor(sc):
    r = sc.apartados.procesar_vencimientos(date(2026, 11, 6))
    assert r.vencidos == ["AP-0005"] and r.saldo_a_favor_total == "162.72"
    assert estado_serie(sc, "SN-LAP-0009") == EstadoSerie.DISPONIBLE
    assert sc.apartados.consultar("AP-0005").saldo_a_favor == "162.72"
    assert sc.apartados.procesar_vencimientos(date(2026, 11, 7)).vencidos == []


def test_contar_activos_y_limite_de_tres_sobre_sql(sc):
    with sc.uow_factory() as uow:
        assert uow.apartados.contar_activos("TEC-C004") == 3
    with pytest.raises(ReglaNegocioViolada, match="3 apartados"):
        apartar(sc, cliente="TEC-C004", serie="SN-LAP-0004")


def test_consulta_de_stock_sobre_sql(sc):
    filas = sc.stock.handle(ConsultarStockGlobalQuery(sku="TEC-P005"))
    assert [(f.sucursal_id, f.reservados) for f in filas] == [("SUC-01", 2), ("SUC-03", 1)]


def test_uow_sql_es_una_instancia_por_operacion(sc):
    assert sc.uow_factory() is not sc.uow_factory()
    assert isinstance(sc.uow_factory(), UnidadDeTrabajoSql)


def test_si_el_commit_falla_no_se_publican_eventos_ni_se_guarda_nada(sc):
    with pytest.raises(IntegrityError):
        with sc.uow_factory() as uow:
            item = uow.items.find_by_serie(NumeroSerie("SN-LAP-0001"))
            item.bloquear_para_reserva()                     # genera SerieBloqueadaEvent
            uow.items.save(item)
            uow.session.add(ItemSerieRow(numero_serie="SN-LAP-0002", sku="X",
                                         sucursal_id="S", estado="DISPONIBLE"))
            uow.commit()                                     # choca con la PK existente
    assert sc.bus.publicados == []
    assert estado_serie(sc, "SN-LAP-0001") == EstadoSerie.DISPONIBLE


def test_venta_directa_sobre_sql_genera_ticket_consecutivo(sc):
    from src.application.dto import (
        LineaVentaCommand,
        PagoCommand,
        ProcesarVentaDirectaCommand,
    )
    t = sc.ventas.procesar_venta_directa(ProcesarVentaDirectaCommand(
        "SUC-05", [LineaVentaCommand("TEC-P002", "SN-MON-0001")],
        [PagoCommand("EFECTIVO", Decimal("407.00"))]), HOY)
    assert t.ticket_id == "V-0003"
    assert estado_serie(sc, "SN-MON-0001") == EstadoSerie.VENDIDO


def test_configuracion_por_entorno_elige_la_persistencia(monkeypatch):
    from src.infrastructure.contenedor import construir_desde_entorno
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert construir_desde_entorno().almacen is not None          # memoria
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    c = construir_desde_entorno()
    assert c.almacen is None and c.sesiones is not None           # SQL
    assert c.apartados.consultar("AP-0004").estado == "ACTIVO"
