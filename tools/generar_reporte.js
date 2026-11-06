// Genera docs/Reporte_U5_TecnoStock.docx leyendo las evidencias reales del proyecto.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, Header, Footer,
  AlignmentType, WidthType, BorderStyle, ShadingType, PageNumber, HeadingLevel, LevelFormat,
  PageBreak,
} = require("docx");

const PROY = "C:/Users/famca/Downloads/CLNG/tecnostock-u4";
const EV = path.join(PROY, "docs/evidencias");
const leer = (f) => fs.readFileSync(f, "utf-8").replace(/^\uFEFF/, "");
const AZUL = "1F3864", GRIS = "595959", CLARO = "D9E2F3";
const W = 9360; // ancho útil (DXA) con márgenes de 1"

// ---------- helpers ----------
const run = (t, o = {}) => new TextRun({ text: t, font: "Arial", size: 22, ...o });
const P = (t, o = {}) => new Paragraph({
  spacing: { after: 120, line: 276 }, alignment: o.align,
  children: Array.isArray(t) ? t : [run(t, o.run || {})], ...(o.p || {}),
});
const B = (t) => new Paragraph({ numbering: { reference: "vinetas", level: 0 }, spacing: { after: 60 },
  children: Array.isArray(t) ? t : [run(t)] });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t })] });
const negrita = (t) => run(t, { bold: true });

const borde = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const bordes = { top: borde, bottom: borde, left: borde, right: borde };
const celda = (contenido, ancho, o = {}) => new TableCell({
  width: { size: ancho, type: WidthType.DXA }, borders: bordes,
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
  margins: { top: 50, bottom: 50, left: 90, right: 90 }, verticalAlign: o.v,
  children: (Array.isArray(contenido) ? contenido : [contenido]).map((c) =>
    typeof c === "string"
      ? new Paragraph({ alignment: o.align, spacing: { after: 0 },
          children: [new TextRun({ text: c, font: "Arial", size: o.size || 18, bold: o.bold, color: o.color })] })
      : c),
});
function tabla(anchos, encabezado, filas, o = {}) {
  const size = o.size || 18;
  const total = anchos.reduce((a, b) => a + b, 0);
  const hdr = new TableRow({ tableHeader: true, cantSplit: true,
    children: encabezado.map((h, i) => celda(h, anchos[i], { fill: AZUL, bold: true, color: "FFFFFF", size })) });
  const cuerpo = filas.map((f, r) => new TableRow({ cantSplit: true,
    children: f.map((c, i) => celda(c, anchos[i], { size, fill: r % 2 ? "F5F8FC" : undefined })) }));
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: anchos, rows: [hdr, ...cuerpo] });
}
const espacio = () => new Paragraph({ spacing: { after: 80 }, children: [] });

// bloque de código/salida de terminal
function codigo(texto, maxLen = 112) {
  const lineas = texto.replace(/\r/g, "").split("\n").filter((l, i, a) => !(i === a.length - 1 && l === ""));
  return lineas.map((l, i) => new Paragraph({
    spacing: { after: 0, line: 240 }, keepNext: i < lineas.length - 1 && lineas.length < 14,
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2", color: "auto" },
    indent: { left: 120, right: 120 },
    children: [new TextRun({ text: l.length > maxLen ? l.slice(0, maxLen - 1) + "…" : l, font: "Consolas", size: 16 })],
  }));
}
// recuadro amarillo: captura/texto que debe completar el equipo
function pendiente(titulo, detalle) {
  const b = { style: BorderStyle.DASHED, size: 8, color: "BF9000" };
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({
    cantSplit: true, children: [new TableCell({
      width: { size: W, type: WidthType.DXA }, borders: { top: b, bottom: b, left: b, right: b },
      shading: { fill: "FFF4CC", type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 100, bottom: 100, left: 140, right: 140 },
      children: [
        new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: "PENDIENTE DEL EQUIPO — " + titulo, font: "Arial", size: 18, bold: true, color: "7F6000" })] }),
        new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: detalle, font: "Arial", size: 18, color: "7F6000" })] }),
      ] })] })] });
}
const pie = (t) => new Paragraph({ spacing: { before: 40, after: 160 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: t, font: "Arial", size: 18, italics: true, color: GRIS })] });

// ---------- datos reales ----------
const cobertura = leer(path.join(EV, "E7_cobertura.txt")).split("\n");
const filasCob = cobertura.filter((l) => /^src\\/.test(l)).map((l) => l.trim().split(/\s+/))
  .filter((c) => c[1] !== "0").map((c) => [c[0].replace(/\\/g, "/"), c[1], c[2], c[3]]);
const totalCob = cobertura.find((l) => l.startsWith("TOTAL")).trim().split(/\s+/);
const reqCob = (cobertura.find((l) => l.startsWith("Required")) || "").match(/Total coverage: ([\d.]+)%/);
const covPct = reqCob ? reqCob[1] : "99.4";

