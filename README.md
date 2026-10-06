# Prototipo ARDPOL — vales de inventario offline-first

Prototipo funcional de la arquitectura de referencia offline-first (tesis, cap. IV) para validar
disponibilidad local, convergencia CRDT, event sourcing y trazabilidad.

## Diseño aplicado

- **Capa de campo (P1):** SQLite local por nodo. Cada operación (vale + saldo + evento en la cola) se confirma en una sola transacción ACID.
- **Motor CRDT (P2/P4), en `shared/crdt.py`:**
  - El **saldo de cada ítem** es un PN-Counter con componentes indexados por movimiento (`V:<vale>` para el efecto y `A:<vale>` para la compensación). Por eso una anulación concurrente compensa una sola vez.
  - El **vale** es un CRDT compuesto. Sus hechos físicos (tipo SALIDA/INGRESO, ítem, cantidad, unidad) son inmutables: una corrección se registra como anulación más un vale nuevo. El estado es monótono (ACTIVO < ANULADO). `proyecto` y `observacion` son registros LWW por campo, ordenados por un sello de Lamport derivado del `version_vector`, con desempate por nodo.
  - Un intento de cambiar un hecho físico se registra como evento `CONFLICTO` y no altera el saldo.
- **Sincronización (P5/P7):** push en lotes de 100 vales (`POST /api/v1/sync/bulk`), idempotente por `evento_id` y atómico por lote, con reintentos y backoff exponencial con jitter. El pull es incremental (`GET /api/v1/sync/changes?since=seq`).
- **Capa central (P3/P6):** `evento_sincronizacion`, `movimiento_inventario` y `bitacora_auditoria` son append-only, con triggers SQL además del bloqueo en el ORM. Invariante verificable: Σ movimientos = saldo − stock de referencia (`GET /api/v1/items/{id}`).
- **ABAC (P8):** rol y proyectos del actor (cabeceras `x-actor-*`, sustituibles por JWT).
- La central SQLite serializa los lotes con un escritor único. En producción multi-proceso: PostgreSQL con `SELECT … FOR UPDATE`.

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r client/requirements.txt
uvicorn backend.app.main:app
```

Para el nodo de campo, ver `python -m client.app.main --help`. Pruebas: `pytest` (15 pruebas, P1–P8).

## Validación experimental (Plan EP01–EP04)

```powershell
.\.venv\Scripts\python -m laboratorio.runner --repeticiones 30        # 60 corridas, 5 nodos en procesos paralelos
.\.venv\Scripts\python -m laboratorio.consolidar resultados/01_recoleccion_en_bruto
python analisis/estadistica.py          # requiere pandas, scipy, matplotlib
python analisis/preparar_informe.py
node analisis/informes/0X_*.js          # requiere el paquete npm "docx"
```

| Carpeta | Fase | Contenido |
|---|---|---|
| `resultados/01_recoleccion_en_bruto/` | 3a — recolección | CSV en bruto, artefactos por corrida y `Fase3a_Recoleccion_datos_en_bruto.docx` |
| `resultados/02_analisis_estadistico/` | 3b — estadística | Tablas, figuras, datos para Jamovi, script R y `Fase3b_Analisis_estadistico.docx` |
| `resultados/03_reporte_validacion/` | 4 — cierre | `Reporte_validacion_artefacto.docx` |

`legado/` conserva las pruebas y el arnés de la versión anterior, que son incompatibles con el modelo corregido.
