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
- Los relojes vectoriales detectan causalidad. Ante concurrencia, `CANCELADO` prevalece; si no, gana la mayor marca temporal y el dispositivo como desempate (P2/P4).
- Auditoría y movimientos de inventario se construyen desde los eventos (P6).
- REST JSON desacopla cliente y núcleo (P5/P7). ABAC se ha excluido para las simulaciones solicitadas.