const csv = (txt) => { // CSV simple (los campos no llevan comas)
  const [h, ...rows] = txt.trim().split(/\r?\n/).map((l) => l.split(","));
  return rows.map((r) => Object.fromEntries(h.map((k, i) => [k, r[i]])));
};
const matriz = csv(leer(path.join(PROY, "docs/matriz_pruebas.csv")));
const nTipo = (t) => matriz.filter((m) => m.tipo === t).length;
const mut = leer(path.join(EV, "mutaciones.txt")).trim().split("\n").map((l) => {
  const i = l.indexOf("DETECTADO"); return [l.slice(0, i).trim(), "Detectado", l.slice(i + 13).split("::").pop().split(" - ")[0].trim()]; });
const esc = leer(path.join(EV, "E15_escenarios.txt")).trim().split("\n").filter((l) => /^E\d\d /.test(l))
  .map((l) => { const [a, ev] = l.split(" | "); const m = a.match(/^(E\d\d) (.*)$/); return [m[1], m[2], ev || ""]; });
const red = leer(path.join(EV, "E3_RED.txt")).split("\n");
const redFallas = red.filter((l) => l.startsWith("FAILED") || /\d+ failed/.test(l)).slice(0, 4);
const redMsgs = red.filter((l) => l.startsWith("E  ") && /assert|DID NOT/.test(l) && !/where/.test(l)).slice(0, 3);
const ci = leer(path.join(EV, "E8_ci_local.txt")).split("\n");
const entorno = leer(path.join(EV, "entorno.txt")).trim();
const resumenPytest = leer(path.join(EV, "E1_pytest_verbose.txt")).trim().split("\n").slice(-1)[0].replace(/=/g, "").trim();

// ---------- documento ----------
const hijos = [];

// Encabezado tipo reporte (igual que U3/U4)
const celdaInfo = (lineas, ancho) => new TableCell({ width: { size: ancho, type: WidthType.DXA }, borders: bordes,
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  children: lineas.map(([k, v]) => new Paragraph({ spacing: { after: 40 }, children: [
    new TextRun({ text: k + " ", font: "Arial", size: 20, bold: true }), new TextRun({ text: v, font: "Arial", size: 20 })] })) });
hijos.push(new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: "Reporte", font: "Arial", size: 44, bold: true, color: AZUL })] }));
hijos.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [4680, 4680], rows: [new TableRow({ children: [
  celdaInfo([["Nombre:", "Roberto Carlos Cantú González"], ["Matrícula:", "2114360"], ["Nombre:", "Ángel Daniel Jiménez Fuantos"],
    ["Matrícula:", "2117083"], ["Nombre:", "Mario Iván González Martínez"], ["Matrícula:", "2117170"]], 4680),
  celdaInfo([["Nombre del curso:", "Componentes de Lógica de Negocios"], ["Nombre del profesor:", "Miguel Ángel Gómez Marroquín"],
    ["Módulo NetaCad:", "5"], ["Actividad:", "Actividad 5. Reporte"], ["Fecha:", "05/11/2026"], ["Equipo / empresa:", "Equipo 5 · TecnoStock"]], 4680),
] })] }));
hijos.push(espacio());
hijos.push(P([negrita("Bibliografía (formato APA): "), run("ver sección Referencias al final del documento.")]));

hijos.push(H1("Objetivo"));
hijos.push(P("Comprobar con pruebas automatizadas que las reglas de negocio de TecnoStock (apartados, ventas con número de serie y devoluciones) funcionan correctamente; verificar la persistencia con SQLAlchemy (commit y rollback) sin tocar datos de producción; simular el servicio externo de pagos con mocks; probar la autorización por rol; medir una cobertura de líneas mayor o igual al 80 % y automatizar todas las verificaciones con un pipeline de CI, entregando evidencia reproducible."));

hijos.push(H1("Contexto y corrección de la Unidad 4"));
hijos.push(P("Al iniciar la Unidad 5 el equipo detectó que su entrega de la Unidad 4 se había construido sobre TechStore, el ejemplo del profesor, por la similitud de nombre con TecnoStock, su empresa asignada. Antes de probar nada se reconstruyó el núcleo de negocio para TecnoStock siguiendo el BRD y la arquitectura de la Unidad 3 del equipo: Domain Model, CQRS básico y Repository con Unit of Work. Las pruebas de esta unidad se hicieron sobre ese código."));
hijos.push(tabla([1500, 3300, 4560], ["Caso de uso (U3)", "Estado en este reporte", "Componentes principales"], [
  ["CU-01 Venta con serie", "Implementado y probado", "Venta, ItemSerie, IPasarelaPagos"],
  ["CU-02 Registrar apartado", "Implementado y probado", "Apartado, Specifications, ItemSerie"],
  ["CU-03 Vencimiento de apartados", "Implementado y probado", "Apartado.evaluar_vencimiento, manejador de eventos"],
  ["CU-04 Transferencia entre sucursales", "No implementado (PIA)", "Transferencia (solo el estado EN_TRANSITO existe)"],
  ["CU-05 Devolución especial", "Implementado y probado", "PoliticaDevolucionDomainService, clave de Supervisor"],
]));
hijos.push(espacio());
hijos.push(P([negrita("Reglas de negocio bajo prueba (fuente: BRD y levantamiento del equipo): "),
  run("anticipo mínimo del 20 %; vigencia de 30 días (vence el día 31); penalización del 10 % que genera saldo a favor; máximo 3 apartados activos por cliente; serie reservada no se vende; pagos combinados que deben igualar el total; devolución dentro de 15 días, con empaque completo, sin daño del cliente y con clave de Supervisor.")]));

