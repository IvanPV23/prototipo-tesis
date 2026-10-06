// Documento 2 — Fase 3b: análisis estadístico.
const path = require("path");
const { ROOT, DATA, S, fmt, int, pct, pval, run, p, b, i, h1, h2, bullet, caption, note, table, figure, cover, build } = require("./comun");

const OUT = path.join(ROOT, "resultados", "02_analisis_estadistico", "Fase3b_Analisis_estadistico.docx");
const C = { limpia: "Red limpia", fallos: "Con cortes (EP04)" };
const T = S.tp, I = S.indicadores, CMP = S.comparacion, RS = S.resiliencia;
const decision = (h) => h.rechaza_H0 ? "Se rechaza H0" : "No se rechaza H0";

function descRow(label, x) {
  return [label, int(x.n), fmt(x.media), fmt(x.de), `[${fmt(x.ic95_media_inf)}; ${fmt(x.ic95_media_sup)}]`, fmt(x.mediana), fmt(x.riq), fmt(x.p95), fmt(x.min), fmt(x.max), fmt(x.cv_pct)];
}
const descHead = ["Grupo", "n", "Media", "DE", "IC 95 % media", "Mediana", "RIQ", "P95", "Mín.", "Máx.", "CV %"];
const descW = [2.2, .6, .9, .9, 1.6, .9, .8, .9, .8, .9, .7];
const descA = ["L", "R", "R", "R", "C", "R", "R", "R", "R", "R", "R"];

