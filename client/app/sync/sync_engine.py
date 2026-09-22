import httpx
import time
from datetime import datetime, timezone
from shared.schemas import SyncRequest
from .conflict_resolver import apply_remote
from shared.structured_log import append_jsonl

class SyncEngine:
    def __init__(self, db, device_id: str, base_url="http://127.0.0.1:8000", transport=None, max_retries=3, log_path="outputs/plan/client-sync.jsonl"):
        self.db, self.device_id, self.base_url, self.transport, self.max_retries, self.log_path = db, device_id, base_url.rstrip("/"), transport, max_retries, log_path
    def sync(self) -> dict:
        pending = self.db.pending()
        request = SyncRequest(device_id=self.device_id, events=pending)
        payload = request.model_dump(mode="json")
        error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(transport=self.transport, timeout=10) as client:
                    response = client.post(self.base_url + "/api/v1/sync/bulk", json=payload)
                response.raise_for_status(); data = response.json()
                append_jsonl(self.log_path, {"lote_id": str(request.lote_id), "device_id": self.device_id, "enviado_en": request.enviado_en, "intento_num": attempt, "resultado_http": response.status_code, "error": None, "confirmado_en": data["confirmado_en"], "n_vales": len(pending)})
                break
            except httpx.HTTPError as exc:
                error = exc
                append_jsonl(self.log_path, {"lote_id": str(request.lote_id), "device_id": self.device_id, "enviado_en": request.enviado_en, "intento_num": attempt, "resultado_http": None, "error": str(exc), "n_vales": len(pending)})
                if attempt == self.max_retries:
                    raise
                time.sleep(0.02 * (2 ** (attempt - 1)))
        else:
            raise error  # pragma: no cover
        self.db.mark_synced(data["applied"] + data["duplicates"] + data["conflicts"])
        for raw in data["remote_events"]: apply_remote(self.db, __import__("shared.schemas", fromlist=["EventoSync"]).EventoSync.model_validate(raw))
        self.db.registrar_sync(self.device_id)
        return data
