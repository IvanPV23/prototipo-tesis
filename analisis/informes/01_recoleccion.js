// Documento 1 — Fase 3a: recolección de datos en bruto.
const path = require("path");
const { ROOT, DATA, S, fmt, int, pct, run, p, b, h1, h2, bullet, caption, note, table, cover, build } = require("./comun");

const A = DATA.ambiente;
const OUT = path.join(ROOT, "resultados", "01_recoleccion_en_bruto", "Fase3a_Recoleccion_datos_en_bruto.docx");
const tx = (v) => (v === null || v === undefined) ? "" : String(v);

const children = [
  ...cover("Recolección de datos en bruto", "Validación experimental técnica de la arquitectura offline-first", "Fase 3 — Resultados (recolección) · Plan de validación, semana 6"),

  h1("1. Propósito de la fase"),
  p("Este documento presenta los datos en bruto obtenidos al ejecutar los escenarios EP01 a EP04 del Plan de Validación Experimental Técnica. Los registros se presentan tal como los emitieron los instrumentos —logs append-only del gateway de campo y del servidor central, y extracción directa de las tablas evento_sincronizacion, movimiento_inventario y bitacora_auditoria— sin resumirlos ni interpretarlos. El procesamiento estadístico y la interpretación corresponden a la Fase 3b y al reporte de validación."),

  h1("2. Procedimiento de recolección"),
  p("Cada corrida experimental levantó un servidor central nuevo con una base SQLite vacía, sembró el catálogo de 6 ítems y 50 vales compartidos emitidos por logística, y lanzó 5 nodos de campo como procesos independientes del sistema operativo que ejecutaron en paralelo las fases siguientes, sincronizadas mediante barreras:"),
  bullet([b("Arranque en línea: "), "cada nodo descargó el catálogo y los vales compartidos."]),
  bullet([b("EP01 — registro sin red: "), "cada nodo registró 200 operaciones con la red bloqueada en el propio dispositivo; cada 50 operaciones sondeó la conectividad para confirmar que no había red."]),
  bullet([b("EP02/EP03 — reconexión simultánea: "), "los 5 nodos restablecieron la red en el mismo instante y transmitieron su cola en lotes de 100 vales."]),
  bullet([b("EP04 — cortes inyectados: "), "en la condición «fallos», cada lote sufrió al menos un corte REST (antes del envío, a mitad de la transmisión o tras la confirmación) y cerca del 30 % sufrió un segundo corte consecutivo."]),
  bullet([b("Convergencia: "), "cada nodo descargó los cambios del resto y se registró el hash de su estado final para compararlo con la central."]),
  p([run("Se realizaron "), b(`${S.meta.corridas} corridas`), run(` (30 por condición, intercaladas), con un total de ${int(S.meta.vales_transmitidos)} vales transmitidos y ${int(S.meta.lotes)} lotes. La repetición r de ambas condiciones usa el mismo dataset (semilla 20260000 + r), lo que permite una comparación pareada.`)]),

  h1("3. Ambiente de recolección"),
  table(["Componente", "Valor"], [
    ["Equipo", `${tx(A.procesador)}, ${tx(A.nucleos_logicos)} hilos lógicos, ${tx(A.memoria_gb)} GB RAM`],
    ["Sistema operativo", tx(A.sistema_operativo)],
    ["Red", tx(A.red)],
    ["Software", `Python ${A.python} · SQLite ${A.sqlite} · FastAPI ${A.fastapi} · Uvicorn ${A.uvicorn} · SQLAlchemy ${A.sqlalchemy} · Pydantic ${A.pydantic} · httpx ${A.httpx}`],
    ["Parámetros", `Lote de ${A.tamano_lote} vales · hasta ${A.max_reintentos} intentos por lote · backoff exponencial con jitter (base 50 ms)`],
  ], [1, 3]),

  h1("4. Inventario de archivos recolectados"),
  p("Los archivos se encuentran en resultados/01_recoleccion_en_bruto/. El diccionario de datos completo está en LEEME.md, en la misma carpeta."),
  caption("Tabla 1. Archivos consolidados de la recolección"),
  table(["Archivo", "Registros", "Tamaño (KB)"], DATA.inventario.map((r) => [r.archivo, int(r.filas), int(r.kb)]), [4, 1, 1], ["L", "R", "R"]),
  note("Además, corridas/<condición>_rNN/ conserva por corrida la base central (central.db), las 5 réplicas (CLI-*.sqlite), el dataset con su oráculo y los logs JSONL originales."),

  h1("5. Registro por corrida"),
  p("La Tabla 2 lista los conteos directos de cada corrida tal como los entregaron las consultas de verificación. «Do», «Id» y «Tr» se expresan como numerador/denominador (sin porcentaje: el cálculo pertenece a la fase estadística)."),
  caption("Tabla 2. Conteos en bruto por corrida"),
  table(["Corrida", "Do", "Id", "Tr", "Eventos central", "Mov. dupl.", "Réplicas conv.", "Fallas", "Reintentos", "Dupl. reconocidos", "Latencia media lote (ms)", "Conv. (ms)"],
    DATA.corridas.map((r) => [r.run_id, `${r.do_exitos}/${r.do_intentos}`, `${r.id_consistentes}/${r.id_transmitidos}`,
      `${r.tr_movimientos_trazados}/${r.tr_movimientos}`, int(r.eventos_central), int(r.movimientos_duplicados), `${r.replicas_convergentes}/5`,
      int(r.fallas_inyectadas), int(r.reintentos), int(r.duplicados_detectados), fmt(r.lat_media, 1), fmt(r.tiempo_convergencia_ms, 0)]),
    [1.5, 1.2, 1.2, 1.1, 1, .8, .8, .7, .9, 1, 1.1, .9], ["L", "C", "C", "C", "R", "R", "C", "R", "R", "R", "R", "R"], 14),

  h1("6. Muestras de registros en bruto"),
  h2("6.1 Operaciones offline (EP01)"),
  caption("Tabla 3. Primeros registros de operaciones_offline.csv"),
  table(["Corrida", "Nodo", "Seq", "Operación", "Vale", "Solapada", "Latencia (ms)", "Resultado"],
    DATA.muestra_ops.map((r) => [r.run_id, r.device_id, r.seq, r.op, r.vale_id, r.overlap ? "sí" : "no", fmt(r.latencia_ms, 3), r.resultado]),
    [1.3, .8, .5, 1.1, 1.1, .8, 1, 1], ["L", "L", "R", "L", "L", "C", "R", "L"]),
  h2("6.2 Intentos de transmisión con cortes (EP04)"),
  caption("Tabla 4. Primeros registros de intentos.csv en la condición «fallos»"),
  table(["Corrida", "Nodo", "Intento", "Duración (ms)", "HTTP", "Error", "Falla inyectada"],
    DATA.muestra_intentos.map((r) => [r.run_id, r.device_id, r.intento_num, fmt(r.duracion_ms, 1), r.resultado_http === "" ? "—" : int(r.resultado_http), r.error_tipo || "—", r.falla_inyectada || "—"]),
    [1.3, .8, .7, 1, .7, 1.2, 1.5], ["L", "L", "R", "R", "C", "L", "L"]),
  h2("6.3 Lotes confirmados"),
  caption("Tabla 5. Primeros registros de lotes.csv en la condición «fallos»"),
  table(["Corrida", "Nodo", "Lote", "E2E (ms)", "Servidor (ms)", "Cola (ms)", "Conciliación (ms)", "Intentos", "Fallas", "Aplic.", "Dupl."],
    DATA.muestra_lotes.map((r) => [r.run_id, r.device_id, r.lote_ordinal + 1, fmt(r.latencia_e2e_ms), fmt(r.duracion_servidor_ms), fmt(r.espera_cola_ms),
      fmt(r.conciliacion_ms), r.intentos, r.fallas_inyectadas || "—", r.aplicados, r.duplicados]),
    [1.2, .7, .5, .9, .9, .8, 1, .7, 2, .6, .6], ["L", "L", "C", "R", "R", "R", "R", "C", "L", "R", "R"], 15),
  h2("6.4 Eventos y bitácora de un vale compartido"),
  caption("Tabla 6. evento_sincronizacion: operaciones concurrentes sobre vales compartidos"),
  table(["Corrida", "Seq", "Vale", "Tipo de evento", "Nodo", "Sello lógico", "Estado", "version_vector"],
    DATA.muestra_eventos.map((r) => [r.run_id, r.seq, r.vale_id, r.tipo_evento, r.nodo_origen_id, r.sello_tiempo_logico, r.estado, r.version_vector]),
    [1.2, .5, .7, 1.3, .9, .6, .8, 2.2], ["L", "R", "L", "L", "L", "R", "L", "L"], 15),
  caption("Tabla 7. bitacora_auditoria de los mismos vales"),
  table(["Corrida", "Vale", "Acción", "Nodo", "Sello lógico", "Movimiento", "Detalles"],
    DATA.muestra_bitacora.map((r) => [r.run_id, r.vale_id, r.accion, r.nodo_id, r.sello_logico, r.movimiento_id === "" ? "—" : int(r.movimiento_id), r.detalles]),
    [1.1, .6, 1, .8, .6, .7, 4], ["L", "L", "L", "L", "R", "R", "L"], 14),
  note("Los valores de version_vector y detalles se transcriben literalmente (JSON) desde la base central de la corrida."),

  h1("7. Integridad del proceso de recolección"),
  bullet(`Todas las corridas planificadas finalizaron: ${S.meta.corridas} de 60.`),
  bullet("Ningún registro fue editado a mano: los CSV se regeneran íntegramente con «python -m laboratorio.consolidar»."),
  bullet("Las tablas centrales son append-only también a nivel SQL (triggers): la extracción no pudo alterar los datos."),
  bullet("Las pruebas funcionales del artefacto (P1–P8) se ejecutaron sobre la misma versión del código; su evidencia está en pruebas_funcionales/."),
];

build(OUT, "Fase 3a — Recolección de datos en bruto", children);