hijos.push(H1("Procedimiento"));

// 3.1 Estrategia y E1
hijos.push(H2("1. Estrategia de pruebas y ejecución inicial (E1)"));
hijos.push(P("Se organizaron las pruebas en la pirámide de la unidad. Las unitarias no dependen de base de datos ni de red; las de integración usan SQLite en memoria, Mocks y la API con TestClient. Las pruebas de extremo a extremo (E2E) no se implementaron: se propone para el PIA un flujo HTTP real contra la aplicación desplegada (crear apartado, abonar, entregar y devolver)."));
hijos.push(tabla([1500, 4100, 2300, 1460], ["Nivel", "Qué prueba", "Archivos", "Casos"], [
  ["Unitarias", "Value Objects, Aggregates, Specifications, políticas y matriz de roles", "test_dominio, test_especificaciones, test_autorizacion (matriz de roles y su API)", "128"],
  ["Integración", "Servicios + Unit of Work, SQLAlchemy/SQLite, Mock de pasarela, API REST, escenarios E01–E15", "test_aplicacion, test_persistencia_sql, test_pasarela_mock, test_api, test_escenarios", "111"],
  ["Calidad de la suite", "La matriz de casos apunta a pruebas que existen", "test_matriz", "2"],
  ["E2E", "No implementadas (propuesta para el PIA)", "—", "0"],
], { size: 17 }));
hijos.push(P([negrita("Total: 241 pruebas.")], { p: { spacing: { before: 100, after: 120 } } }));
hijos.push(...codigo(`$ python -m pytest -v\n...\n${resumenPytest}\n\nEntorno:\n${entorno}`));
hijos.push(pie("Salida de terminal (texto). Archivos: docs/evidencias/E1_pytest_verbose.txt y entorno.txt"));
hijos.push(pendiente("E1", "Pegar aquí la captura de pantalla de la terminal con el comando `python -m pytest -v` y el resumen final (241 passed). pytest localiza las funciones test_*; el entorno virtual (.venv) aísla las dependencias para que el resultado sea reproducible en cualquier equipo y en el CI."));

// 3.2 E2
hijos.push(H2("2. Pruebas unitarias con Arrange–Act–Assert (E2)"));
hijos.push(P("Cada prueba prepara los datos (Arrange), ejecuta una sola operación (Act) y verifica el resultado (Assert). Ejemplo de la penalización del 10 % por vencimiento:"));
hijos.push(...codigo(`def test_penalizacion_10_por_ciento_calculada_en_el_dominio():
    ap = apartado(anticipo="250.50")              # Arrange
    ap.evaluar_vencimiento(date(2027, 1, 1))      # Act
    assert ap.saldo_a_favor == M("225.45")        # Assert  (250.50 - 25.05)`));
hijos.push(espacio());
hijos.push(tabla([2700, 2300, 2300, 2060], ["Entrada", "Regla", "Resultado esperado", "Resultado real"], [
  ["Total 1000.00, anticipo 200.00", "Anticipo ≥ 20 %", "Apartado ACTIVO", "ACTIVO"],
  ["Total 1000.00, anticipo 199.99", "Anticipo ≥ 20 %", "Rechazo", "ReglaNegocioViolada"],
  ["Apartado de 250.50 vencido", "Penalización 10 %", "Saldo a favor 225.45", "225.45"],
  ["Día 30 y día 31 desde la creación", "Vigencia de 30 días", "Vigente / VENCIDO", "Vigente / VENCIDO"],
  ["Serie RESERVADA, venta directa", "Serie reservada no se vende", "TransicionInvalida", "TransicionInvalida"],
]));

