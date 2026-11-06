# Evidencias U5 — Integración, Pruebas y Calidad (TecnoStock · Equipo 5)

> Todo lo de este documento se generó ejecutando el proyecto el 2026-11-05 (Python 3.15.0; el CI usa 3.11).
> Los archivos de salida cruda están en `docs/evidencias/`. **Las capturas de pantalla las debe tomar el equipo**
> (ver la lista de pendientes al final): este documento las sustituye con la salida de texto, no las reemplaza.

## 0. Resumen ejecutivo
| Indicador | Resultado | Fuente |
|---|---|---|
| Pruebas | **241 passed** | `evidencias/E1_pytest_verbose.txt` |
| Cobertura de líneas (`src/`) | **99.43 %** (umbral 80 %) | `evidencias/E7_cobertura.txt`, `htmlcov/index.html` |
| Lint | `ruff check src tests` sin errores | `evidencias/E7_ruff.txt` |
| Matriz de casos | **47 casos** (15 éxito · 24 error · 8 límite), todos PASSED | `matriz_pruebas.csv` |
| Escenarios E01–E15 | idénticos en memoria y en SQLite | `evidencias/E15_escenarios.txt`, `bitacora.md` |
| Mutaciones | **14 de 14** defectos inyectados fueron detectados | `evidencias/mutaciones.txt` |

Reproducir: `python -m pip install -r requirements.txt` → `python -m pytest --cov=src --cov-fail-under=80` →
`python tools/generar_matriz.py` → `python tools/ci_local.py`.

### Pirámide de pruebas del proyecto
| Nivel | Qué prueba | Archivos | Depende de |
|---|---|---|---|
| Unitarias | Value Objects, Aggregates, Specifications, políticas, matriz de roles | `test_dominio`, `test_especificaciones`, `test_autorizacion` (matriz) | Nada: sin BD ni red |
| Integración | Servicios + Unit of Work + SQLAlchemy/SQLite, mock de pasarela, API con `TestClient` | `test_aplicacion`, `test_persistencia_sql`, `test_pasarela_mock`, `test_api`, `test_escenarios` | SQLite en memoria, Mocks |
| E2E | **No implementadas.** Propuesta (PIA): `docker compose up` (DB + App) y un flujo HTTP real: crear apartado → abonar → entregar → devolver contra la URL desplegada | — | App desplegada |

## E1 — Entorno y ejecución
`entorno.txt` lista versiones. `pytest` localiza funciones `test_*`; el entorno virtual (`.venv`) aísla las
dependencias del curso para que el resultado sea reproducible en cualquier máquina/CI.
Salida resumida: `241 passed, 1 warning` (la advertencia es de `httpx`/Starlette, de terceros, no afecta).

## E2 — Pruebas unitarias nuevas (Arrange-Act-Assert)
Ejemplo (`tests/test_dominio.py`):
```python
def test_penalizacion_10_por_ciento_calculada_en_el_dominio():
    ap = apartado(anticipo="250.50")                  # Arrange
    ap.evaluar_vencimiento(date(2027, 1, 1))          # Act
    assert ap.saldo_a_favor == M("225.45")            # Assert  (250.50 - 25.05)
```
| Entrada | Regla | Esperado | Real |
|---|---|---|---|
| total 1000.00, anticipo 200.00 | anticipo ≥ 20 % | Apartado ACTIVO | ACTIVO ✔ |
| total 1000.00, anticipo 199.99 | anticipo ≥ 20 % | Rechazo | `ReglaNegocioViolada` ✔ |
| apartado de 250.50 vencido | penalización 10 % | saldo a favor 225.45 | 225.45 ✔ |
| día 30 / día 31 | vigencia 30 días | vigente / VENCIDO | vigente / VENCIDO ✔ |

## E3 — TDD real: Red → Green → Refactor
Se escribieron **primero** tres pruebas para reglas del BRD que el código no cumplía:
1. **US-03** «rechazo … indicando el monto mínimo faltante» (dominio y servicio).
2. **US-02** una misma serie no puede repetirse en un ticket.
3. **Borde descubierto durante el refactor:** el 20 % de 100.02 es 20.004; redondear a 20.00 permitía un anticipo
   menor al 20 % y el mensaje decía «faltan 0.00». Se escribió la prueba, falló, y se redondeó **hacia arriba**.

