"""Infraestructura en memoria: repositorios + Unit of Work con rollback real.

U5 añadirá la implementación SQLAlchemy de las mismas interfaces.
"""
from __future__ import annotations

import copy
from datetime import date
from itertools import chain

from src.domain.apartado import Apartado, EstadoApartado
from src.domain.devolucion import ISupervisorAuthDomainService
from src.domain.entidades import Cliente, Producto
from src.domain.eventos import EventoDominio
from src.domain.item_serie import ItemSerie
from src.domain.repositorios import (
    IApartadoRepository,
    IClienteRepository,
    IItemSerieRepository,
    IProductoRepository,
    IUnitOfWork,
    IVentaRepository,
)
from src.domain.valores import SKU, NumeroSerie
from src.domain.venta import Venta


class Almacen:
    """Datos 'persistidos'. Se copia al abrir una transacción."""

    def __init__(self) -> None:
        self.items: dict[str, ItemSerie] = {}
        self.apartados: dict[str, Apartado] = {}
        self.ventas: dict[str, Venta] = {}
        self.clientes: dict[str, Cliente] = {}
        self.productos: dict[str, Producto] = {}
        self.supervisores: dict[str, bool] = {}

    def _estado(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class BusEventos:
    """Bus en proceso (decisión U3: sin RabbitMQ/Kafka)."""

    def __init__(self) -> None:
        self._suscriptores: dict[str, list] = {}
        self.publicados: list[EventoDominio] = []

    def suscribir(self, nombre_evento: str, manejador) -> None:
        self._suscriptores.setdefault(nombre_evento, []).append(manejador)

    def publicar(self, evento: EventoDominio) -> None:
        self.publicados.append(evento)
        for manejador in self._suscriptores.get(evento.nombre, []):
            manejador(evento)


class _ItemsMem(IItemSerieRepository):
    def __init__(self, a: Almacen): self.a = a
    def find_by_serie(self, sn: NumeroSerie): return self.a.items.get(sn.valor)
    def listar(self): return list(self.a.items.values())
    def save(self, item): self.a.items[item.numero_serie.valor] = item


class _ApartadosMem(IApartadoRepository):
    def __init__(self, a: Almacen): self.a = a
    def find_by_id(self, folio): return self.a.apartados.get(folio)
    def save(self, apartado): self.a.apartados[apartado.folio] = apartado

    def get_vencidos(self, fecha_corte: date):
        return [x for x in self.a.apartados.values()
                if x.estado == EstadoApartado.ACTIVO
                and fecha_corte > x.fecha_limite]

    def contar_activos(self, cliente_id: str) -> int:
        return sum(1 for x in self.a.apartados.values()
                   if x.cliente_id == cliente_id
                   and x.estado == EstadoApartado.ACTIVO)

    def siguiente_folio(self) -> str:
        return f"AP-{len(self.a.apartados) + 1:04d}"


class _VentasMem(IVentaRepository):
    def __init__(self, a: Almacen): self.a = a
    def find_by_id(self, ticket_id): return self.a.ventas.get(ticket_id)
    def save(self, venta): self.a.ventas[venta.ticket_id] = venta
    def siguiente_ticket(self): return f"V-{len(self.a.ventas) + 1:04d}"


class _ClientesMem(IClienteRepository):
    def __init__(self, a: Almacen): self.a = a
    def find_by_id(self, cliente_id): return self.a.clientes.get(cliente_id)


class _ProductosMem(IProductoRepository):
    def __init__(self, a: Almacen): self.a = a
    def find_by_sku(self, sku: SKU): return self.a.productos.get(sku.valor)


class SupervisorAuthMemoria(ISupervisorAuthDomainService):
    def __init__(self, a: Almacen): self.a = a
    def validar(self, clave: str) -> bool: return self.a.supervisores.get(clave, False)


class UnidadDeTrabajoMemoria(IUnitOfWork):
    def __init__(self, almacen: Almacen, bus: BusEventos) -> None:
        self.almacen, self.bus = almacen, bus
        self.items = _ItemsMem(almacen)
        self.apartados = _ApartadosMem(almacen)
        self.ventas = _VentasMem(almacen)
        self.clientes = _ClientesMem(almacen)
        self.productos = _ProductosMem(almacen)
        self._foto: dict | None = None

    def __enter__(self):
        self._foto = copy.deepcopy(self.almacen._estado())
        return self

    def __exit__(self, *exc) -> None:
        if self._foto is not None:     # no hubo commit -> rollback
            self.rollback()

    def commit(self) -> None:
        agregados = chain(self.almacen.items.values(),
                          self.almacen.apartados.values(),
                          self.almacen.ventas.values())
        eventos = [e for ag in agregados for e in ag.extraer_eventos()]
        self._foto = None
        for evento in eventos:         # se publica sólo tras confirmar
            self.bus.publicar(evento)

    def rollback(self) -> None:
        if self._foto is not None:
            self.almacen.__dict__.update(self._foto)
            self._foto = None
