from pathlib import Path
from client.app.services.vale_service import ValeService
from client.app.storage.local_db import LocalDB
from client.app.sync.sync_engine import SyncEngine


class SimulatedNode:
    """Una réplica de campo real: SQLite local, servicio y motor de sync."""
    def __init__(self, device_id: str, base_url: str, workdir: Path):
        self.device_id = device_id
        self.db = LocalDB(str(workdir / f"{device_id}.sqlite"))
        self.vales = ValeService(self.db, device_id)
        self.sync_engine = SyncEngine(self.db, device_id, base_url)

    def operate(self, vale_id: str, cantidad: float, timestamp):
        return self.vales.guardar(vale_id, vale_id, "MATERIAL-LAB", cantidad, timestamp=timestamp)

    def sync(self):
        return self.sync_engine.sync()

    def quantity(self, vale_id: str) -> float | None:
        row = self.db.get_vale(vale_id)
        return row[0].cantidad if row else None
