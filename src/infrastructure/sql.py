"""Persistencia SQLAlchemy 2: implementa las MISMAS interfaces del dominio.

- Una sesión por Unit of Work; salir sin commit() equivale a rollback().
- Los eventos de dominio se publican sólo DESPUÉS del commit exitoso.
  (Limitación: si el proceso cae entre commit y publicación se pierden;
  la solución es un outbox transaccional — pendiente para el PIA.)
- Dinero se guarda como texto decimal exacto: sin float en SQLite ni Postgres.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from src.domain.apartado import VIGENCIA_DIAS, Abono, Apartado, EstadoApartado
from src.domain.devolucion import ISupervisorAuthDomainService
from src.domain.entidades import Cliente, Producto
from src.domain.eventos import RaizAgregada
from src.domain.item_serie import EstadoSerie, ItemSerie
from src.domain.repositorios import (
    IApartadoRepository,
    IClienteRepository,
    IItemSerieRepository,
    IProductoRepository,
    IUnitOfWork,
    IVentaRepository,
)
from src.domain.valores import SKU, MontoMonetario, NumeroSerie, SucursalId
from src.domain.venta import LineaVenta, Pago, Venta
from src.infrastructure.memoria import BusEventos


class Dinero(TypeDecorator):
    impl = String(24)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(value)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class Base(DeclarativeBase):
    pass


class ClienteRow(Base):
    __tablename__ = "clientes"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    telefono: Mapped[str] = mapped_column(String(20))
    correo: Mapped[str] = mapped_column(String(80))
    activo: Mapped[bool] = mapped_column(Boolean)


class ProductoRow(Base):
    __tablename__ = "productos"
    sku: Mapped[str] = mapped_column(String(20), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(80))
    precio = mapped_column(Dinero)
    requiere_serie: Mapped[bool] = mapped_column(Boolean)
    habilitado: Mapped[bool] = mapped_column(Boolean)


class SupervisorRow(Base):
    __tablename__ = "supervisores"
    clave: Mapped[str] = mapped_column(String(20), primary_key=True)
    activo: Mapped[bool] = mapped_column(Boolean)


class ItemSerieRow(Base):
    """La PK garantiza que un número de serie es único en toda la red."""
    __tablename__ = "items_serie"
    numero_serie: Mapped[str] = mapped_column(String(30), primary_key=True)
    sku: Mapped[str] = mapped_column(String(20))
    sucursal_id: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(20))


class AbonoRow(Base):
    __tablename__ = "abonos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folio: Mapped[str] = mapped_column(ForeignKey("apartados.folio"))
    monto = mapped_column(Dinero)
    fecha: Mapped[date] = mapped_column(Date)


class ApartadoRow(Base):
    __tablename__ = "apartados"
    folio: Mapped[str] = mapped_column(String(20), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(20))
    numero_serie: Mapped[str] = mapped_column(ForeignKey("items_serie.numero_serie"))
    sucursal_id: Mapped[str] = mapped_column(String(20))
    total = mapped_column(Dinero)
    fecha_creacion: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20))
    saldo_a_favor = mapped_column(Dinero, nullable=True)
    abonos: Mapped[list[AbonoRow]] = relationship(
        cascade="all, delete-orphan", order_by=AbonoRow.id, lazy="selectin")
    # Una serie no puede tener dos apartados vigentes a la vez (garantía en BD).
    __table_args__ = (Index(
        "uq_apartado_vigente_por_serie", "numero_serie", unique=True,
        sqlite_where=text("estado IN ('ACTIVO','LIQUIDADO')"),
        postgresql_where=text("estado IN ('ACTIVO','LIQUIDADO')")),)


class LineaVentaRow(Base):
    __tablename__ = "lineas_venta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ventas.ticket_id"))
    sku: Mapped[str] = mapped_column(String(20))
    precio = mapped_column(Dinero)
    requiere_serie: Mapped[bool] = mapped_column(Boolean)
    numero_serie: Mapped[str | None] = mapped_column(String(30), nullable=True)
    devuelta: Mapped[bool] = mapped_column(Boolean, default=False)


class PagoRow(Base):
    __tablename__ = "pagos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ventas.ticket_id"))
    metodo: Mapped[str] = mapped_column(String(20))
    monto = mapped_column(Dinero)


class VentaRow(Base):
    __tablename__ = "ventas"
    ticket_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    fecha: Mapped[date] = mapped_column(Date)
    sucursal_id: Mapped[str] = mapped_column(String(20))
    lineas: Mapped[list[LineaVentaRow]] = relationship(
        cascade="all, delete-orphan", order_by=LineaVentaRow.id, lazy="selectin")
    pagos: Mapped[list[PagoRow]] = relationship(
        cascade="all, delete-orphan", order_by=PagoRow.id, lazy="selectin")


# ---------- fila <-> agregado ----------
def _item_de(r: ItemSerieRow) -> ItemSerie:
    return ItemSerie(NumeroSerie(r.numero_serie), SKU(r.sku),
                     SucursalId(r.sucursal_id), EstadoSerie(r.estado))


def _apartado_de(r: ApartadoRow) -> Apartado:
    ap = Apartado(r.folio, r.cliente_id, NumeroSerie(r.numero_serie),
                  SucursalId(r.sucursal_id), MontoMonetario(r.total),
                  r.fecha_creacion)
    ap.abonos = [Abono(MontoMonetario(a.monto), a.fecha) for a in r.abonos]
    ap.estado = EstadoApartado(r.estado)
    if r.saldo_a_favor is not None:
        ap.saldo_a_favor = MontoMonetario(r.saldo_a_favor)
    return ap


def _venta_de(r: VentaRow) -> Venta:
    lineas = [LineaVenta(SKU(x.sku), MontoMonetario(x.precio), x.requiere_serie,
                         NumeroSerie(x.numero_serie) if x.numero_serie else None)
              for x in r.lineas]
    pagos = [Pago(p.metodo, MontoMonetario(p.monto)) for p in r.pagos]
    v = Venta(r.ticket_id, r.fecha, r.sucursal_id, lineas, pagos)
    v.series_devueltas = {x.numero_serie for x in r.lineas if x.devuelta}
    return v


class _Repos:
    def __init__(self, session: Session, vistos: list[RaizAgregada]) -> None:
        self.s, self.vistos = session, vistos

    def _ver(self, agregado):
        if agregado is not None:
            self.vistos.append(agregado)
        return agregado


class _ItemsSql(_Repos, IItemSerieRepository):
    def find_by_serie(self, sn):
        r = self.s.get(ItemSerieRow, sn.valor)
        return self._ver(_item_de(r)) if r else None

    def listar(self):
        return [self._ver(_item_de(r)) for r in
                self.s.scalars(select(ItemSerieRow).order_by(
                    ItemSerieRow.numero_serie))]

    def save(self, item):
        r = self.s.get(ItemSerieRow, item.numero_serie.valor) or ItemSerieRow(
            numero_serie=item.numero_serie.valor)
        r.sku, r.sucursal_id = item.sku.valor, item.sucursal.valor
        r.estado = item.estado.value
        self.s.add(r)
        self._ver(item)


class _ApartadosSql(_Repos, IApartadoRepository):
    def find_by_id(self, folio):
        r = self.s.get(ApartadoRow, folio)
        return self._ver(_apartado_de(r)) if r else None

    def get_vencidos(self, fecha_corte):
        limite = fecha_corte - timedelta(days=VIGENCIA_DIAS)   # creado < corte-30
        q = select(ApartadoRow).where(
            ApartadoRow.estado == EstadoApartado.ACTIVO.value,
            ApartadoRow.fecha_creacion < limite)
        return [self._ver(_apartado_de(r)) for r in self.s.scalars(q)]

    def contar_activos(self, cliente_id):
        return self.s.scalar(select(func.count()).select_from(ApartadoRow).where(
            ApartadoRow.cliente_id == cliente_id,
            ApartadoRow.estado == EstadoApartado.ACTIVO.value)) or 0

    def siguiente_folio(self):
        n = self.s.scalar(select(func.count()).select_from(ApartadoRow)) or 0
        return f"AP-{n + 1:04d}"

    def save(self, ap):
        r = self.s.get(ApartadoRow, ap.folio) or ApartadoRow(folio=ap.folio)
        r.cliente_id, r.numero_serie = ap.cliente_id, ap.numero_serie.valor
        r.sucursal_id, r.total = ap.sucursal.valor, ap.total.cantidad
        r.fecha_creacion, r.estado = ap.fecha_creacion, ap.estado.value
        r.saldo_a_favor = ap.saldo_a_favor.cantidad if ap.saldo_a_favor else None
        r.abonos = [AbonoRow(monto=a.monto.cantidad, fecha=a.fecha)
                    for a in ap.abonos]
        self.s.add(r)
        self._ver(ap)


class _VentasSql(_Repos, IVentaRepository):
    def find_by_id(self, ticket_id):
        r = self.s.get(VentaRow, ticket_id)
        return self._ver(_venta_de(r)) if r else None

    def siguiente_ticket(self):
        n = self.s.scalar(select(func.count()).select_from(VentaRow)) or 0
        return f"V-{n + 1:04d}"

    def save(self, v):
        r = self.s.get(VentaRow, v.ticket_id) or VentaRow(ticket_id=v.ticket_id)
        r.fecha, r.sucursal_id = v.fecha, v.sucursal_id
        r.lineas = [LineaVentaRow(
            sku=x.sku.valor, precio=x.precio.cantidad,
            requiere_serie=x.requiere_serie,
            numero_serie=x.numero_serie.valor if x.numero_serie else None,
            devuelta=bool(x.numero_serie
                          and x.numero_serie.valor in v.series_devueltas))
            for x in v.lineas]
        r.pagos = [PagoRow(metodo=p.metodo, monto=p.monto.cantidad)
                   for p in v.pagos]
        self.s.add(r)
        self._ver(v)


class _ClientesSql(_Repos, IClienteRepository):
    def find_by_id(self, cliente_id):
        r = self.s.get(ClienteRow, cliente_id)
        return Cliente(r.id, r.nombre, r.telefono, r.correo, r.activo) if r else None


class _ProductosSql(_Repos, IProductoRepository):
    def find_by_sku(self, sku):
        r = self.s.get(ProductoRow, sku.valor)
        return Producto(SKU(r.sku), r.descripcion, MontoMonetario(r.precio),
                        r.requiere_serie, r.habilitado) if r else None


class SupervisorAuthSql(ISupervisorAuthDomainService):
    def __init__(self, fabrica_sesion: sessionmaker) -> None:
        self.fabrica = fabrica_sesion

    def validar(self, clave: str) -> bool:
        with self.fabrica() as s:
            r = s.get(SupervisorRow, clave)
            return bool(r and r.activo)


class UnidadDeTrabajoSql(IUnitOfWork):
    """Una instancia por operación (la crea la fábrica de los servicios)."""

    def __init__(self, fabrica_sesion: sessionmaker, bus: BusEventos) -> None:
        self.fabrica, self.bus = fabrica_sesion, bus
        self.session: Session | None = None

    def __enter__(self):
        self.session = self.fabrica()
        self._vistos: list[RaizAgregada] = []
        args = (self.session, self._vistos)
        self.items, self.apartados = _ItemsSql(*args), _ApartadosSql(*args)
        self.ventas, self.clientes = _VentasSql(*args), _ClientesSql(*args)
        self.productos = _ProductosSql(*args)
        return self

    def __exit__(self, *exc) -> None:
        if self.session is not None:
            self.session.rollback()          # no-op si ya hubo commit
            self.session.close()
            self.session = None

    def commit(self) -> None:
        # Se extraen los eventos de cada agregado una vez; se publican tras el commit.
        unicos = {id(a): a for a in self._vistos}.values()
        eventos = [e for a in unicos for e in a.extraer_eventos()]
        self.session.commit()
        for e in eventos:
            self.bus.publicar(e)

    def rollback(self) -> None:
        self.session.rollback()


# ---------- fábricas y datos ----------
def crear_engine(url: str = "sqlite+pysqlite:///:memory:") -> Engine:
    if url.startswith("sqlite") and ":memory:" in url:
        engine = create_engine(url, poolclass=StaticPool,
                               connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine


def sembrar(fabrica: sessionmaker, almacen) -> None:
    """Copia los datos cargados desde CSV (memoria) a la base de datos."""
    with fabrica() as s:
        for c in almacen.clientes.values():
            s.add(ClienteRow(id=c.id, nombre=c.nombre, telefono=c.telefono,
                             correo=c.correo, activo=c.activo))
        for p in almacen.productos.values():
            s.add(ProductoRow(sku=p.sku.valor, descripcion=p.descripcion,
                              precio=p.precio.cantidad,
                              requiere_serie=p.requiere_serie,
                              habilitado=p.habilitado))
        for clave, activo in almacen.supervisores.items():
            s.add(SupervisorRow(clave=clave, activo=activo))
        s.commit()
    bus = BusEventos()
    with UnidadDeTrabajoSql(fabrica, bus) as uow:
        for it in almacen.items.values():
            uow.items.save(it)
        uow.session.flush()          # items antes que apartados (FK)
        for ap in almacen.apartados.values():
            uow.apartados.save(ap)
        for v in almacen.ventas.values():
            uow.ventas.save(v)
        uow.commit()