**RED** (`evidencias/E3_RED.txt`, salida real antes de tocar el código):
```
FAILED tests/test_dominio.py::test_anticipo_insuficiente_indica_minimo_y_faltante
FAILED tests/test_dominio.py::test_venta_rechaza_la_misma_serie_dos_veces
FAILED tests/test_aplicacion.py::test_rechazo_de_anticipo_informa_minimo_y_faltante
3 failed, 67 passed
E  assert 'mínimo 200.00' in 'El anticipo debe ser >= 20% y no mayor al total (anticipo 150.00, total 1000.00)'
E  Failed: DID NOT RAISE ReglaNegocioViolada
```
**GREEN** (`E3_GREEN.txt`): `241 passed` tras la implementación mínima:
```python
# src/domain/valores.py
@staticmethod
def minimo(total):      # 20 % redondeado HACIA ARRIBA al centavo
    return MontoMonetario((total.cantidad * ANTICIPO_MINIMO).quantize(CENTAVOS, ROUND_CEILING), total.moneda)
# src/domain/venta.py  (cerrar)
if len(series) != len(set(series)):
    raise ReglaNegocioViolada("La venta contiene una serie repetida")
```
**REFACTOR:** el mensaje de rechazo salió de la regla estática a `PorcentajeAnticipo.motivo_de_rechazo`, y
`REGLAS_APARTAR` acepta mensajes calculados; el comportamiento público no cambió (la suite siguió verde).
**¿Por qué TDD no es «correr pruebas después»?** Porque la prueba roja demuestra que *detecta* el defecto
y fija el contrato antes de implementar; una prueba escrita después de programar puede pasar sin comprobar nada.

## E4 — Persistencia, commit y rollback (SQLAlchemy + SQLite en memoria)
`src/infrastructure/sql.py` implementa las mismas interfaces de repositorio y un `UnidadDeTrabajoSql` (una sesión
por operación). Pruebas en `tests/test_persistencia_sql.py` (23), cada una con su propia BD en memoria:
- `test_commit_hace_visible_el_apartado_con_sus_abonos`: tras `commit` se ve desde **otra** sesión.
- `test_salir_sin_commit_descarta_los_cambios` y `test_falla_a_mitad_de_operacion_revierte_la_serie_ya_bloqueada`: **rollback**.
- `test_si_el_commit_falla_no_se_publican_eventos_ni_se_guarda_nada`: los eventos salen sólo tras un commit exitoso.
- Unicidad: PK de `numero_serie` y **índice parcial único** (una serie no puede tener dos apartados ACTIVO/LIQUIDADO).
- `test_el_dinero_se_guarda_como_texto_decimal_sin_float`: `typeof(total) = 'text'`.

**Commit vs rollback:** `commit` confirma la transacción y vuelve duraderos todos sus cambios a la vez; `rollback`
los descarta todos y deja la BD como estaba. Por eso, si falla cualquier paso de «reservar serie + crear apartado»,
no queda una serie RESERVADA sin apartado. Límite: SQLite en memoria no prueba concurrencia ni tipos de PostgreSQL;
el PIA debe repetir estas pruebas contra PostgreSQL (Docker Compose).

## E5 — Servicio externo sin cobros reales (mock de pasarela)
Puerto `IPasarelaPagos`; las pruebas usan `Mock(spec=IPasarelaPagos)` (`tests/test_pasarela_mock.py`):
| Ruta | Prueba | Verifica |
|---|---|---|
| Aprobado | `test_pago_aprobado_cobra_una_vez_con_ticket_como_referencia` | `cobrar.assert_called_once_with(407.00, "TARJETA", ticket)` |
| Rechazado | `test_pago_rechazado_lanza_error_y_no_vende_la_serie` | `PagoRechazado`; serie sigue DISPONIBLE |
| Timeout | `test_timeout_de_pasarela_es_servicio_no_disponible_y_hace_rollback` | `ServicioNoDisponible` (HTTP 503) |
| Efectivo | `test_efectivo_no_invoca_la_pasarela` | `assert_not_called()` |