const children = [
  ...cover("Análisis estadístico de la validación", "Procesamiento de tiempos de respuesta, integridad, trazabilidad y disponibilidad", "Fase 3 — Resultados (procesamiento estadístico) · Plan de validación, semana 6"),

  h1("1. Datos de entrada y método"),
  p([run("El análisis procesa los CSV de la Fase 3a: "), b(`${S.meta.corridas} corridas`), run(`, ${int(S.meta.lotes)} lotes de 100 vales y ${int(S.meta.vales_transmitidos)} vales transmitidos. Se emplea un nivel de significación α = 0.05. El cálculo se realizó en Python (SciPy) y se acompaña del script analisis_reproducible.R y de los datos en datos_jamovi/ para replicarlo en R-Studio o Jamovi, tal como prevé el plan.`)]),
  h2("1.1 Unidades de análisis"),
  bullet([b("Lote (n = 300 por condición): "), "describe la distribución del tiempo de conciliación y su desviación estándar, que es lo que pide el plan."]),
  bullet([b("Corrida (n = 30 por condición): "), "los 10 lotes de una corrida compiten por el mismo servidor y no son independientes entre sí. Por eso las pruebas de hipótesis principales usan la media por corrida como observación independiente; el análisis por lote se informa como complemento."]),
  h2("1.2 Procedimientos"),
  bullet("Proporciones (Id, Tr, Do): estimación puntual con intervalo de confianza exacto de Clopper-Pearson al 95 %. Cuando el resultado observado es del 100 %, el límite inferior del intervalo expresa la tasa mínima compatible con los datos."),
  bullet("Tiempo por lote (Tp): descriptivos completos, IC 95 % t de Student y bootstrap BCa (10,000 remuestreos), normalidad (Shapiro-Wilk y D'Agostino K²)."),
  bullet("Contraste con la meta (< 2.5 s por lote de 100 vales): H0: μ ≥ 2,500 ms frente a H1: μ < 2,500 ms, mediante t de una muestra unilateral y Wilcoxon de rangos con signo unilateral (no paramétrico, por si falla la normalidad)."),
  bullet("Efecto de los cortes (EP04): comparación pareada por repetición (mismo dataset), con t pareada y Wilcoxon pareado; tamaño del efecto dz de Cohen. Por lote: U de Mann-Whitney y δ de Cliff."),

  h1("2. Indicadores de proporción"),
  caption("Tabla 1. Integridad, trazabilidad y disponibilidad local (todas las corridas)"),
  table(["Indicador", "Condición", "Aciertos / total", "Resultado", "IC 95 % (Clopper-Pearson)", "Meta"],
    ["Id", "Tr", "Do"].flatMap((k) => ["limpia", "fallos", "global"].map((c) => [
      { Id: "Integridad (Id)", Tr: "Trazabilidad (Tr)", Do: "Disponibilidad local (Do)" }[k], c === "global" ? "Global" : C[c],
      `${int(I[c][k].k)} / ${int(I[c][k].n)}`, pct(I[c][k].pct), `[${pct(I[c][k].ic95_inf_pct, 3)}; ${pct(I[c][k].ic95_sup_pct, 0)}]`, "100 %"])),
    [1.8, 1.4, 1.5, .9, 1.9, .6], ["L", "L", "R", "R", "C", "C"]),
  note("Id: vales transmitidos cuyo evento se concilió una sola vez y cuyo estado final coincide con el oráculo y con las 5 réplicas. Tr: movimientos con registro en la bitácora y evento de origen. Do: registros sin red persistidos / intentos de registro."),
  p([run("En las tres dimensiones no se observó ningún fallo en ninguna corrida (desviación estándar entre corridas = 0). Con el tamaño de muestra alcanzado, el límite inferior del IC 95 % para la integridad es "),
    b(pct(I.global.Id.ic95_inf_pct, 3)), run(", para la trazabilidad "), b(pct(I.global.Tr.ic95_inf_pct, 3)), run(" y para la disponibilidad local "), b(pct(I.global.Do.ic95_inf_pct, 3)),
    run(". Es decir, con un 95 % de confianza, la tasa real de error del prototipo en estas condiciones de laboratorio es inferior a "), b(pct(100 - I.global.Id.ic95_inf_pct, 3)), run(".")]),
  caption("Tabla 2. Verificaciones complementarias de consistencia"),
  table(["Verificación", "Limpia", "Con cortes"], [
    ["Réplicas convergentes con la central (hash idéntico)", `${I.limpia.convergencia_replicas.k}/${I.limpia.convergencia_replicas.n}`, `${I.fallos.convergencia_replicas.k}/${I.fallos.convergencia_replicas.n}`],
    ["Corridas sin eventos ni movimientos duplicados", `${I.limpia.corridas_sin_duplicados.k}/${I.limpia.corridas_sin_duplicados.n}`, `${I.fallos.corridas_sin_duplicados.k}/${I.fallos.corridas_sin_duplicados.n}`],
    ["Corridas con invariante Σ movimientos = saldo − referencia", `${I.limpia.corridas_invariante_saldo.k}/${I.limpia.corridas_invariante_saldo.n}`, `${I.fallos.corridas_invariante_saldo.k}/${I.fallos.corridas_invariante_saldo.n}`],
    ["Corridas con saldos iguales al oráculo en central y réplicas", `${I.limpia.corridas_saldos_igual_oraculo.k}/${I.limpia.corridas_saldos_igual_oraculo.n}`, `${I.fallos.corridas_saldos_igual_oraculo.k}/${I.fallos.corridas_saldos_igual_oraculo.n}`],
    ["Lotes confirmados", `${I.limpia.lotes_confirmados.k}/${I.limpia.lotes_confirmados.n}`, `${I.fallos.lotes_confirmados.k}/${I.fallos.lotes_confirmados.n}`],
  ], [4, 1, 1], ["L", "C", "C"]),
  ...figure("f08_indicadores_ic.png", "Integridad, trazabilidad y disponibilidad local con IC 95 % exacto"),

  h1("3. Tiempo de conciliación por lote (Tp)"),
  h2("3.1 Estadística descriptiva"),
  caption("Tabla 3. Descriptivos de la latencia extremo a extremo (ms)"),
  table(descHead, [
    descRow("Limpia — por lote", T.limpia.lote), descRow("Con cortes — por lote", T.fallos.lote),
    descRow("Limpia — media por corrida", T.limpia.corrida), descRow("Con cortes — media por corrida", T.fallos.corrida),
    descRow("Limpia — Tp por vale", T.limpia.tp_ms_por_vale), descRow("Con cortes — Tp por vale", T.fallos.tp_ms_por_vale),
  ], descW, descA, 15),
  note("DE: desviación estándar; RIQ: rango intercuartílico; P95: percentil 95; CV: coeficiente de variación. Tp por vale = latencia del lote / 100 (ms por vale)."),
  p([run("Con la red limpia, un lote de 100 vales tardó en promedio "), b(`${fmt(T.limpia.lote.media)} ms`), run(` (DE = ${fmt(T.limpia.lote.de)} ms; IC 95 % BCa de la media [${fmt(T.limpia.lote.ic95_bca_media[0])}; ${fmt(T.limpia.lote.ic95_bca_media[1])}] ms), y el peor lote observado tardó ${fmt(T.limpia.lote.max)} ms. Con cortes inyectados, la media subió a `),
    b(`${fmt(T.fallos.lote.media)} ms`), run(` (DE = ${fmt(T.fallos.lote.de)} ms), con un máximo de ${fmt(T.fallos.lote.max)} ms. La desviación estándar media de los lotes dentro de una corrida fue de ${fmt(T.limpia.de_lotes_por_corrida.media)} ms (limpia) y ${fmt(T.fallos.de_lotes_por_corrida.media)} ms (con cortes).`)]),
  ...figure("f01_histograma_latencia_lote.png", "Distribución de la latencia por lote de 100 vales, por condición"),
  ...figure("f05_ecdf_latencia.png", "Distribución acumulada (ECDF) de la latencia por lote frente a la meta"),

  h2("3.2 Normalidad"),
  caption("Tabla 4. Pruebas de normalidad"),
  table(["Serie", "n", "Shapiro-Wilk W", "p", "Asimetría", "Curtosis (exceso)", "¿Normal (α = 0.05)?"],
    [["limpia", "lote"], ["fallos", "lote"], ["limpia", "corrida"], ["fallos", "corrida"]].map(([c, u]) => [
      `${C[c]} — ${u}`, int(T[c][u].n), fmt(T[c][u].normalidad.shapiro_W, 4), pval(T[c][u].normalidad.shapiro_p), fmt(T[c][u].asimetria, 3),
      fmt(T[c][u].curtosis_exceso, 3), T[c][u].normalidad.normal_alpha05 ? "Sí" : "No"]),
    [2.4, .6, 1.1, .8, .9, 1.1, 1.2], ["L", "R", "R", "R", "R", "R", "C"]),
  p("Cuando se rechaza la normalidad, la conclusión se apoya también en la prueba de Wilcoxon y en los intervalos bootstrap, que no la presuponen. La forma de la distribución por lote refleja la cola de espera: en una reconexión simultánea, los lotes se concilian uno tras otro en el escritor único de la central, y los que llegan últimos acumulan la espera de los anteriores (ver sección 3.4)."),
  ...figure("f03_qq_normalidad.png", "Gráficos Q-Q de normalidad de la latencia por lote"),

  h2("3.3 Contraste con la meta de rendimiento"),
  caption("Tabla 5. H0: μ ≥ 2,500 ms frente a H1: μ < 2,500 ms (unilateral)"),
  table(["Condición", "Unidad", "n", "Media (ms)", "Lím. sup. 95 % (ms)", "t (gl)", "p (t)", "p (Wilcoxon)", "d de Cohen", "% lotes < meta [IC inf.]", "Decisión"],
    [["limpia", "lote"], ["limpia", "corrida"], ["fallos", "lote"], ["fallos", "corrida"]].map(([c, u]) => {
      const h = T[c][u].contraste_meta;
      return [C[c], u, int(T[c][u].n), fmt(T[c][u].media), fmt(h.limite_sup_unilateral95_media), `${fmt(h.t, 2)} (${h.gl})`, pval(h.p_t_una_cola),
        pval(h.p_wilcoxon_una_cola), fmt(h.d_cohen, 2), `${pct(h.bajo_meta.pct, 1)} [${pct(h.bajo_meta.ic95_inf_pct, 1)}]`, decision(h)];
    }), [1.2, .8, .5, .9, 1, 1, .7, .8, .7, 1.4, 1.2], ["L", "L", "R", "R", "R", "R", "R", "R", "R", "C", "L"], 14),
  p([run("En ambas condiciones y en ambas unidades de análisis se rechaza H0: el tiempo medio por lote de 100 vales es significativamente menor que 2.5 s. Con la unidad más conservadora (media por corrida), el límite superior unilateral al 95 % es "),
    b(`${fmt(T.limpia.corrida.contraste_meta.limite_sup_unilateral95_media)} ms`), run(" con red limpia y "), b(`${fmt(T.fallos.corrida.contraste_meta.limite_sup_unilateral95_media)} ms`), run(" con cortes. "),
    run(`El ${pct(T.limpia.lote.contraste_meta.bajo_meta.pct, 1)} de los lotes con red limpia y el ${pct(T.fallos.lote.contraste_meta.bajo_meta.pct, 1)} de los lotes con cortes quedaron individualmente por debajo de la meta.`)]),
  ...figure("f04_medias_por_corrida.png", "Latencia media por corrida (10 lotes) con IC 95 %"),

  h2("3.4 Composición del tiempo y efecto del orden de llegada"),
  caption("Tabla 6. Componentes medios del tiempo por lote (ms)"),
  table(["Componente", "Limpia: media", "Limpia: DE", "Con cortes: media", "Con cortes: DE"],
    [["Conciliación CRDT + commit", "conciliacion_ms"], ["Espera en cola del escritor único", "espera_cola_ms"], ["Red + serialización JSON", "red_serializacion_ms"],
      ["Reintentos (intentos fallidos + backoff)", "sobrecosto_recuperacion_ms"], ["Total dentro del servidor", "duracion_servidor_ms"]].map(([l, k]) => [
      l, fmt(T.limpia.componentes_ms[k].media), fmt(T.limpia.componentes_ms[k].de), fmt(T.fallos.componentes_ms[k].media), fmt(T.fallos.componentes_ms[k].de)]),
    [3, 1, 1, 1, 1], ["L", "R", "R", "R", "R"]),
  ...figure("f06_descomposicion_tiempo.png", "Descomposición del tiempo medio por lote"),
  p([run(`La conciliación propiamente dicha de 100 vales (join CRDT, movimientos, bitácora y commit) toma en promedio ${fmt(T.limpia.componentes_ms.conciliacion_ms.media)} ms; la mayor parte del resto es espera en cola, porque los 10 lotes llegan en el mismo instante y la central SQLite admite un solo escritor. El segundo lote de cada nodo tardó más que el primero (mediana ${fmt(T.limpia.orden_lote.segundo.mediana)} frente a ${fmt(T.limpia.orden_lote.primero.mediana)} ms con red limpia; U de Mann-Whitney, p = ${pval(T.limpia.orden_lote.p)}; δ de Cliff = ${fmt(T.limpia.orden_lote.delta_cliff, 2)}). No hubo diferencias atribuibles a un nodo en particular (Kruskal-Wallis H = ${fmt(T.limpia.por_nodo.H, 2)}, p = ${pval(T.limpia.por_nodo.p)}).`)]),
  p(`Con cortes, el efecto del orden desaparece (p = ${pval(T.fallos.orden_lote.p)}; δ de Cliff = ${fmt(T.fallos.orden_lote.delta_cliff, 2)}): los intentos fallidos y el backoff escalonan la llegada de los lotes a la central. Por la misma razón, la espera en cola y la conciliación promedio son menores en esa condición: los ${int(RS.cortes_post_confirmacion)} reenvíos de lotes ya confirmados se resuelven solo con la verificación de evento_id (100 duplicados, sin escrituras), y el tiempo adicional se traslada a los reintentos del cliente.`),
  ...figure("f02_boxplot_condicion_orden.png", "Latencia por condición y orden de envío del lote"),

  h1("4. Efecto de los cortes de red (EP04)"),
  caption("Tabla 7. Comparación pareada por repetición (mismo dataset en ambas condiciones)"),
  table(["Estadístico", "Valor"], [
    ["Pares (repeticiones)", int(CMP.pares)],
    ["Diferencia media (con cortes − limpia), ms", `${fmt(CMP.diferencia_media_ms)} (DE ${fmt(CMP.diferencia_de_ms)})`],
    ["IC 95 % BCa de la diferencia, ms", `[${fmt(CMP.ic95_bca_diferencia[0])}; ${fmt(CMP.ic95_bca_diferencia[1])}]`],
    ["t pareada; p", `${fmt(CMP.t_pareado, 3)}; ${pval(CMP.p_t_pareado)}`],
    ["Wilcoxon pareado W; p", `${fmt(CMP.wilcoxon_pareado_W, 1)}; ${pval(CMP.p_wilcoxon)}`],
    ["dz de Cohen", fmt(CMP.dz_cohen, 2)],
    ["Por lote: U de Mann-Whitney; p; δ de Cliff", `${fmt(CMP.lotes_mann_whitney_U, 0)}; ${pval(CMP.lotes_p)}; ${fmt(CMP.lotes_delta_cliff, 3)}`],
    ["Variación de la mediana por lote", pct(CMP.incremento_mediana_pct, 1)],
  ], [3, 2], ["L", "R"]),
  ...figure("f10_pareado_condiciones.png", "Comparación pareada por repetición: red limpia frente a cortes"),
  caption("Tabla 8. Resiliencia ante cortes"),
  table(["Medida", "Valor"], [
    ["Cortes inyectados (total)", int(RS.fallas_inyectadas)],
    ...Object.entries(RS.por_tipo).map(([k, v]) => [`   · ${k}`, int(v)]),
    ["Lotes afectados por al menos un corte", `${int(RS.lotes_afectados)} de ${int(RS.lotes)}`],
    ["Lotes finalmente confirmados", `${int(RS.lotes_recuperados.k)} de ${int(RS.lotes_recuperados.n)} (${pct(RS.lotes_recuperados.pct)})`],
    ["Reintentos totales", int(RS.reintentos)],
    ["Intentos por lote: media (máx.)", `${fmt(RS.intentos_por_lote.media, 2)} (${int(RS.intentos_por_lote.max)})`],
    ["Eventos reenviados reconocidos como duplicados", int(RS.eventos_reconocidos_duplicados)],
    ["Eventos duplicados almacenados en la central", int(RS.eventos_duplicados_en_central)],
    ["Movimientos duplicados en la central", int(RS.movimientos_duplicados_en_central)],
    ["Tasa de duplicación por reintento [IC 95 % sup.]", `${pct(RS.tasa_duplicacion_por_reintento.pct)} [${pct(RS.tasa_duplicacion_por_reintento.ic95_sup_pct, 2)}]`],
    ["Eventos pendientes al final", int(RS.pendientes_finales)],
    ["Sobrecosto medio de recuperación por lote, ms", fmt(RS.sobrecosto_recuperacion_ms.media)],
  ], [3, 2], ["L", "R"]),
  caption("Tabla 9. Latencia según el primer corte sufrido por el lote"),
  table(["Primer corte", "Lotes", "Media (ms)", "DE (ms)", "Mediana (ms)", "Sobrecosto medio (ms)", "Duplicados reconocidos"],
    DATA.tablas.t06_latencia_por_tipo_falla.map((r) => [r.primera_falla, int(r.lotes), fmt(r.media_ms), fmt(r.de_ms), fmt(r.mediana_ms), fmt(r.sobrecosto_medio_ms), int(r.duplicados_reconocidos)]),
    [1.6, .7, 1, 1, 1, 1.2, 1.2], ["L", "R", "R", "R", "R", "R", "R"]),
  p(`Kruskal-Wallis entre tipos de corte: H = ${fmt(RS.latencia_por_tipo_kruskal.H, 2)}, p = ${pval(RS.latencia_por_tipo_kruskal.p)}. Todos los reenvíos tras un corte post-confirmación (${int(RS.cortes_post_confirmacion)} casos) fueron reconocidos por evento_id y ninguno generó un movimiento adicional.`),
  ...figure("f07_latencia_por_intentos.png", "EP04: latencia según el número de intentos hasta la confirmación"),

  h1("5. Operación sin red (EP01)"),
  caption("Tabla 10. Latencia de registro local sin red (ms)"),
  table(descHead, DATA.tablas.t07_ep01_latencia_registro_local.map((r) => descRow(r.operacion, r)), descW, descA, 15),
  p([run(`Las ${int(S.ep01.sondas.n)} sondas de conectividad realizadas durante EP01 resultaron «SIN_RED» en el ${pct(S.ep01.sondas.pct)} de los casos, lo que confirma que los registros se hicieron efectivamente sin red. La mediana del registro local fue de `), b(`${fmt(S.ep01.latencia_registro_ms.mediana, 2)} ms`), run(` (P95 = ${fmt(S.ep01.latencia_registro_ms.p95, 2)} ms), incluida la escritura durable (synchronous=FULL) del vale, el saldo y el evento en una sola transacción.`)]),
  ...figure("f09_ep01_registro_local.png", "EP01: latencia de registro local sin red"),

  h1("6. Convergencia eventual"),
  caption("Tabla 11. Tiempo desde la reconexión simultánea hasta la convergencia de las 5 réplicas (ms)"),
  table(descHead, [descRow("Limpia — convergencia", S.convergencia.limpia.tiempo_convergencia_ms), descRow("Con cortes — convergencia", S.convergencia.fallos.tiempo_convergencia_ms),
    descRow("Limpia — fin del push", S.convergencia.limpia.tiempo_push_ms), descRow("Con cortes — fin del push", S.convergencia.fallos.tiempo_push_ms)], descW, descA, 15),
  p(`En cada corrida, el motor CRDT resolvió en promedio ${fmt(S.convergencia.limpia.actualizaciones_concurrentes.media, 0)} actualizaciones concurrentes (eventos con version_vector concurrente con el estado central: anulaciones dobles, reasignaciones y observaciones simultáneas sobre los vales compartidos) sin intervención manual, y se registraron ${int(S.convergencia.limpia.conflictos_inmutables + S.convergencia.fallos.conflictos_inmutables)} conflictos de hechos físicos. Los saldos de los ${int(S.convergencia.saldos_items.filas)} pares ítem-corrida cumplieron la invariante en ${int(S.convergencia.saldos_items.invariante_ok)} casos y coincidieron con el oráculo en ${int(S.convergencia.saldos_items.central_igual_oraculo)}.`),

  h1("7. Archivos del análisis"),
  bullet("tablas/t01 a t08: tablas de esta sección en CSV."),
  bullet("figuras/f01 a f10: figuras en PNG (150 ppp)."),
  bullet("resultados_estadisticos.json: todos los valores calculados, con la precisión completa."),
  bullet("datos_jamovi/: lotes.csv, corridas.csv y pareado_por_repeticion.csv, listos para Jamovi o R."),
  bullet("analisis_reproducible.R: reproduce en R base las pruebas de las tablas 1, 5 y 7."),
];

build(OUT, "Fase 3b — Análisis estadístico", children);