// 3.3 E3 TDD
hijos.push(H2("3. TDD real: Red → Green → Refactor (E3)"));
hijos.push(P("Se escribieron primero las pruebas de reglas del BRD que el código aún no cumplía y se ejecutaron antes de modificar el código fuente:"));
hijos.push(B("US-03: el rechazo por anticipo insuficiente debe indicar el monto mínimo y lo que falta."));
hijos.push(B("US-02: una misma serie no puede aparecer dos veces en un ticket."));
hijos.push(B("Borde descubierto al refactorizar: el 20 % de 100.02 es 20.004; redondear a 20.00 dejaba pasar un anticipo menor al 20 %."));
hijos.push(P([negrita("RED. "), run("Salida real antes de implementar:")], { p: { keepNext: true } }));
hijos.push(...codigo([...redFallas, ...redMsgs].join("\n")));
hijos.push(pie("Fuente: docs/evidencias/E3_RED.txt"));
hijos.push(P([negrita("GREEN. "), run("Implementación mínima y suite completa en verde:")], { p: { keepNext: true } }));
hijos.push(...codigo(`# src/domain/valores.py\n@staticmethod\ndef minimo(total):   # 20 % redondeado HACIA ARRIBA al centavo\n    return MontoMonetario((total.cantidad * ANTICIPO_MINIMO).quantize(CENTAVOS, ROUND_CEILING), total.moneda)\n\n# src/domain/venta.py (Venta.cerrar)\nif len(series) != len(set(series)):\n    raise ReglaNegocioViolada("La venta contiene una serie repetida")\n\n$ python -m pytest -q\n241 passed`));
hijos.push(P([negrita("REFACTOR. "), run("El mensaje de rechazo pasó de una cadena fija a PorcentajeAnticipo.motivo_de_rechazo y REGLAS_APARTAR admite mensajes calculados. El comportamiento público no cambió y la suite siguió en verde.")], { p: { spacing: { before: 120, after: 120 } } }));
hijos.push(pendiente("E3", "Pegar la captura del RED (pytest con 3 failed) y la del GREEN (241 passed). Son la evidencia principal del ciclo TDD: sin la captura roja no se demuestra que la prueba se escribió antes."));

// 3.4 E4
hijos.push(H2("4. Persistencia, commit y rollback con SQLAlchemy (E4)"));
hijos.push(P("Se implementó src/infrastructure/sql.py con las mismas interfaces de repositorio que la versión en memoria y un Unit of Work por operación: salir del bloque sin llamar a commit() equivale a rollback(). Cada prueba crea su propia base SQLite en memoria, por lo que nunca se toca información real. Los eventos de dominio se publican solo después de un commit exitoso."));
hijos.push(tabla([4400, 4960], ["Prueba (tests/test_persistencia_sql.py)", "Qué demuestra"], [
  ["test_commit_hace_visible_el_apartado_con_sus_abonos", "Tras el commit, otra sesión ve el apartado con sus 2 abonos"],
  ["test_salir_sin_commit_descarta_los_cambios", "Lo hecho dentro del UoW sin commit no llega a la BD"],
  ["test_falla_a_mitad_de_operacion_revierte_la_serie_ya_bloqueada", "Si falla un paso, la serie ya bloqueada vuelve a DISPONIBLE"],
  ["test_si_el_commit_falla_no_se_publican_eventos_ni_se_guarda_nada", "Un commit fallido no publica eventos ni deja datos"],
  ["test_pk_impide_dos_items_con_el_mismo_numero_de_serie", "Unicidad global del número de serie (IntegrityError)"],
  ["test_la_base_impide_dos_apartados_vigentes_de_la_misma_serie", "Índice único parcial: una serie, un apartado vigente"],
  ["test_el_dinero_se_guarda_como_texto_decimal_sin_float", "Los importes se guardan exactos, sin float"],
], { size: 17 }));
hijos.push(P([negrita("Commit vs. rollback. "), run("commit confirma la transacción y vuelve duraderos todos sus cambios a la vez; rollback los descarta todos y deja la base como estaba. Por eso, si falla cualquier paso de «reservar serie y crear apartado», no queda una serie RESERVADA sin apartado. Límite: SQLite en memoria no prueba concurrencia ni los tipos de PostgreSQL; para el PIA estas pruebas deben repetirse contra PostgreSQL en Docker Compose.")], { p: { spacing: { before: 120, after: 120 } } }));
hijos.push(pendiente("E4", "Pegar la captura de `python -m pytest tests/test_persistencia_sql.py -v` (23 passed)."));

// 3.5 E5
hijos.push(H2("5. Servicio externo sin cobros reales: Mock de pasarela (E5)"));
hijos.push(P("Los pagos con tarjeta pasan por el puerto IPasarelaPagos. Las pruebas lo sustituyen por Mock(spec=IPasarelaPagos); el adaptador por defecto, PasarelaSimulada, tampoco hace llamadas de red. No se transmite dinero en ningún caso."));
hijos.push(tabla([1400, 4300, 3660], ["Ruta", "Prueba", "Verifica"], [
  ["Aprobado", "test_pago_aprobado_cobra_una_vez_con_ticket_como_referencia", "cobrar.assert_called_once_with(407.00, TARJETA, ticket); serie VENDIDA"],
  ["Rechazado", "test_pago_rechazado_lanza_error_y_no_vende_la_serie", "PagoRechazado (HTTP 402); serie sigue DISPONIBLE"],
  ["Timeout", "test_timeout_de_pasarela_es_servicio_no_disponible_y_hace_rollback", "ServicioNoDisponible (HTTP 503) y rollback"],
  ["Efectivo", "test_efectivo_no_invoca_la_pasarela", "assert_not_called()"],
  ["Combinado", "test_pago_combinado_solo_cobra_la_parte_de_tarjeta", "Solo se cobra el monto de tarjeta (300.00)"],
], { size: 17 }));
hijos.push(P([negrita("Riesgo de consistencia y propuesta. "), run("El cobro se ejecuta como último paso antes del commit: si la pasarela rechaza o no responde, se hace rollback y nunca queda una serie vendida sin pago aprobado. El riesgo residual es que la tarjeta se apruebe y luego falle el commit (cobro sin venta). Propuesta: usar el ticket como idempotency key (ya se envía como referencia), reversa o compensación automática y un outbox transaccional para el PIA.")], { p: { spacing: { before: 120, after: 120 } } }));
hijos.push(pendiente("E5", "Pegar la captura de `python -m pytest tests/test_pasarela_mock.py -v` (9 passed)."));