El mock no genera cargos: es un objeto en memoria; el adaptador por defecto (`PasarelaSimulada`) tampoco hace red.
**Riesgo de consistencia (el del laboratorio base):** el cobro se hace como **último paso antes del commit**, así un
rechazo o timeout provoca rollback y nunca queda una serie VENDIDA sin pago aprobado. Riesgo residual: tarjeta
aprobada y *después* falla el commit → cobro sin venta. **Propuesta:** idempotency key (ya se envía el ticket como
referencia), reversa/compensación automática y *outbox* transaccional (pendiente PIA).

## E6 — Autorización (matriz rol × acción)
Política en `src/domain/autorizacion.py`, probada con un oráculo independiente en `tests/test_autorizacion.py`
(8 acciones × 7 roles = 56 casos parametrizados + API). Sin rol/rol desconocido → **401**; rol sin permiso → **403**.
| Acción \ Rol | CLIENTE | VENDEDOR | CAJERO | SUPERVISOR | ALMACEN | ADMINISTRADOR | SISTEMA |
|---|---|---|---|---|---|---|---|
| CONSULTAR_STOCK | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| CONSULTAR_APARTADO | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✘ |
| CREAR_APARTADO | ✘ | ✔ | ✔ | ✔ | ✘ | ✘ | ✘ |
| REGISTRAR_ABONO | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ | ✘ |
| ENTREGAR_APARTADO | ✘ | ✘ | ✔ | ✔ | ✔ | ✘ | ✘ |
| PROCESAR_VENTA | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ | ✘ |
| PROCESAR_DEVOLUCION | ✘ | ✘ | ✔ | ✔ | ✘ | ✘ | ✘ |
| PROCESAR_VENCIMIENTOS | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ | ✔ |

Autenticación ≠ autorización: `test_cajero_con_rol_valido_aun_necesita_clave_de_supervisor` — el rol CAJERO puede
*iniciar* una devolución, pero sin la clave de un Supervisor **activo** el dominio responde 403.
**Supuestos a validar con el profesor:** ALMACEN entrega apartados (glosario: «despacho»); el encabezado `X-Rol`
representa al usuario ya autenticado (no hay login real en esta unidad). Los permisos salen de BRD p.11–12.

## E7 — Cobertura y calidad
`pytest --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80` → **99.43 %** (`E7_cobertura.txt`;
reporte navegable en `htmlcov/index.html`, no se versiona). Cobertura ≠ 80 % de defectos detectados: por eso se
añadió el chequeo de **mutaciones** (E7b).
**Rama aún sin probar:** `src/infrastructure/carga_csv.py:68-73,78` (`main()`, el resumen por consola de
`python cargar_csv.py`): no contiene reglas de negocio, sólo imprime; se prefirió invertir en reglas. También
`servicios.py:83` (apartar una serie cuyo SKU ya no existe en el catálogo → 404): es una rama relevante pendiente.

### E7b — ¿Detectan defectos las pruebas? (mutaciones manuales)
`tools/mutar.py` inyecta 14 defectos en una copia del código (p. ej. `<=` → `<` en el vencimiento, 20 % → 10 %,
devolución sin clave de Supervisor, ALMACEN puede vender, rollback omitido, eventos antes del commit) y exige
que alguna prueba falle: **14/14 detectados** (`evidencias/mutaciones.txt`).

## E8 — Pipeline de CI
Workflow: `.github/workflows/ci.yml` (ruff → pytest con `--cov-fail-under=80` → E01–E15 → compileall → artefacto htmlcov).
`tools/ci_local.py` ejecuta los mismos pasos; `evidencias/E8_ci_local.txt` muestra **verde → rojo → verde**:
al romper a propósito el dominio (anticipo 20 % → 10 %) fallan 11 pruebas y el pipeline sale con código 1;
al revertir vuelve a verde (241 passed).
> ⚠ **Esto es una simulación local, no una ejecución de GitHub Actions.** Falta que el equipo haga `git push`,
> capture la ejecución verde, provoque una roja (cambiar una aserción), la recupere y capture la URL del repo.
> Bloquear el merge exige configurar *branch protection / rulesets*; el YAML solo no lo hace.

