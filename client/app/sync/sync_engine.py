import httpx
from shared.schemas import SyncRequest
from .conflict_resolver import apply_remote

class SyncEngine:
    def __init__(self, db, device_id: str, base_url="http://127.0.0.1:8000"):
        self.db, self.device_id, self.base_url = db, device_id, base_url.rstrip("/")
    def sync(self) -> dict:
        pending = self.db.pending()
        response = httpx.post(self.base_url + "/api/v1/sync/bulk", json=SyncRequest(device_id=self.device_id, events=pending).model_dump(mode="json"), timeout=10)
        response.raise_for_status(); data = response.json()
        self.db.mark_synced(data["applied"] + data["duplicates"] + data["conflicts"])
        for raw in data["remote_events"]: apply_remote(self.db, __import__("shared.schemas", fromlist=["EventoSync"]).EventoSync.model_validate(raw))
        return data