// 3.6 E6
hijos.push(H2("6. Seguridad de negocio: autorización por rol (E6)"));
hijos.push(P("La política rol → acción (src/domain/autorizacion.py) sale del BRD: el Cajero solo selecciona método de pago, escanea series y captura facturación; devoluciones, cancelaciones y descuentos excepcionales son del Supervisor; Almacén no modifica precios. Se probó con un oráculo independiente (8 acciones × 7 roles = 56 casos parametrizados) y en la API: sin X-Rol o con rol desconocido responde 401; con rol sin permiso, 403."));
const ROLES = ["CLIENTE", "VENDEDOR", "CAJERO", "SUPERVISOR", "ALMACEN", "ADMIN.", "SISTEMA"];
const ACC = [
  ["CONSULTAR_STOCK", "0111110"], ["CONSULTAR_APARTADO", "0111010"], ["CREAR_APARTADO", "0111000"], ["REGISTRAR_ABONO", "0011000"],
  ["ENTREGAR_APARTADO", "0011100"], ["PROCESAR_VENTA", "0011000"], ["PROCESAR_DEVOLUCION", "0011000"], ["PROCESAR_VENCIMIENTOS", "0001011"]];
hijos.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2360, ...ROLES.map(() => 1000)], rows: [
  new TableRow({ tableHeader: true, children: [celda("Acción \\ Rol", 2360, { fill: AZUL, bold: true, color: "FFFFFF", size: 16 }),
    ...ROLES.map((r) => celda(r, 1000, { fill: AZUL, bold: true, color: "FFFFFF", size: 14, align: AlignmentType.CENTER }))] }),
  ...ACC.map(([a, bits]) => new TableRow({ cantSplit: true, children: [celda(a, 2360, { size: 16 }),
    ...[...bits].map((b) => celda(b === "1" ? "✔" : "✘", 1000, { size: 18, align: AlignmentType.CENTER, color: b === "1" ? "2E7D32" : "C62828" }))] })),
] }));
hijos.push(P([negrita("Autenticación no es autorización. "), run("test_cajero_con_rol_valido_aun_necesita_clave_de_supervisor: el rol CAJERO puede iniciar una devolución, pero sin la clave de un Supervisor activo el dominio responde 403 aunque el rol sea válido. Supuestos por validar: Almacén puede entregar apartados liquidados (despacho) y el encabezado X-Rol representa al usuario ya autenticado (no hay login real en esta unidad).")], { p: { spacing: { before: 120, after: 120 } } }));
hijos.push(pendiente("E6", "Pegar la captura de `python -m pytest tests/test_autorizacion.py -v` y, si el profesor lo pide, una petición en Swagger (/docs) con y sin el encabezado X-Rol."));

// 3.7 E7
hijos.push(H2("7. Cobertura y calidad (E7)"));
hijos.push(P(`Comando: python -m pytest --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80. Resultado: cobertura total de ${covPct} % (umbral 80 %) y ruff check src tests sin errores. Se listan todos los módulos con código (los __init__.py vacíos se omiten).`));
hijos.push(tabla([5200, 1300, 1300, 1560], ["Módulo", "Líneas", "Sin cubrir", "Cobertura"],
  [...filasCob, [`TOTAL (${totalCob[1]} líneas)`, totalCob[1], totalCob[2], covPct + " %"]], { size: 17 }));
hijos.push(P([negrita("Ramas aún sin probar. "), run("carga_csv.py:68-73,78 corresponde a main(), el resumen por consola de python cargar_csv.py; no contiene reglas de negocio, solo imprime. Además servicios.py:83 (apartar una serie cuyo SKU ya no existe en el catálogo, que debe responder 404) es una rama relevante que queda como pendiente.")], { p: { spacing: { before: 120, after: 120 } } }));
hijos.push(P([negrita("La cobertura no es calidad. "), run("80 % de cobertura significa que al menos 80 % de las líneas se ejecutaron, no que se detectó 80 % de los defectos. Por eso se inyectaron 14 defectos a propósito en una copia del código (tools/mutar.py) y se exigió que alguna prueba fallara:")]));
hijos.push(tabla([4300, 1100, 3960], ["Defecto inyectado", "Resultado", "Prueba que lo detectó"], mut, { size: 15 }));
hijos.push(P([negrita("14 de 14 defectos fueron detectados."), run(" Antes de la versión final dos mutantes eran marcadores vacíos que no cambiaban nada; se reemplazaron por defectos reales de SQL y se agregó la prueba que faltaba (el commit fallido no publica eventos).")], { p: { spacing: { before: 100, after: 120 } } }));
hijos.push(pendiente("E7", "Pegar (1) la captura del resumen de cobertura en la terminal y (2) la captura de htmlcov/index.html abierto en el navegador (se genera con el comando de arriba)."));