## E9 — Matriz de casos y adaptación al PIA
`docs/matriz_pruebas.csv` (generada por `tools/generar_matriz.py` con el resultado **real** de pytest): 47 casos con
regla, referencia BRD/US, entrada, esperado, tipo, nivel y prueba ejecutable. Reglas reales de TecnoStock (BRD),
cada una con éxito + error + límite: **anticipo 20 %**, **vigencia 30 días y penalización 10 %**, **máximo 3
apartados**, **devolución 15 días con Supervisor**, cuadratura de pagos y serie obligatoria.
`tests/test_matriz.py` falla si la matriz apunta a una prueba que ya no existe.
Decisiones de diseño: reglas en el dominio (no en la API); Specifications para elegibilidad; eventos publicados sólo
tras commit; Decimal/texto exacto para dinero; UoW por operación (seguro con peticiones concurrentes).

## Bitácora de uso de IA (obligatoria)
Se usó un asistente de IA (Claude Code) como apoyo para proponer casos de prueba y código y para automatizar evidencias.
Cada resultado se ejecutó y se contrastó con el BRD. Las iteraciones se conservan en el historial de sesión del equipo.

| # | Objetivo | Propuesta de la IA | Error / supuesto detectado | Decisión humana / corrección |
|---|---|---|---|---|
| 1 | Entender la tarea | Tomar `techstore-u4` como base | Era el ejemplo del profesor; el equipo lo copió por parecido de nombre | El usuario aclaró: rehacer U4 para TecnoStock |
| 2 | Dominio TecnoStock | Basarse en el CSV del PIA (comprador/operación) | El caso y el BRD hablan de apartados/series/devoluciones; el LEEME dice que el CSV es solo propuesta | Se usó el BRD y la arquitectura U3 (`TecnoStock-U3/`) |
| 3 | Reglas de ruff | Dejar `ruff` con su configuración por defecto | La versión nueva activa reglas extra y rompía el CI | Se fijó `ruff.toml` (E4,E7,E9,F,I) |
| 4 | Pruebas de rollback | Un test que parchaba el catálogo con un truco | Ilegible y frágil | Se reescribió con `dataclasses.replace` |
| 5 | Mutaciones | Dos «mutantes» vacíos (no cambiaban nada) | Habrían contado como detectados sin serlo | Se reemplazaron por mutantes reales de SQL y se añadió la prueba que faltaba |
| 6 | Simulación de CI | Copiar solo `src`/`tests` | Faltaba `docs/` y fallaban 2 pruebas por la copia, no por el código | Se copió el proyecto completo y se repitió |
| 7 | Sesgo de redondeo | Redondeo normal del 20 % | Con 100.02 permitía un anticipo menor al 20 % | TDD: prueba roja y redondeo hacia arriba |

## Reflexión (BORRADOR — cada integrante debe reescribirla con sus palabras, 150–200 palabras)
El defecto más costoso en producción sería vender por error una laptop que ya estaba apartada, o liberar un apartado
antes de tiempo. El cliente que dejó su anticipo llegaría a una tienda sin producto y habría que reembolsar, además
de perder su confianza; es exactamente el problema ISS-02 del BRD. Lo previenen varias pruebas en capas: la regla
del 20 % y los límites del día 30/31 en el dominio, la prueba que impide vender una serie RESERVADA, y el índice único
en la base de datos que impide dos apartados vigentes de la misma serie. Aprendí que cubrir líneas no basta: un test
sin aserciones sube la cobertura pero no protege nada, por eso inyectamos defectos a propósito y comprobamos que las
pruebas fallan. También aprendí que el rollback debe probarse a mitad de una operación, no solo cuando todo sale
bien, y que los eventos solo deben publicarse después de confirmar la transacción.

## Pendientes del EQUIPO antes de entregar
- [ ] Capturas legibles de: `pytest` (E1), RED y GREEN (E3), `test_persistencia_sql` (E4), mocks (E5), matriz (E6), `htmlcov/index.html` (E7).
- [ ] `git init` + push al repositorio acordado; ejecución **real** de Actions: verde → roja → verde (E8) y URL del repo.
- [ ] Verificar con Python 3.11 (el del CI): `py -3.11` está dañado en la máquina donde se desarrolló.
- [ ] Validar con el profesor los supuestos: `requiere_serie`, día 30/31, día 15/16, rol ALMACEN entrega.
- [ ] Reescribir la reflexión y agregar los prompts propios a la bitácora de IA.
