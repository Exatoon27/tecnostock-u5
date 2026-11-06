# TecnoStock U4 — Núcleo de negocio (CLN · FIME UANL · Equipo 5)

Implementación en código de la arquitectura U3 del equipo (Domain Model + CQRS básico
+ Repository/Unit of Work) con las pruebas, persistencia SQL y CI de la Unidad 5. Cubre los casos de uso **CU-01 venta con serie, CU-02 apartado,
CU-03 vencimiento y CU-05 devolución especial**. CU-04 (transferencias) queda para el PIA.

> Sustituye al `techstore-u4` entregado por error (ese era el ejemplo del profesor).

## Instalación y ejecución
```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python cargar_csv.py                  # carga datos/ y resume
python ejecutar_escenarios.py         # E01-E15 -> bitacora.md
python -m pytest --cov=src --cov-fail-under=80
python -m ruff check src tests
python tools/generar_matriz.py        # matriz de casos con resultado real
python tools/ci_local.py              # mismos pasos que .github/workflows/ci.yml
uvicorn src.api.main:app --reload     # http://127.0.0.1:8000/docs
```
Persistencia: sin configurar usa **memoria**; con `DATABASE_URL=sqlite+pysqlite:///./tecnostock.db`
(ver `.env.example`) usa **SQLAlchemy**. Las peticiones llevan `X-Rol: CAJERO|VENDEDOR|SUPERVISOR|ALMACEN|...`.

## Estructura
```
src/domain/          Aggregates (Apartado, ItemSerie, Venta), Value Objects, Specifications,
                     Domain Events, PoliticaDevolucionDomainService, interfaces de repositorio
src/application/     Application Services, Commands/Queries/DTOs (CQRS), manejadores de eventos
src/infrastructure/  Repositorios + Unit of Work (memoria y SQLAlchemy), bus de eventos, pasarela
                     simulada, carga de CSV, raíz de composición (contenedor.py)
src/api/             FastAPI (controladores delgados; excepciones de dominio -> HTTP)
datos/               CSV (clientes, productos, series, apartados, ventas, supervisores, escenarios)
tests/               unitarias, integración (servicios + UoW + SQLite), mocks, autorización, API
docs/                trazabilidad, matriz de pruebas, evidencias U5 (+ evidencias/)
tools/               generar_matriz.py, ci_local.py, mutar.py
```

## Reglas (fuente: BRD y levantamiento del equipo, 10/09/2026)
| Regla | Dónde vive | Prueba |
|---|---|---|
| Anticipo ≥ 20% (y ≤ total) | `PorcentajeAnticipo`, `AnticipoMinimoSpec`, `Apartado.crear` | E01, E02 |
| Máx. 3 apartados activos por cliente | `LimiteApartadosSpec` | E04 |
| Cliente activo con datos de contacto | `ClienteActivoSpec`, `Cliente` | E03 |
| Serie reservada no se vende ni se reserva de nuevo | `ItemSerie` (estados), `SerieDisponibleSpec` | E05, E13 |
| Vigencia 30 días: día 30 vigente, día 31 vence | `Apartado.evaluar_vencimiento` | E09, E10 |
| Penalización 10% → saldo a favor 90% (calculada en el dominio) | `Apartado` | E10 |
| No abonos a vencido/liquidado; abonos ≤ saldo | `Apartado.registrar_abono` | E07, E08, E11 |
| Entrega sólo de apartado liquidado; serie → VENDIDO | `Apartado.entregar` | E12 |
| Venta: serie obligatoria y pagos == total | `Venta.cerrar` | tests/test_dominio.py |
| Devolución ≤ 15 días, empaque y accesorios, sin daño del cliente | `DEVOLUCION_ELEGIBLE` | E14, E15 |
| Devolución exige clave de Supervisor válida | `PoliticaDevolucionDomainService` | tests |

Estados de `ItemSerie`: DISPONIBLE → RESERVADO → (liberada | VENDIDO); VENDIDO → DISPONIBLE (devolución).
Estados de `Apartado`: ACTIVO → LIQUIDADO → ENTREGADO; ACTIVO → VENCIDO.
`EN_TRANSITO` y `EN_GARANTIA` existen en el enum pero sus transiciones se implementan en el PIA.

## API (OpenAPI en `/docs`)
| Método y ruta | Caso de uso | Códigos |
|---|---|---|
| `POST /apartados` | CU-02 | 201, 404, 422 |
| `GET /apartados/{folio}` | consulta | 200, 404 |
| `POST /apartados/{folio}/abonos` | abono | 200, 404, 409, 422 |
| `POST /apartados/{folio}/entrega` | entrega | 200, 404, 409 |
| `POST /procesos/vencimientos` | CU-03 (proceso nocturno) | 200 |
| `POST /ventas` | CU-01 | 201, 404, 409, 422 |
| `POST /devoluciones` | CU-05 | 201, 403, 404, 409, 422 |
| `GET /stock?sku=&sucursal_id=` | Query CQRS (US-01) | 200 |

Códigos transversales: 401 sin/desconocido `X-Rol`, 403 rol sin permiso, 402 pago rechazado por la pasarela,
503 pasarela sin respuesta.

Las fechas se reciben en el cuerpo (`fecha`) para pruebas deterministas; por omisión usan hoy.
Las claves de Supervisor de demostración están en `datos/supervisores.csv` (ficticias).

## Calidad (U5)
241 pruebas · cobertura 99 % (umbral 80 %) · 47 casos en `docs/matriz_pruebas.csv` · E01–E15 idénticos en
memoria y SQLite · 14/14 mutaciones detectadas · pasarela de pagos simulada con Mock. Detalle y evidencias:
`docs/evidencias_U5.md`.

## Límites conocidos
- La autenticación es un encabezado `X-Rol` (no hay login real); la autorización por rol y la clave del
  Supervisor sí se aplican. Peticiones sin rol -> 401; sin permiso -> 403.
- Eventos publicados tras el commit sin outbox: si el proceso cae justo después se pierden.
- SQLite en memoria no prueba concurrencia ni PostgreSQL (pendiente PIA con Docker Compose).
- Fuera de alcance de U4: transferencias (CU-04), alertas programadas 5/2 días, contingencia
  offline, facturación, reportes, cancelación por Supervisor, ajustes de inventario.

Ver `docs/trazabilidad_y_diferencias.md`.