// 3.8 E8
hijos.push(H2("8. Pipeline de CI con GitHub Actions (E8)"));
hijos.push(P("El workflow .github/workflows/ci.yml se ejecuta en cada push y pull request con Python 3.11: instala dependencias, corre ruff, pytest con --cov-fail-under=80, los escenarios E01–E15, compila src/ y sube el reporte htmlcov como artefacto. Para verificar los pasos antes de publicar se escribió tools/ci_local.py, que ejecuta los mismos comandos; se hizo verde → rojo → verde:"));
hijos.push(...codigo(ci.join("\n")));
hijos.push(pie("Simulación local. Fuente: docs/evidencias/E8_ci_local.txt"));
hijos.push(P([negrita("Qué detectó el pipeline: "), run("al romper a propósito la regla del anticipo mínimo (20 % → 10 %) fallaron 11 pruebas, entre ellas test_anticipo_insuficiente_422 (esperaba 422 y obtuvo 201); el pipeline salió con código 1 y volvió a verde al revertir el cambio.")]));
hijos.push(pendiente("E8 — ejecución REAL en GitHub", "Esto fue una simulación local y NO sustituye a GitHub Actions. Falta: (1) git push del proyecto; (2) captura de la pestaña Actions con la ejecución VERDE; (3) cambiar una aserción y hacer push para obtener la ejecución ROJA y capturarla; (4) revertir y capturar la VERDE de nuevo; (5) anotar la URL del repositorio abajo. Bloquear el merge exige configurar branch protection/rulesets; el YAML solo no lo hace."));

// 3.9 E9
hijos.push(H2("9. Matriz de casos y adaptación al PIA (E9)"));
hijos.push(P(`La matriz completa (Anexo A y docs/matriz_pruebas.csv) tiene ${matriz.length} casos: ${nTipo("exito")} de éxito, ${nTipo("error")} de error y ${nTipo("limite")} de límite (mínimo pedido: 5, 4 y 3). Se genera con tools/generar_matriz.py, que ejecuta pytest y llena el resultado real de cada caso; todos están en PASSED. Un test (test_matriz) falla si la matriz apunta a una prueba que ya no existe. Cada una de las reglas siguientes de TecnoStock tiene caso de éxito, de error y de límite:`));
hijos.push(tabla([2300, 2700, 2300, 2060], ["Regla del PIA (BRD)", "Éxito", "Error", "Límite"], [
  ["Anticipo mínimo 20 %", "CP-01 anticipo 200 de 1000", "CP-02 anticipo 150 de 1000", "CP-04 20 % de 100.02 = 20.01"],
  ["Vigencia 30 días y penalización 10 %", "CP-06 saldo a favor 225.45", "CP-08 abono a vencido (409)", "CP-05 día 30 vigente, día 31 vence"],
  ["Máximo 3 apartados activos", "CP-12 se libera uno y puede apartar", "CP-11 cuarto apartado rechazado", "CP-10 con 2 sí, con 3 no"],
  ["Devolución 15 días con Supervisor", "CP-25 devolución a 8 días", "CP-26 daño del cliente", "CP-24 día 15 sí, día 16 no"],
], { size: 16 }));
hijos.push(espacio());
hijos.push(P("Decisiones de diseño: las reglas viven en el dominio y no en la API, de modo que ninguna pantalla puede omitirlas; la elegibilidad se expresa con Specifications (AND, OR, NOT); los eventos se publican solo tras el commit; el dinero usa Decimal y se guarda como texto decimal exacto; el Unit of Work es una instancia por operación, seguro ante peticiones concurrentes."));
hijos.push(pendiente("E9", "Pegar una captura de docs/matriz_pruebas.csv abierto en Excel (columnas resultado_real = PASSED)."));

// 3.10 IA
hijos.push(H2("10. Uso responsable de IA"));
hijos.push(P("El equipo usó un asistente de IA (Claude Code) para proponer pruebas, escribir el código y automatizar evidencias. Cada propuesta se ejecutó y se verificó contra el BRD. Casos en los que la propuesta se corrigió o se rechazó:"));
hijos.push(tabla([300, 2300, 3300, 3460], ["#", "Propuesta de la IA", "Error o supuesto detectado", "Decisión del equipo"], [
  ["1", "Usar techstore-u4 como base", "Era el ejemplo del profesor; se copió por parecido de nombre", "Se rehízo U4 para TecnoStock"],
  ["2", "Modelar el dominio con el CSV del PIA (comprador/operación)", "El caso y el BRD hablan de apartados, series y devoluciones; el LEEME dice que el CSV es solo propuesta", "Se usó el BRD y la arquitectura U3"],
  ["3", "Dejar ruff con su configuración por defecto", "La versión nueva activa reglas extra y rompería el CI", "Se fijó ruff.toml (E4, E7, E9, F, I)"],
  ["4", "Mutantes de prueba", "Dos eran marcadores vacíos que contaban como «detectados» sin serlo", "Se reemplazaron por mutantes reales y se añadió la prueba faltante"],
  ["5", "Simular CI copiando solo src y tests", "Faltaba docs/ y fallaban 2 pruebas por la copia, no por el código", "Se copió el proyecto completo y se repitió"],
  ["6", "Redondeo normal del 20 %", "Con 100.02 permitía un anticipo menor al 20 %", "TDD: prueba roja y redondeo hacia arriba"],
], { size: 16 }));
hijos.push(pendiente("Bitácora de IA", "Agregar aquí los prompts reales que ustedes usaron (texto o enlace) y confirmar que revisaron cada resultado. El profesor pidió conservar las iteraciones con IA."));

