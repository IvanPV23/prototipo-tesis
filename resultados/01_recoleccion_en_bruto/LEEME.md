# Fase 3a — Recolección de datos en bruto

Datos tal como los emitieron los instrumentos del Plan de Validación (secc. 4), **sin resumir ni transformar**.
Generados por `laboratorio/runner.py` (ejecución) y `laboratorio/consolidar.py` (aplanado a CSV).

## Diseño de la recolección

| Elemento | Valor |
|---|---|
| Condiciones | `limpia` (EP01, EP02, EP03) y `fallos` (EP01, EP02, EP04: cortes REST inyectados) |
| Repeticiones | 30 por condición = 60 corridas, intercaladas (limpia r01, fallos r01, limpia r02, …) |
| Dataset por corrida | 1,000 transacciones = 5 nodos × 200 (850 vales nuevos + 150 operaciones solapadas sobre 50 vales compartidos) |
| Diseño pareado | La repetición *r* usa la misma semilla (`20260000 + r`) en ambas condiciones |
| Nodos | 5 procesos del sistema operativo en paralelo (`CLI-1` … `CLI-5`), cada uno con su SQLite |
| Central | 1 proceso uvicorn nuevo por corrida, con base SQLite vacía |
| Lote | 100 vales → 10 lotes por corrida, enviados de forma simultánea al reconectar |

## Archivos consolidados (una fila = un registro del instrumento)

| Archivo | Fuente (instrumento) | Filas esperadas | Contenido |
|---|---|---|---|
| `corridas.csv` | consultas de verificación (`verificacion.json`) | 60 | Conteos por corrida: Id, Tr, Do, duplicados, convergencia, reintentos |
| `lotes.csv` | log JSONL del cliente (`tipo = lote`) | 600 | Un lote confirmado: latencia extremo a extremo, tiempos del servidor, intentos, fallas |
| `intentos.csv` | log JSONL del cliente (`tipo = intento`) | ≥ 600 | Cada intento HTTP de cada lote, incluidos los cortados |
| `servidor_lotes.csv` | log JSONL del servidor | ≥ 600 | Cada lote que la central procesó (incluye reenvíos reconocidos como duplicados) |
| `operaciones_offline.csv` | log JSONL de EP01 | 60,000 | Cada intento de registro sin red con su latencia y resultado |
| `sondas_conectividad.csv` | log JSONL de EP01 | 1,200 | Sondeo de red cada 50 operaciones (debe resultar `SIN_RED`) |
| `convergencia_nodos.csv` | resultado de cada proceso nodo | 300 | Push/pull por nodo y hash del estado final de la réplica |
| `saldos_items.csv` | consultas de verificación | 360 | Saldo por ítem: referencia, esperado (oráculo), central, réplicas, invariante |
| `tablas_centrales/evento_sincronizacion.csv` | extracción directa de la tabla | 63,000 | Eventos append-only con `version_vector` y `sello_tiempo_logico` |
| `tablas_centrales/movimiento_inventario.csv` | extracción directa de la tabla | por corrida = oráculo | Movimientos conciliados y compensaciones por anulación |
| `tablas_centrales/bitacora_auditoria.csv` | extracción directa de la tabla | 63,000 | Bitácora inmutable (acción, actor, nodo, sello lógico, detalles JSON) |
| `ambiente.json` | runner | 1 | Hardware y versiones de software del laboratorio |
| `pruebas_funcionales/` | pytest | — | Evidencia de las pruebas unitarias y funcionales P1–P8 (JUnit XML y salida) |

`corridas/<condicion>_rNN/` conserva, por corrida, los artefactos originales: `central.db` (SQLite central),
`CLI-*.sqlite` (réplicas), `LOGISTICA.sqlite`, `dataset.json` (con oráculo), `cliente-*.jsonl`, `ep01-*.jsonl`,
`sondas-*.jsonl`, `servidor-lotes.jsonl`, `nodos.json`, `verificacion.json` y logs de uvicorn.

## Diccionario de las variables principales

**lotes.csv**
- `latencia_e2e_ms`: desde el primer intento de envío del lote hasta recibir la confirmación de conciliación (reloj monotónico del cliente). Base de Tp.
- `latencia_ultimo_intento_ms`: duración del intento HTTP que finalmente tuvo éxito.
- `duracion_servidor_ms` = `espera_cola_ms` + `conciliacion_ms` (+ validación): tiempo dentro de la central.
  - `espera_cola_ms`: espera por el escritor único de SQLite mientras otros lotes simultáneos se concilian.
  - `conciliacion_ms`: join CRDT, movimientos, bitácora y `COMMIT` del lote completo.
- `intentos`: intentos hasta la confirmación (1 = sin reintento). `fallas_inyectadas`: cortes aplicados, separados por `|`.
- `aplicados` / `duplicados` / `conflictos`: clasificación de los 100 eventos en la central. `duplicados = 100` indica un reenvío tras un corte post-confirmación reconocido sin efecto.

**operaciones_offline.csv**
- `op`: `REGISTRAR` (vale nuevo), `ANULAR`, `REASIGNAR` (proyecto) u `OBSERVAR` (observación). `overlap = True` indica una operación sobre un vale compartido.
- `resultado`: `EXITO` si el vale y su evento quedaron persistidos en SQLite en la misma transacción.

**corridas.csv**
- `id_consistentes` / `id_transmitidos`: vales transmitidos cuyo evento se concilió exactamente una vez y cuyo estado final coincide con el oráculo y con las 5 réplicas.
- `tr_movimientos_trazados` / `tr_movimientos`: movimientos con fila en `bitacora_auditoria` (mismo evento) y evento en `evento_sincronizacion`.
- `do_exitos` / `do_intentos`: registros sin red persistidos / intentos de registro.
- `eventos_duplicados`, `movimientos_duplicados`: exceso frente al oráculo (0 = sin duplicidad).
- `tiempo_convergencia_ms`: desde la reconexión simultánea hasta que la última réplica terminó su pull.
- `actualizaciones_concurrentes_resueltas`: eventos cuyo `version_vector` era concurrente con el estado central y se fusionaron por el CRDT.
