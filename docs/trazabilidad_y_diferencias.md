# Trazabilidad U2 → U3 → U4 y diferencias documentadas

## 1. Trazabilidad
| Necesidad (BRD) | US | Caso de uso (U3) | Componente (código) | Pruebas |
|---|---|---|---|---|
| N-01 stock global | US-01 | CU-01 consulta | `ConsultarStockGlobalQueryHandler`, `GET /stock` | `test_stock_*` |
| N-02 bloqueo por apartado | US-03, US-04 | CU-02 | `ApartadoApplicationService.crear_apartado`, `Apartado`, `ItemSerie.bloquear_para_reserva` | E01–E05 |
| N-02 / US-05 liberación por vencimiento | US-05 | CU-03 | `Apartado.evaluar_vencimiento`, `procesar_vencimientos`, `ApartadoVencidoEventHandler` | E09–E11 |
| N-03 serie obligatoria | US-02, US-11 | CU-01 | `Venta.cerrar`, `NumeroSerie`, `ItemSerie` | E13, `test_venta_*` |
| US-12 pagos combinados | US-12 | CU-01 | `Venta.cerrar` (pagos == total) | `test_venta_pagos_*` |
| N-04 devoluciones con Supervisor | US-09, US-10 | CU-05 | `PoliticaDevolucionDomainService`, `DEVOLUCION_ELEGIBLE` | E14, E15 |
| CON-02 sólo Supervisor autoriza | US-09 | CU-05 | `ISupervisorAuthDomainService` → 403 | `test_devolucion_rechazos_*` |
| ADR-01 Domain Model | — | — | `src/domain/*` sin imports de FastAPI/SQL | — |
| ADR-02 CQRS básico | — | — | `dto.py` (Commands/Queries) + `ConsultarStockGlobalQueryHandler` | `test_stock_*` |
| ADR-03 Repository + UoW | — | — | `repositorios.py`, `memoria.py` (rollback) | `test_*hace_rollback*` |

## 2. Diferencias contra U3 (actualizar diagramas)
1. Se añadieron `Cliente` y `Producto` (+ `IClienteRepository`, `IProductoRepository`): el diagrama
   sólo referenciaba `clienteId` y `sku`, pero la regla "cliente activo / datos obligatorios" y el
   precio necesitan ambos.
2. `IApartadoRepository` ganó `contar_activos(cliente_id)` (regla de máximo 3) y `siguiente_folio()`;
   `IVentaRepository` ganó `siguiente_ticket()`; `IItemSerieRepository` ganó `listar()` (lado de lectura).
3. `Abono` es un value-record dentro de `Apartado` (U3 lo listó como entidad); no tiene identidad propia usada.
4. `PorcentajeAnticipo` valida 20 % ≤ anticipo ≤ total.
5. La regla "no más de 3 apartados" cuenta apartados ACTIVOS (los vencidos/entregados ya no cuentan).
6. Eventos adicionales: `ApartadoEntregadoEvent`. `SerieLiberadaEvent` se emite también al reingresar por devolución.

## 3. Diferencias contra el paquete CSV del PIA (`PIA/05_TecnoStock`)
El LEEME de ese paquete declara que su modelo (Comprador/Operación; BORRADOR→APROBADA→SURTIDA→ENTREGADA;
`puede_procesarse`, `beneficio_referencia` ≥1500 MXN) es una **propuesta**, no un requerimiento original,
y que debe prevalecer el BRD del equipo. Por eso:
- Se reutilizaron **actores→clientes** (12, con `activo`) y **catálogo→productos** (20, mismos IDs y precios).
- No se usó `es_preferente`, el umbral 1500 ni el flujo BORRADOR→…→ENTREGADA: no existen en el BRD.
- `requiere_serie` en `productos.csv` es un **supuesto nuestro** (Laptop y Monitor = 1) para disponer de
  series; validar con el profesor/stakeholder.
- Los 120 casos y 20 transiciones del paquete no se ejecutan; se reemplazan por E01–E15 propios.

## 4. Supuestos (no inventados en el BRD, marcados para validar)
- Día 30 desde la creación sigue vigente; el apartado vence el día 31 (BRD: "al cumplirse el día 31").
- Devolución: día 15 desde la venta procede, día 16 no (BRD: "primeros 15 días").
- Anticipo igual al total crea el apartado ya LIQUIDADO.
- Rechazo por política de devolución no requiere clave de Supervisor; la autorización sí.
- Producto con falla de fábrica vs. reembolso/cambio: no se distingue en U4 (sólo nota de crédito).
