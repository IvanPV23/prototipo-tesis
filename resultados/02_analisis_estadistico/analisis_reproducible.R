# Reproducción en R-Studio de las pruebas principales (Plan de validación, Fase 3).
# Abrir este archivo desde la carpeta resultados/02_analisis_estadistico y ejecutar.
# Solo usa R base (stats). Los mismos CSV de datos_jamovi/ pueden abrirse en Jamovi:
#   - Exploración > Descriptivos (latencia_e2e_ms agrupado por condicion)
#   - Pruebas T > Prueba T de una muestra (valor de prueba 2500, hipótesis "< valor")
#   - Pruebas T > Prueba T de muestras pareadas (pareado_por_repeticion.csv)

meta <- 2500  # ms por lote de 100 vales (Tabla 1 del plan)
lotes    <- read.csv("datos_jamovi/lotes.csv")
corridas <- read.csv("datos_jamovi/corridas.csv")
pareado  <- read.csv("datos_jamovi/pareado_por_repeticion.csv")

descr <- function(x) c(n = length(x), media = mean(x), de = sd(x), mediana = median(x),
                       p95 = unname(quantile(x, .95)), min = min(x), max = max(x))

cat("\n== Descriptivos de latencia por lote (ms) ==\n")
print(round(t(sapply(split(lotes$latencia_e2e_ms, lotes$condicion), descr)), 3))

for (cond in c("limpia", "fallos")) {
  x   <- lotes$latencia_e2e_ms[lotes$condicion == cond]
  run <- corridas$latencia_media_lote_ms[corridas$condicion == cond]
  cat("\n== Condición:", cond, "==\n")
  print(shapiro.test(x))
  cat("-- Unidad lote: H1 mu < 2500 ms --\n")
  print(t.test(x, mu = meta, alternative = "less"))
  print(wilcox.test(x, mu = meta, alternative = "less"))
  cat("-- Unidad corrida (media de 10 lotes): H1 mu < 2500 ms --\n")
  print(t.test(run, mu = meta, alternative = "less"))
}

cat("\n== Comparación pareada limpia vs fallos (por repetición) ==\n")
print(t.test(pareado$latencia_fallos_ms, pareado$latencia_limpia_ms, paired = TRUE))
print(wilcox.test(pareado$latencia_fallos_ms, pareado$latencia_limpia_ms, paired = TRUE))

cat("\n== Indicadores de proporción con IC 95 % exacto (Clopper-Pearson) ==\n")
prop <- function(k, n, nombre) { b <- binom.test(k, n); cat(sprintf("%-4s %d/%d = %.4f %%  IC95 [%.4f, %.4f] %%\n",
  nombre, k, n, 100 * k / n, 100 * b$conf.int[1], 100 * b$conf.int[2])) }
prop(sum(corridas$id_consistentes), sum(corridas$id_transmitidos), "Id")
prop(sum(corridas$tr_movimientos_trazados), sum(corridas$tr_movimientos), "Tr")
prop(sum(corridas$do_exitos), sum(corridas$do_intentos), "Do")
