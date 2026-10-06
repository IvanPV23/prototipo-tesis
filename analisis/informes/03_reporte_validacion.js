// Documento 3 — Reporte de validación del artefacto (Fase 4: análisis y cierre).
const path = require("path");
const { ROOT, DATA, S, fmt, int, pct, pval, run, p, b, i, h1, h2, bullet, caption, note, table, figure, cover, build } = require("./comun");

const OUT = path.join(ROOT, "resultados", "03_reporte_validacion", "Reporte_validacion_artefacto.docx");
const A = DATA.ambiente, I = S.indicadores.global, T = S.tp, RS = S.resiliencia, CMP = S.comparacion;

// --- veredictos derivados de la estadística (no escritos a mano)
const okProp = (k) => I[k].pct === 100;
const okTp = ["limpia", "fallos"].every((c) => T[c].corrida.contraste_meta.rechaza_H0 && T[c].lote.contraste_meta.rechaza_H0);
const maxLote = Math.max(T.limpia.lote.max, T.fallos.lote.max);
const okTpEstricto = maxLote < S.meta.meta_lote_ms;
const okDup = RS.movimientos_duplicados_en_central === 0 && RS.eventos_duplicados_en_central === 0 && RS.lotes_recuperados.pct === 100;
const allOk = okProp("Id") && okProp("Tr") && okProp("Do") && okTp && okDup;
const si = (v) => v ? "Cumple" : "No cumple";

