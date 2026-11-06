"""Application Services: coordinan casos de uso; las reglas viven en el dominio.

Cada método abre un Unit of Work: sin commit() => rollback.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from src.application.dto import (
    ApartadoDTO,
    ConsultarStockGlobalQuery,
    CrearApartadoCommand,
    NotaCreditoDTO,
    ProcesarDevolucionCommand,
    ProcesarVentaDirectaCommand,
    RegistrarAbonoCommand,
    ResumenProcesoVencimientoDTO,
    StockGlobalDTO,
    TicketConfirmacionDTO,
)
from src.domain.apartado import Apartado
from src.domain.devolucion import PoliticaDevolucionDomainService
from src.domain.errores import (
    DatosInvalidos,
    PagoRechazado,
    RecursoNoEncontrado,
    ReglaNegocioViolada,
    ServicioNoDisponible,
)
from src.domain.especificaciones import (
    REGLAS_APARTAR,
    SolicitudApartado,
    SolicitudDevolucion,
)
from src.domain.item_serie import EstadoSerie, ItemSerie
from src.domain.puertos import IPasarelaPagos
from src.domain.repositorios import IUnitOfWork
from src.domain.valores import SKU, MontoMonetario, NumeroSerie, SucursalId
from src.domain.venta import LineaVenta, Pago, Venta

UowFactory = Callable[[], IUnitOfWork]


def _dto(ap: Apartado) -> ApartadoDTO:
    return ApartadoDTO(
        folio=ap.folio, cliente_id=ap.cliente_id,
        numero_serie=ap.numero_serie.valor, sucursal_id=ap.sucursal.valor,
        estado=ap.estado.value, total=str(ap.total), pagado=str(ap.pagado),
        saldo=str(ap.saldo), fecha_limite=ap.fecha_limite,
        saldo_a_favor=str(ap.saldo_a_favor) if ap.saldo_a_favor else None,
        eventos=[e.nombre for e in ap.eventos])


def _item(uow: IUnitOfWork, serie: str) -> ItemSerie:
    item = uow.items.find_by_serie(NumeroSerie(serie))
    if item is None:
        raise RecursoNoEncontrado(f"No existe la serie {serie}")
    return item


def _apartado(uow: IUnitOfWork, folio: str) -> Apartado:
    ap = uow.apartados.find_by_id(folio)
    if ap is None:
        raise RecursoNoEncontrado(f"No existe el apartado {folio}")
    return ap


class ApartadoApplicationService:
    def __init__(self, uow_factory: UowFactory) -> None:
        self.uow_factory = uow_factory

    def crear_apartado(self, cmd: CrearApartadoCommand, hoy: date) -> ApartadoDTO:
        with self.uow_factory() as uow:
            cliente = uow.clientes.find_by_id(cmd.cliente_id)
            if cliente is None:
                raise RecursoNoEncontrado(f"No existe el cliente {cmd.cliente_id}")
            item = _item(uow, cmd.numero_serie)
            producto = uow.productos.find_by_sku(item.sku)
            if producto is None:
                raise RecursoNoEncontrado(f"No existe el SKU {item.sku.valor}")
            solicitud = SolicitudApartado(
                cliente_activo=cliente.activo, total=producto.precio,
                anticipo=MontoMonetario.de(cmd.anticipo),
                apartados_activos_cliente=uow.apartados.contar_activos(cliente.id),
                estado_serie=item.estado)
            fallas = [m(solicitud) if callable(m) else m
                      for m, regla in REGLAS_APARTAR
                      if not regla.se_cumple(solicitud)]
            if fallas:
                raise ReglaNegocioViolada("No se puede apartar: " + "; ".join(fallas))
            item.bloquear_para_reserva()
            apartado = Apartado.crear(
                uow.apartados.siguiente_folio(), cliente.id, item.numero_serie,
                SucursalId(cmd.sucursal_id) if cmd.sucursal_id else item.sucursal,
                producto.precio, solicitud.anticipo, hoy)
            uow.items.save(item)
            uow.apartados.save(apartado)
            dto = _dto(apartado)
            uow.commit()
            return dto

    def registrar_abono(self, cmd: RegistrarAbonoCommand, hoy: date) -> ApartadoDTO:
        with self.uow_factory() as uow:
            ap = _apartado(uow, cmd.folio)
            ap.registrar_abono(MontoMonetario.de(cmd.monto), hoy)
            uow.apartados.save(ap)
            dto = _dto(ap)
            uow.commit()
            return dto

    def entregar_apartado(self, folio: str) -> ApartadoDTO:
        with self.uow_factory() as uow:
            ap = _apartado(uow, folio)
            ap.entregar()
            item = _item(uow, ap.numero_serie.valor)
            item.marcar_como_vendido(desde_apartado=True)
            uow.apartados.save(ap)
            uow.items.save(item)
            dto = _dto(ap)
            uow.commit()
            return dto

    def consultar(self, folio: str) -> ApartadoDTO:
        with self.uow_factory() as uow:
            return _dto(_apartado(uow, folio))

    def procesar_vencimientos(self, hoy: date) -> ResumenProcesoVencimientoDTO:
        """Proceso nocturno (CU-03): vence, penaliza 10% y libera la serie."""
        with self.uow_factory() as uow:
            vencidos, a_favor = [], Decimal("0.00")
            for ap in uow.apartados.get_vencidos(hoy):
                if ap.evaluar_vencimiento(hoy):
                    item = _item(uow, ap.numero_serie.valor)
                    item.liberar()
                    uow.apartados.save(ap)
                    uow.items.save(item)
                    vencidos.append(ap.folio)
                    a_favor += ap.saldo_a_favor.cantidad
            uow.commit()
            return ResumenProcesoVencimientoDTO(vencidos, f"{a_favor:.2f}")


METODOS_CON_PASARELA = {"TARJETA"}


class VentaApplicationService:
    def __init__(self, uow_factory: UowFactory,
                 pasarela: IPasarelaPagos) -> None:
        self.uow_factory, self.pasarela = uow_factory, pasarela

    def _cobrar_con_tarjeta(self, venta: Venta) -> None:
        """Último paso antes del commit: si la pasarela falla se hace rollback,
        así nunca queda una serie VENDIDA sin pago aprobado."""
        for pago in venta.pagos:
            if pago.metodo not in METODOS_CON_PASARELA:
                continue
            try:
                aprobado = self.pasarela.cobrar(pago.monto, pago.metodo,
                                                venta.ticket_id)
            except TimeoutError as exc:
                raise ServicioNoDisponible(
                    "La pasarela de pagos no respondió; reintente") from exc
            if not aprobado:
                raise PagoRechazado("La pasarela rechazó el pago con tarjeta")

    def procesar_venta_directa(self, cmd: ProcesarVentaDirectaCommand,
                               hoy: date) -> TicketConfirmacionDTO:
        with self.uow_factory() as uow:
            lineas, items = [], []
            for lc in cmd.lineas:
                producto = uow.productos.find_by_sku(SKU(lc.sku))
                if producto is None or not producto.habilitado:
                    raise RecursoNoEncontrado(f"SKU no disponible: {lc.sku}")
                serie = NumeroSerie(lc.numero_serie) if lc.numero_serie else None
                if serie is not None:
                    item = _item(uow, serie.valor)
                    if item.sku != producto.sku:
                        raise DatosInvalidos("La serie no corresponde al SKU")
                    item.marcar_como_vendido()   # RESERVADA -> TransicionInvalida
                    items.append(item)
                lineas.append(LineaVenta(producto.sku, producto.precio,
                                         producto.requiere_serie, serie))
            pagos = [Pago(p.metodo, MontoMonetario.de(p.monto)) for p in cmd.pagos]
            venta = Venta.cerrar(uow.ventas.siguiente_ticket(), hoy,
                                 cmd.sucursal_id, lineas, pagos)
            uow.ventas.save(venta)
            for item in items:
                uow.items.save(item)
            self._cobrar_con_tarjeta(venta)
            dto = TicketConfirmacionDTO(
                venta.ticket_id, str(venta.total),
                [x.numero_serie.valor for x in lineas if x.numero_serie])
            uow.commit()
            return dto


class DevolucionApplicationService:
    def __init__(self, uow_factory: UowFactory,
                 politica: PoliticaDevolucionDomainService) -> None:
        self.uow_factory, self.politica = uow_factory, politica

    def procesar_devolucion_especial(self, cmd: ProcesarDevolucionCommand,
                                     hoy: date) -> NotaCreditoDTO:
        with self.uow_factory() as uow:
            venta = uow.ventas.find_by_id(cmd.ticket_id)
            if venta is None:
                raise RecursoNoEncontrado(f"No existe el ticket {cmd.ticket_id}")
            serie = NumeroSerie(cmd.numero_serie)
            item = _item(uow, serie.valor)
            monto = venta.linea_de(serie).precio
            solicitud = SolicitudDevolucion(
                venta.fecha, hoy, cmd.empaque_original,
                cmd.accesorios_completos, cmd.dano_cliente)
            nota, evento = self.politica.autorizar(
                venta.ticket_id, serie.valor, monto, solicitud,
                cmd.clave_supervisor)
            venta.registrar_devolucion(serie)
            item.reingresar()
            venta.eventos.append(evento)
            uow.ventas.save(venta)
            uow.items.save(item)
            uow.commit()
            return NotaCreditoDTO(nota.ticket_id, nota.numero_serie,
                                  str(nota.monto), nota.autorizada_por)


class ConsultarStockGlobalQueryHandler:
    """Lado de lectura: no devuelve agregados, sólo un modelo plano."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self.uow_factory = uow_factory

    def handle(self, q: ConsultarStockGlobalQuery) -> list[StockGlobalDTO]:
        cuenta: dict[tuple[str, str], dict[EstadoSerie, int]] = defaultdict(
            lambda: defaultdict(int))
        with self.uow_factory() as uow:
            items = uow.items.listar()
        for it in items:
            if q.sku and it.sku.valor != q.sku:
                continue
            if q.sucursal_id and it.sucursal.valor != q.sucursal_id:
                continue
            cuenta[(it.sku.valor, it.sucursal.valor)][it.estado] += 1
        return [StockGlobalDTO(sku, suc, c[EstadoSerie.DISPONIBLE],
                               c[EstadoSerie.RESERVADO], c[EstadoSerie.VENDIDO])
                for (sku, suc), c in sorted(cuenta.items())]
