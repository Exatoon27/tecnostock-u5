"""Cliente y Producto (soporte). Se añaden respecto a U3: el diagrama sólo
referenciaba clienteId/sku; hay que actualizar el diagrama de clases."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.errores import DatosInvalidos
from src.domain.valores import SKU, MontoMonetario


@dataclass(frozen=True)
class Cliente:
    id: str
    nombre: str
    telefono: str
    correo: str
    activo: bool = True

    def __post_init__(self) -> None:
        # BRD levantamiento p.15: nombre, celular y correo obligatorios
        if not (self.id and self.nombre.strip() and self.telefono.strip()
                and self.correo.strip()):
            raise DatosInvalidos("Cliente: nombre, teléfono y correo requeridos")


@dataclass(frozen=True)
class Producto:
    sku: SKU
    descripcion: str
    precio: MontoMonetario
    requiere_serie: bool
    habilitado: bool = True
