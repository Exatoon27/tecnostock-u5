"""Interfaces (puertos) de persistencia en términos del dominio (ADR-03, ISP)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from src.domain.apartado import Apartado
from src.domain.entidades import Cliente, Producto
from src.domain.item_serie import ItemSerie
from src.domain.valores import SKU, NumeroSerie
from src.domain.venta import Venta


class IItemSerieRepository(ABC):
    @abstractmethod
    def find_by_serie(self, sn: NumeroSerie) -> ItemSerie | None: ...
    @abstractmethod
    def listar(self) -> list[ItemSerie]: ...
    @abstractmethod
    def save(self, item: ItemSerie) -> None: ...


class IApartadoRepository(ABC):
    @abstractmethod
    def find_by_id(self, folio: str) -> Apartado | None: ...
    @abstractmethod
    def get_vencidos(self, fecha_corte: date) -> list[Apartado]: ...
    @abstractmethod
    def contar_activos(self, cliente_id: str) -> int: ...
    @abstractmethod
    def siguiente_folio(self) -> str: ...
    @abstractmethod
    def save(self, apartado: Apartado) -> None: ...


class IVentaRepository(ABC):
    @abstractmethod
    def find_by_id(self, ticket_id: str) -> Venta | None: ...
    @abstractmethod
    def siguiente_ticket(self) -> str: ...
    @abstractmethod
    def save(self, venta: Venta) -> None: ...


class IClienteRepository(ABC):
    @abstractmethod
    def find_by_id(self, cliente_id: str) -> Cliente | None: ...


class IProductoRepository(ABC):
    @abstractmethod
    def find_by_sku(self, sku: SKU) -> Producto | None: ...


class IUnitOfWork(ABC):
    """Límite transaccional: salir sin commit() equivale a rollback()."""
    items: IItemSerieRepository
    apartados: IApartadoRepository
    ventas: IVentaRepository
    clientes: IClienteRepository
    productos: IProductoRepository

    @abstractmethod
    def __enter__(self) -> IUnitOfWork: ...
    @abstractmethod
    def __exit__(self, *exc) -> None: ...
    @abstractmethod
    def commit(self) -> None: ...
    @abstractmethod
    def rollback(self) -> None: ...