const children = [
  ...cover("Reporte de validación del artefacto", "Arquitectura de referencia offline-first (ARDPOL) — prototipo funcional", "Fase 4 — Análisis y cierre · Evaluación DSRM (OE5)"),

  h1("1. Resumen ejecutivo"),
  p([run("Se evaluó experimentalmente el prototipo de la arquitectura offline-first mediante "), b(`${S.meta.corridas} corridas de laboratorio`),
    run(` (30 con red limpia y 30 con cortes REST inyectados), ${int(S.meta.vales_transmitidos)} vales transmitidos desde 5 nodos de campo ejecutados como procesos paralelos y ${int(S.meta.lotes)} lotes de 100 vales. `),
    allOk ? b("El artefacto cumple las cuatro metas del plan de validación en el ambiente de laboratorio.") : b("El artefacto no cumple todas las metas del plan; ver la sección 6."),
    run(` La integridad, la trazabilidad y la disponibilidad local fueron del 100 % en todas las corridas (límite inferior del IC 95 % ≥ ${pct(Math.min(I.Id.ic95_inf_pct, I.Tr.ic95_inf_pct, I.Do.ic95_inf_pct), 3)}), y el tiempo medio por lote de 100 vales fue de ${fmt(T.limpia.lote.media, 0)} ms con red limpia y de ${fmt(T.fallos.lote.media, 0)} ms con cortes, significativamente menor que la meta de 2,500 ms (p ${pval(Math.max(T.limpia.corrida.contraste_meta.p_t_una_cola, T.fallos.corrida.contraste_meta.p_t_una_cola))}).`)]),
  caption("Tabla 1. Cumplimiento de las metas del plan (Tabla 1 del Plan de Validación)"),
  table(["Dimensión", "Indicador", "Meta", "Resultado (IC 95 %)", "Base estadística", "Veredicto"], [
    ["Integridad", "Id = conciliados sin error / transmitidos", "100 %", `${pct(I.Id.pct)} (${int(I.Id.k)}/${int(I.Id.n)}; IC inf. ${pct(I.Id.ic95_inf_pct, 3)})`, "Clopper-Pearson exacto", si(okProp("Id"))],
    ["Rendimiento", "Tp = tiempo de conciliación del lote", "< 2.5 s por lote de 100 vales",
      `Limpia ${fmt(T.limpia.lote.media, 0)} ms (lím. sup. 95 % ${fmt(T.limpia.corrida.contraste_meta.limite_sup_unilateral95_media, 0)}); con cortes ${fmt(T.fallos.lote.media, 0)} ms (lím. sup. ${fmt(T.fallos.corrida.contraste_meta.limite_sup_unilateral95_media, 0)}); máx. observado ${fmt(maxLote, 0)} ms`,
      `t unilateral y Wilcoxon (n = 30 corridas y n = 300 lotes por condición); p ${pval(Math.max(T.limpia.corrida.contraste_meta.p_t_una_cola, T.fallos.corrida.contraste_meta.p_t_una_cola))}`, si(okTp)],
    ["Trazabilidad", "Tr = movimientos con registro inmutable / total", "100 %", `${pct(I.Tr.pct)} (${int(I.Tr.k)}/${int(I.Tr.n)}; IC inf. ${pct(I.Tr.ic95_inf_pct, 3)})`, "Clopper-Pearson exacto", si(okProp("Tr"))],
    ["Operatividad", "Do = registros offline exitosos / intentos", "100 %", `${pct(I.Do.pct)} (${int(I.Do.k)}/${int(I.Do.n)}; IC inf. ${pct(I.Do.ic95_inf_pct, 3)})`, "Clopper-Pearson exacto", si(okProp("Do"))],
    ["Resiliencia (EP04)", "Duplicidad tras reintentos", "0 duplicados", `${int(RS.movimientos_duplicados_en_central)} movimientos duplicados en ${int(RS.reintentos)} reintentos; ${int(RS.lotes_recuperados.k)}/${int(RS.lotes_recuperados.n)} lotes recuperados`, "Conteo exhaustivo frente al oráculo", si(okDup)],
  ], [1.1, 1.8, 1.1, 2.6, 1.8, .9], ["L", "L", "C", "L", "L", "C"], 15),

  h1("2. Objetivo y marco de la validación"),
  p("De acuerdo con el objetivo específico OE5 y con la actividad de evaluación de la metodología DSRM (Peffers et al., 2007), se busca determinar si el artefacto —la arquitectura de referencia instanciada en un prototipo funcional— preserva la integridad transaccional, la trazabilidad y la disponibilidad operativa, con un tiempo de procesamiento aceptable, cuando varios nodos de campo operan desconectados y luego se sincronizan con la capa central. La forma de validación es la experimental técnica de laboratorio (simulación de estrés operacional) definida en el Plan de Validación."),

  h1("3. Artefacto evaluado"),
  h2("3.1 Instanciación de la arquitectura"),
  bullet([b("Capa de campo: "), "SQLite local por nodo. Cada operación (vale, saldo y evento en la cola) se confirma en una sola transacción ACID local (principio P1)."]),
  bullet([b("Capa de sincronización: "), "motor push/pull por lotes de 100 vales sobre REST (P5/P7), con reintentos con backoff exponencial y jitter. El mismo join CRDT se ejecuta en el campo y en la central."]),
  bullet([b("Motor CRDT: "), "el saldo de cada ítem es un PN-Counter cuyos componentes se indexan por movimiento; el vale es un CRDT compuesto: hechos físicos inmutables (tipo, ítem, cantidad, unidad), estado monótono ACTIVO < ANULADO (la anulación prevalece y es idempotente) y registros LWW por campo para proyecto y observación, con un sello lógico de Lamport derivado del version_vector y desempate determinista por nodo."]),
  bullet([b("Capa central: "), "event sourcing en evento_sincronizacion (append-only), movimiento_inventario y bitacora_auditoria (también append-only, con triggers SQL). Cada lote se concilia en una única transacción, de modo que un corte nunca deja un lote a medias."]),
  bullet([b("Modelo de información: "), "tablas alineadas con la Figura 7 de la tesis (actor con atributos_abac, nodo_campo, item_inventario, vale_inventario, evento_sincronizacion, movimiento_inventario, bitacora_auditoria)."]),
  h2("3.2 Depuración previa a la validación"),
  p("Antes de la campaña se revisó el código contra el marco teórico. Se corrigieron los defectos de la Tabla 2. Dentro del ciclo DSRM, esta revisión constituye una iteración de diseño-evaluación: las pruebas de laboratorio se ejecutaron sobre la versión corregida."),
  caption("Tabla 2. Defectos detectados y correcciones aplicadas"),
  table(["#", "Defecto en la versión anterior", "Riesgo para la tesis", "Corrección"], [
    ["1", "El PN-Counter vivía en la cantidad de cada vale: dos ediciones concurrentes de un mismo vale (10 y 18) daban 28.", "Saldo físico falso; contradice la secc. 4.8 y el informe de avance (PN-Counter para saldos).", "PN-Counter sobre el saldo del ítem; el vale es un documento con hechos físicos inmutables."],
    ["2", "LWW ordenado por reloj de pared del dispositivo.", "Dispositivos offline con relojes desfasados deciden mal al ganador.", "Sello lógico de Lamport derivado del version_vector + desempate por nodo y evento."],
    ["3", "Vales sin tipo SALIDA/INGRESO, sin ítem ni stock de referencia.", "No se podía verificar la invariante de la secc. 4.3.", "item_inventario, tipo y unidad; invariante Σ movimientos = saldo − referencia."],
    ["4", "En el cliente, el vale y su evento se guardaban en transacciones separadas.", "Una caída podía dejar un vale sin evento que sincronizar.", "Una sola transacción por operación."],
    ["5", "La central confirmaba (commit) evento por evento.", "Un corte a mitad del lote dejaba lotes parciales.", "Lote = una transacción ACID; escritor único serializado."],
    ["6", "/sync/bulk devolvía todo el log de eventos en cada sincronización.", "Coste O(N) que inflaba la latencia medida (EP03).", "Pull incremental /sync/changes?since=seq."],
    ["7", "El log del servidor anotaba recibido y confirmado en el mismo instante.", "Latencia del servidor sin valor de medición.", "Reloj monotónico: espera en cola, conciliación y total."],
    ["8", "Lotes de 200 vales.", "La meta del plan se define por lote de 100.", "Lotes de 100 vales."],
    ["9", "EP01 se ejecutaba con el servidor accesible.", "No probaba la desconexión real.", "Transporte sin red y sondas de conectividad cada 50 operaciones."],
    ["10", "EP04: un solo corte post-confirmación en un evento extra.", "Cobertura de fallos insuficiente (lo advertía el informe de avance).", "Tres tipos de corte en todos los lotes, con cortes dobles."],
    ["11", "Una única corrida.", "Sin base estadística.", "30 repeticiones por condición, diseño pareado."],
    ["12", "Las pruebas usaban la base central.db real.", "La prueba P7 fallaba por datos residuales.", "Base aislada por prueba; 15/15 pruebas aprobadas."],
    ["13", "Solo los eventos eran append-only.", "Movimientos y bitácora podían alterarse.", "Triggers en las tres tablas y bloqueo también en el ORM."],
    ["14", "Reglas mayor/menor cantidad declaradas sin efecto en el merge.", "Código muerto que describía una regla inexistente.", "Regla semántica explícita: inmutabilidad, anulación que prevalece y estado CONFLICTO ante hechos divergentes."],
    ["15", "La verificación no contrastaba con un estado esperado independiente.", "Una convergencia a un valor erróneo pasaba por correcta.", "Oráculo calculado desde la semántica del dataset, sin usar el código CRDT."],
  ], [.3, 2.4, 2.2, 2.4], ["C", "L", "L", "L"], 15),
  new (require("docx").Paragraph)({ spacing: { before: 120 }, children: [] }),
  p([b("Nota sobre el informe de avance (semanas 4 y 5). "), run("Ese informe interpretó los 1,001 eventos frente a 1,000 movimientos como «el evento duplicado se almacena para auditoría». La revisión de la base plan-central.db muestra que la central tenía 1,001 eventos y 1,001 movimientos: el evento adicional correspondía al vale EP04-RECOVERY creado para la prueba, y el reenvío duplicado nunca se almacenó. La conclusión de idempotencia era correcta, pero su justificación no; este reporte la sustituye con la medición de la sección 5.4.")]),

  h1("4. Ambiente y diseño experimental"),
  h2("4.1 Ambiente de pruebas"),
  table(["Componente", "Detalle"], [
    ["Hardware", `${A.procesador}; ${A.nucleos_logicos} hilos lógicos; ${A.memoria_gb} GB RAM`],
    ["Sistema operativo", A.sistema_operativo],
    ["Software", `Python ${A.python}, SQLite ${A.sqlite}, FastAPI ${A.fastapi}, Uvicorn ${A.uvicorn} (1 worker), SQLAlchemy ${A.sqlalchemy}, Pydantic ${A.pydantic}, httpx ${A.httpx}`],
    ["Topología", "1 servidor central + gateway (proceso uvicorn) y 5 nodos de campo (procesos independientes), comunicados por loopback 127.0.0.1"],
    ["Persistencia", "SQLite en modo WAL con synchronous=FULL en la central y en cada nodo"],
    ["Análisis", "Python 3.10 (pandas, SciPy, matplotlib); exportación a Jamovi/R"],
  ], [1, 3]),
  h2("4.2 Población y escenarios"),
  p("Cada corrida usó 1,000 transacciones logísticas sintéticas repartidas en 5 nodos (200 por nodo): 850 vales nuevos de salida (~70 %) e ingreso (~30 %), concentrados en los materiales críticos cemento, arena y acero, y 150 operaciones solapadas sobre 50 vales compartidos (anulaciones dobles, reasignaciones y observaciones concurrentes). Los escenarios se instrumentaron así:"),
  table(["Escenario", "Implementación", "Instrumento"], [
    ["EP01 — Registro offline", "200 operaciones por nodo con la red bloqueada en el dispositivo; sondas cada 50 operaciones.", "operaciones_offline.csv, sondas_conectividad.csv"],
    ["EP02 — Sincronización y reconciliación", "Reconexión simultánea de los 5 nodos (barrera) y transmisión de 10 lotes de 100 vales; pull y comparación de las réplicas.", "evento_sincronizacion, convergencia_nodos.csv, oráculo"],
    ["EP03 — Tiempo de respuesta", "Latencia extremo a extremo de cada lote, desde el envío hasta la confirmación de conciliación, con desglose del lado servidor.", "lotes.csv, servidor_lotes.csv"],
    ["EP04 — Resiliencia", "Cortes PRE_ENVIO, CORTE_MITAD (cuerpo JSON truncado) y POST_CONFIRMACION en cada lote; ~30 % con un segundo corte.", "intentos.csv, conteos frente al oráculo"],
  ], [1.4, 3, 1.6]),
  p("Diseño: 2 condiciones (red limpia y red con cortes) × 30 repeticiones, intercaladas en el tiempo. Cada repetición usa el mismo dataset en ambas condiciones (diseño pareado) y una central nueva con la base vacía."),

  h1("5. Resultados"),
  h2("5.1 Integridad (Id)"),
  p([run(`Los ${int(I.Id.n)} vales transmitidos se conciliaron exactamente una vez, y su estado final coincidió con el oráculo y con las 5 réplicas: Id = `), b(pct(I.Id.pct)), run(` (IC 95 % [${pct(I.Id.ic95_inf_pct, 3)}; 100 %]). Las ${int(S.convergencia.saldos_items.filas)} verificaciones de saldo por ítem cumplieron la invariante de la secc. 4.3, y las 300 réplicas finalizaron con un estado idéntico al de la central (hash SHA-256).`)]),
  h2("5.2 Rendimiento (Tp)"),
  p([run("Con red limpia, el tiempo medio por lote de 100 vales fue de "), b(`${fmt(T.limpia.lote.media, 1)} ms`), run(` (DE ${fmt(T.limpia.lote.de, 1)}; P95 ${fmt(T.limpia.lote.p95, 0)}; máx. ${fmt(T.limpia.lote.max, 0)}), equivalente a ${fmt(T.limpia.tp_ms_por_vale.media, 2)} ms por vale. Con cortes, fue de `),
    b(`${fmt(T.fallos.lote.media, 1)} ms`), run(` (DE ${fmt(T.fallos.lote.de, 1)}; P95 ${fmt(T.fallos.lote.p95, 0)}; máx. ${fmt(T.fallos.lote.max, 0)}). Usando la corrida como unidad independiente, la prueba t unilateral rechaza H0: μ ≥ 2,500 ms (limpia: t(${T.limpia.corrida.contraste_meta.gl}) = ${fmt(T.limpia.corrida.contraste_meta.t, 2)}, p ${pval(T.limpia.corrida.contraste_meta.p_t_una_cola)}; con cortes: t(${T.fallos.corrida.contraste_meta.gl}) = ${fmt(T.fallos.corrida.contraste_meta.t, 2)}, p ${pval(T.fallos.corrida.contraste_meta.p_t_una_cola)}), y la prueba de Wilcoxon lo confirma sin suponer normalidad.`)]),
  p(okTpEstricto ? `Además, ninguno de los ${int(T.limpia.lote.n + T.fallos.lote.n)} lotes superó la meta de forma individual.`
    : `Sin embargo, ${fmt(100 - T.fallos.lote.contraste_meta.bajo_meta.pct, 1)} % de los lotes con cortes superó individualmente la meta: el cumplimiento se refiere al tiempo medio, como define el plan.`),
  ...figure("f06_descomposicion_tiempo.png", "Descomposición del tiempo medio por lote", 560),
  p(`La descomposición muestra que conciliar 100 vales (join CRDT, movimientos, bitácora y commit) toma en promedio ${fmt(T.limpia.componentes_ms.conciliacion_ms.media, 0)} ms; el resto es principalmente espera en cola mientras se concilian los otros lotes que llegaron en el mismo instante, porque la central SQLite tiene un único escritor. Con cortes, el tiempo medio aumentó en ${fmt(CMP.diferencia_media_ms, 0)} ms por lote (IC 95 % [${fmt(CMP.ic95_bca_diferencia[0], 0)}; ${fmt(CMP.ic95_bca_diferencia[1], 0)}] ms; Wilcoxon pareado p ${pval(CMP.p_wilcoxon)}), un aumento atribuible a los intentos fallidos y al backoff (${fmt(RS.sobrecosto_recuperacion_ms.media, 0)} ms por lote en promedio).`),
  h2("5.3 Trazabilidad (Tr)"),
  p([run(`Los ${int(I.Tr.n)} movimientos de inventario (conciliaciones de vales y compensaciones por anulación) tienen su registro en bitacora_auditoria, vinculado por evento_id y movimiento_id, y su evento de origen en evento_sincronizacion: Tr = `), b(pct(I.Tr.pct)),
    run(` (IC 95 % inf. ${pct(I.Tr.ic95_inf_pct, 3)}). En todas las corridas, los intentos de DELETE sobre las tres tablas centrales fueron rechazados por los triggers append-only.`)]),
  h2("5.4 Operatividad (Do) y resiliencia"),
  p([run(`Los ${int(I.Do.n)} intentos de registro sin red se persistieron en el almacén local: Do = `), b(pct(I.Do.pct)),
    run(` (IC 95 % inf. ${pct(I.Do.ic95_inf_pct, 3)}), con una mediana de ${fmt(S.ep01.latencia_registro_ms.mediana, 2)} ms por registro. El ${pct(S.ep01.sondas.pct)} de las sondas confirmó la ausencia de red. En EP04 se inyectaron ${int(RS.fallas_inyectadas)} cortes (${Object.entries(RS.por_tipo).map(([k, v]) => `${k}: ${int(v)}`).join("; ")}). Los ${int(RS.lotes)} lotes afectados se confirmaron finalmente, con ${int(RS.reintentos)} reintentos; la central reconoció como duplicados ${int(RS.eventos_reconocidos_duplicados)} eventos reenviados y no almacenó ningún evento ni movimiento duplicado (tasa de duplicación por reintento: 0 %, IC 95 % sup. ${pct(RS.tasa_duplicacion_por_reintento.ic95_sup_pct, 2)}).`)]),
  ...figure("f08_indicadores_ic.png", "Indicadores de proporción frente a la meta del 100 % (IC 95 % exacto)", 560),

  h1("6. Discusión"),
  p("Los resultados aportan evidencia empírica para las preguntas de investigación: una arquitectura que trata la desconexión como un estado normal puede preservar la integridad del inventario cuando varios actores modifican información sin conexión, siempre que la convergencia se resuelva con estructuras CRDT de semántica de dominio y no con un ganador de fila. Tres decisiones de la matriz arquitectónica (Tabla 4 de la tesis) quedan respaldadas por mediciones concretas:"),
  bullet([b("CRDT frente a OT: "), `las ${fmt(S.convergencia.limpia.actualizaciones_concurrentes.media, 0)} actualizaciones concurrentes por corrida convergieron sin coordinación y en cualquier orden de llegada; las anulaciones dobles compensaron el saldo una sola vez.`]),
  bullet([b("BASE con ACID local: "), "cada nodo operó al 100 % sin red y la central nunca dejó lotes parciales, ni siquiera con el cuerpo de la petición cortado a la mitad."]),
  bullet([b("Event sourcing: "), "la bitácora inmutable permitió reconstruir y auditar el 100 % de los movimientos, y las correcciones se registran como anulación más un nuevo vale, nunca como sobrescritura."]),
  p("Frente al proceso actual basado en hojas de cálculo compartidas (Tabla 6 de la tesis), donde la concurrencia se resuelve manualmente y los registros históricos pueden modificarse sin control, el prototipo resolvió automáticamente el 100 % de los casos concurrentes del dataset y rechazó cualquier modificación de los registros históricos."),
  p(`La principal fuente de variabilidad del tiempo no es el motor CRDT sino la serialización de escrituras de la central: con red limpia, el segundo lote de cada nodo esperó más que el primero (mediana ${fmt(T.limpia.orden_lote.segundo.mediana, 0)} frente a ${fmt(T.limpia.orden_lote.primero.mediana, 0)} ms; p ${pval(T.limpia.orden_lote.p)}). El peor lote observado con cortes tardó ${fmt(T.fallos.lote.max, 0)} ms, el ${fmt(100 * T.fallos.lote.max / S.meta.meta_lote_ms, 0)} % de la meta: la media cumple con amplitud, pero el margen en el peor caso es estrecho. Por eso el margen frente a la meta se reduce cuando aumentan los nodos que reconectan a la vez, lo que motiva la recomendación de usar PostgreSQL con bloqueo por fila en producción (ver limitaciones).`),

  h1("7. Alcance"),
  bullet("Valida los mecanismos de sincronización, control transaccional, trazabilidad y disponibilidad local del proceso de vales de salida e ingreso (delimitación 1.6 de la tesis)."),
  bullet("Cubre 5 nodos concurrentes, 1,000 transacciones por corrida, reconexión masiva simultánea y tres tipos de corte REST, con 30 repeticiones por condición."),
  bullet("No evalúa usabilidad con usuarios finales, integración con un ERP/WMS real, seguridad criptográfica, costos ni retorno de inversión."),

  h1("8. Limitaciones y amenazas a la validez"),
  bullet([b("Red simulada: "), "todo el tráfico circuló por loopback en un solo equipo. Las latencias no incluyen la de redes celulares o satelitales reales; los cortes se inyectan en el transporte HTTP del cliente, no con emulación de enlace (pérdida de paquetes, ancho de banda variable)."]),
  bullet([b("Base central SQLite: "), "un escritor único y un proceso uvicorn. La serialización explica la espera en cola y no representa un despliegue multi-proceso, que requiere PostgreSQL con SELECT … FOR UPDATE."]),
  bullet([b("Dispositivos: "), "los nodos son procesos de escritorio, no teléfonos con almacenamiento flash, batería ni suspensión del sistema operativo."]),
  bullet([b("Dataset sintético: "), "1,000 operaciones con distribuciones definidas por la investigación; no son movimientos históricos de Marco Peruana. La concurrencia se concentra en 50 vales compartidos y 3 ítems críticos."]),
  bullet([b("Escala: "), "5 nodos y 10 lotes simultáneos. El comportamiento con decenas de nodos o colas de varios días no fue medido."]),
  bullet([b("Relojes: "), "cliente y central comparten el reloj del mismo equipo; las latencias se miden con un reloj monotónico del cliente, lo que evita el desfase entre relojes pero no lo representa."]),
  bullet([b("Seguridad: "), "ABAC simplificado por cabeceras, sin autenticación ni cifrado. Se verificó la autorización por rol y proyecto, no la resistencia a ataques."]),
  bullet([b("Independencia estadística: "), "los lotes de una corrida no son independientes; por eso las conclusiones se basan en la media por corrida (n = 30). Los indicadores de proporción al 100 % se informan con su límite inferior de confianza, no como certeza absoluta."]),
  bullet([b("Validez interna: "), "el oráculo y el prototipo fueron escritos por el mismo equipo. Se mitigó implementando el oráculo con reglas de negocio sin reutilizar el código CRDT."]),

  h1("9. Resultado final"),
  p([b(allOk ? "Veredicto: el artefacto se considera VALIDADO en el ambiente de laboratorio." : "Veredicto: el artefacto NO se considera validado en todas sus dimensiones.")]),
  p(`Con base en ${S.meta.corridas} corridas, ${int(S.meta.vales_transmitidos)} vales transmitidos y ${int(S.meta.lotes)} lotes, el prototipo de la arquitectura offline-first ${allOk ? "cumple" : "no cumple en su totalidad"} los criterios de éxito del Plan de Validación: integridad del 100 %, tiempo medio por lote de 100 vales significativamente inferior a 2.5 s (${fmt(T.limpia.lote.media, 0)} ms con red limpia y ${fmt(T.fallos.lote.media, 0)} ms con cortes), trazabilidad del 100 % y disponibilidad local del 100 % en desconexión, sin duplicidad de datos tras ${int(RS.reintentos)} reintentos provocados por cortes de red. Este resultado da por cumplido el OE5 dentro del alcance declarado; la validación en un despliegue productivo con dispositivos y redes reales queda como trabajo futuro, junto con la migración de la central a PostgreSQL.`),

  h1("10. Evidencias y reproducibilidad"),
  table(["Evidencia", "Ubicación"], [
    ["Código del artefacto (versión validada)", "backend/, client/, shared/"],
    ["Pruebas unitarias y funcionales P1–P8", "tests/ (resultado en resultados/01_recoleccion_en_bruto/pruebas_funcionales/)"],
    ["Laboratorio (dataset, nodos, fallas, verificación)", "laboratorio/"],
    ["Datos en bruto (Fase 3a)", "resultados/01_recoleccion_en_bruto/ (Fase3a_Recoleccion_datos_en_bruto.docx)"],
    ["Análisis estadístico (Fase 3b)", "resultados/02_analisis_estadistico/ (Fase3b_Analisis_estadistico.docx)"],
    ["Reproducir la campaña", ".venv\\Scripts\\python -m laboratorio.runner --repeticiones 30"],
    ["Reproducir la estadística", "python analisis/estadistica.py · analisis_reproducible.R en R-Studio"],
  ], [2, 3]),
];

build(OUT, "Reporte de validación del artefacto", children);