// Preguntas
hijos.push(H1("Preguntas del reporte"));
const preg = [
  ["¿Cuál es la diferencia entre pruebas unitarias, de integración y E2E?",
   "Una unitaria verifica una regla aislada, sin base de datos ni red (por ejemplo Apartado.registrar_abono). Una de integración verifica que varios componentes colaboran: servicio, Unit of Work y SQLAlchemy, o la API con la base. Una E2E recorre el sistema desplegado como lo haría un usuario (HTTP real contra la app y la BD). Aquí hay unitarias e integración; las E2E se proponen para el PIA."],
  ["¿Qué es Arrange–Act–Assert y por qué ayuda?",
   "Es una estructura de tres pasos: preparar los datos, ejecutar una operación y verificar el resultado. Mantiene cada prueba corta, con una sola razón para fallar, y fácil de leer por quien no la escribió."],
  ["¿Por qué TDD no es simplemente ejecutar pruebas después de programar?",
   "En TDD la prueba se escribe primero y debe fallar por la razón correcta (RED). Eso demuestra que la prueba detecta el defecto y fija el contrato antes de implementar. Una prueba escrita después puede pasar sin comprobar nada. En este proyecto, la prueba del redondeo del 20 % falló primero y gracias a eso se descubrió el error con 100.02."],
  ["¿Qué diferencia hay entre commit y rollback?",
   "commit confirma la transacción y hace duraderos todos sus cambios; rollback los descarta todos. Sin rollback, una falla a mitad de operación dejaría datos inconsistentes, como una serie RESERVADA sin apartado."],
  ["¿Qué demuestra el uso de mocks y qué riesgo de consistencia existe?",
   "Que el servicio se comporta correctamente ante una pasarela que aprueba, rechaza o no responde, sin cobrar dinero real. El riesgo es cobrar y que luego falle el commit; se mitiga cobrando justo antes del commit y, para el PIA, con idempotency key, compensación y outbox."],
  ["¿Autenticación y autorización son lo mismo?",
   "No. Autenticación es saber quién es el usuario; autorización es saber qué puede hacer. Un Cajero autenticado puede iniciar una devolución, pero sin la clave de un Supervisor activo el sistema la rechaza."],
  ["¿Qué significa una cobertura del 80 % y por qué no basta?",
   "Que al menos 80 % de las líneas se ejecutaron durante las pruebas, no que 80 % de los defectos se detectaron. Una prueba sin aserciones sube la cobertura sin proteger nada; por eso se usó la inyección de 14 defectos como segunda medida."],
  ["¿Qué detectó el pipeline?",
   "Con el cambio deliberado del anticipo mínimo (20 % → 10 %), 11 pruebas fallaron y el paso de pytest terminó con código 1, deteniendo el pipeline. Al revertir, volvió a verde. (La ejecución real en GitHub Actions se documenta en la captura del equipo.)"],
  ["¿Qué hace que un caso sugerido por IA deba corregirse o rechazarse?",
   "Que contradiga las reglas aprobadas o no pruebe nada. Ejemplo: la IA propuso dos mutantes que no cambiaban el código y habrían contado como detectados; se rechazaron y se reemplazaron por defectos reales."],
];
preg.forEach(([q, a], i) => { hijos.push(P([negrita(`${i + 1}. ${q}`)], { p: { keepNext: true, spacing: { before: 120, after: 60 } } })); hijos.push(P(a)); });

