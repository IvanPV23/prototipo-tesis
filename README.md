# Prototipo de vales offline-first

Prototipo funcional para validar disponibilidad local, *event sourcing* y convergencia eventual.

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r client/requirements.txt
uvicorn backend.app.main:app --reload
```

En otra consola:

```powershell
python -m client.app.main crear --db .\cliente-a.db --device cliente-a --codigo V-001 --material Cemento --cantidad 10
python -m client.app.main sync --db .\cliente-a.db --device cliente-a
```

Pruebas: `pytest backend/tests client/tests`.

## Diseño validado

- SQLite local acepta escrituras sin servidor (P1); los eventos permanecen en una cola local.
- Todo cambio es un evento inmutable con UUID y reloj vectorial; reintentos son idempotentes (P3).
- El estado se fusiona mediante un join CRDT compartido: cantidad es un PN-Counter por nodo y `codigo`, `material`, `proyecto` y `estado` son registros LWW por campo. El join es conmutativo, asociativo e idempotente; nunca descarta una edición concurrente de otro campo.
- Las reglas `mayor_cantidad`/`menor_cantidad` son políticas semánticas de conciliación o de presentación, no el merge CRDT. No deben implementarse como un ganador de fila.
- El servidor serializa cada agregado con un lock por `aggregate_id`; en despliegues multi-proceso se requiere PostgreSQL y `SELECT FOR UPDATE` para el mismo aislamiento.
- `tests/lab/harness.py` ejecuta nodos SQLite reales en hilos y consolida sus métricas en una cola segura; requiere un único servidor uvicorn compartido.
- Auditoría y movimientos de inventario se construyen desde los eventos (P6).
- REST JSON desacopla cliente y núcleo (P5/P7). ABAC se ha excluido para las simulaciones solicitadas.