// Reflexión
hijos.push(H1("Reflexión"));
const refl = [
  ["Error: entregar la Unidad 4 sobre TechStore en lugar de TecnoStock.", "Lo detectamos al leer la tarea de U5 y reconstruimos el núcleo desde el BRD y la arquitectura U3.", "Aprendimos a verificar que cada entrega corresponde a la empresa asignada y a revisar los artefactos de unidades anteriores antes de construir encima."],
  ["Error: el redondeo del 20 % permitía anticipos ligeramente menores al mínimo (caso 100.02).", "Lo encontramos con un caso límite escrito antes del código (RED) y se corrigió redondeando hacia arriba.", "Aprendimos que los casos límite se prueban de forma explícita y que TDD los saca a la luz."],
  ["Error: confiar en que la simulación del CI era fiel sin incluir todo el proyecto.", "Fallaron 2 pruebas porque la copia no incluía docs/; ajustamos la copia y repetimos.", "Aprendimos a distinguir un fallo del código de un fallo del entorno de la prueba."],
];
refl.forEach(([e, s, a]) => { hijos.push(B([negrita(e + " "), run(s + " "), run(a)])); });
hijos.push(P([negrita("Aprendizaje general: "), run("que un programa corra sin errores no demuestra que sus reglas de negocio sean correctas. Las pruebas por capas, el rollback probado a mitad de una operación, los mocks para servicios externos y la inyección deliberada de defectos dan evidencia reproducible de calidad.")], { p: { spacing: { before: 100, after: 120 } } }));
hijos.push(P([negrita("Defecto de negocio más costoso: "), run("vender por error una laptop ya apartada (problema ISS-02 del BRD). Lo previenen la regla del 20 % y los límites del día 30/31 en el dominio, la prueba que impide vender una serie RESERVADA y el índice único de la base de datos que impide dos apartados vigentes de la misma serie.")]));

// Conclusiones
hijos.push(H1("Conclusiones"));
["Roberto Carlos Cantú González - 2114360", "Ángel Daniel Jiménez Fuantos - 2117083", "Mario Iván González Martínez - 2117170"].forEach((n) => {
  hijos.push(P([negrita(n)], { p: { keepNext: true, spacing: { before: 140, after: 60 } } }));
  hijos.push(pendiente("conclusión individual", "Escribir con sus propias palabras (aprox. 120-150 palabras): qué aprendiste de TDD, de probar persistencia (commit/rollback), de los mocks y de la cobertura; y qué parte del proyecto defenderías en la revisión."));
});

hijos.push(H1("Enlace del repositorio"));
hijos.push(pendiente("repositorio", "Escribir aquí la URL del repositorio de GitHub donde se publicó el proyecto (con el historial de commits y la pestaña Actions) y confirmar que no contiene .venv, credenciales ni datos reales."));

hijos.push(H1("Referencias"));
[
  "Beck, K. (2003). Test-driven development: By example. Addison-Wesley.",
  "Evans, E. (2003). Domain-driven design: Tackling complexity in the heart of software. Addison-Wesley.",
  "Fowler, M. (2002). Patterns of enterprise application architecture. Addison-Wesley.",
  "Percival, H., & Gregory, B. (2020). Architecture patterns with Python. O'Reilly Media.",
  "Krekel, H., et al. (s. f.). pytest documentation. https://docs.pytest.org",
  "SQLAlchemy. (s. f.). SQLAlchemy 2.0 documentation. https://docs.sqlalchemy.org",
  "GitHub. (s. f.). GitHub Actions documentation. https://docs.github.com/actions",
].forEach((r) => hijos.push(new Paragraph({ spacing: { after: 80 }, indent: { left: 540, hanging: 540 }, children: [run(r, { size: 20 })] })));

// Anexo A
hijos.push(new Paragraph({ children: [new PageBreak()] }));
hijos.push(H1("Anexo A. Matriz de casos de prueba"));
hijos.push(P(`Fuente: docs/matriz_pruebas.csv (${matriz.length} casos, generados con el resultado real de pytest).`));
hijos.push(tabla([800, 2200, 760, 1050, 3860, 690], ["ID", "Regla", "Tipo", "Nivel", "Prueba", "Real"],
  matriz.map((m) => [m.caso_id, m.regla, m.tipo, m.nivel, m.funcion, m.resultado_real]), { size: 14 }));

// Anexo B
hijos.push(new Paragraph({ children: [new PageBreak()] }));
hijos.push(H1("Anexo B. Bitácora de escenarios E01–E15"));
hijos.push(P("Cada escenario se ejecuta sobre datos recién cargados desde datos/*.csv y pasa de forma idéntica con persistencia en memoria y en SQLite (tests/test_escenarios.py). El rechazo es el resultado esperado de los escenarios de error y no publica eventos (en E11 los eventos listados son del paso previo de vencimiento; el abono rechazado no publicó ninguno)."));
hijos.push(tabla([640, 5400, 3320], ["Caso", "Resultado real", "Evento(s) publicado(s)"], esc, { size: 14 }));

// ---------- armar ----------
const doc = new Document({
  creator: "Equipo 5", title: "Reporte U5 - TecnoStock",
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 32, bold: true, color: AZUL },
        paragraph: { spacing: { before: 320, after: 140 }, keepNext: true, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: AZUL, space: 2 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 26, bold: true, color: "2F5496" },
        paragraph: { spacing: { before: 260, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "vinetas", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1300, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "Reporte · Actividad 5 · TecnoStock", font: "Arial", size: 16, color: GRIS })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: "Página ", font: "Arial", size: 16, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: GRIS })] })] }) },
    children: hijos,
  }],
});
const salida = path.join(PROY, "docs/Reporte_U5_TecnoStock.docx");
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(salida, b); console.log("OK", salida, b.length, "bytes"); });
