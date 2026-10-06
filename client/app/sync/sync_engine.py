"""Motor de sincronización diferida del nodo de campo (Fig. 5, pasos 3-9).

* push: transmite la cola local en lotes (por defecto 100 vales). Cada lote conserva su
  ``lote_id`` y sus eventos entre reintentos (backoff exponencial con jitter), por lo que
  un reintento tras un corte nunca duplica movimientos en la central.
* pull: descarga incrementalmente los eventos centrales posteriores a ``last_seq`` y los
  fusiona con el mismo join CRDT.

El motor no conoce reglas de inventario (P5): sólo transporta eventos.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from time import perf_counter

import httpx

from shared.schemas import ChangesResponse, SyncRequest
from shared.structured_log import append_jsonl

from .conflict_resolver import apply_remote


class SyncError(RuntimeError):
    pass


class SyncEngine:
    def __init__(self, db, device_id: str, base_url: str = "http://127.0.0.1:8000", transport: httpx.BaseTransport | None = None,
                 max_retries: int = 5, batch_size: int = 100, log_path=None, timeout: float = 60.0, backoff_base: float = 0.05,
                 actor_role: str = "tecnico", actor_projects: str = "*", seed: int | None = None):
        self.db, self.device_id, self.base_url = db, device_id, base_url.rstrip("/")
        self.max_retries, self.batch_size, self.log_path, self.backoff_base = max_retries, batch_size, log_path, backoff_base
        self.headers = {"x-actor-id": device_id, "x-actor-role": actor_role, "x-actor-projects": actor_projects}
        self.transport = transport
        self._random = random.Random(seed)
        self.client = httpx.Client(transport=transport, timeout=timeout, headers=self.headers)

    def close(self) -> None:
        self.client.close()

    def _log(self, record: dict) -> None:
        if self.log_path:
            append_jsonl(self.log_path, record)

    # ------------------------------------------------------------------- push
    def _send_lote(self, events) -> dict:
        request = SyncRequest(device_id=self.device_id, events=events)
        payload = request.model_dump(mode="json")
        lote_id, first_start = str(request.lote_id), perf_counter()
        for attempt in range(1, self.max_retries + 1):
            started_at, started = datetime.now(timezone.utc), perf_counter()
            record = {"tipo": "intento", "lote_id": lote_id, "device_id": self.device_id, "intento_num": attempt,
                      "n_vales": len(events), "inicio": started_at}
            try:
                response = self.client.post(self.base_url + "/api/v1/sync/bulk", json=payload)
                elapsed = round((perf_counter() - started) * 1000, 3)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
                if response.status_code != 200:  # 4xx: error del lote, no se reintenta
                    self._log(dict(record, duracion_ms=elapsed, resultado_http=response.status_code, error_tipo="HTTP_4XX",
                                   error=response.text[:300], falla_inyectada=getattr(self.transport, "last_fault", None)))
                    raise SyncError(f"lote {lote_id} rechazado: HTTP {response.status_code} {response.text[:200]}")
                data = response.json()
                self._log(dict(record, duracion_ms=elapsed, resultado_http=200, error_tipo=None, error=None,
                               falla_inyectada=getattr(self.transport, "last_fault", None)))
                break
            except httpx.HTTPError as exc:
                self._log(dict(record, duracion_ms=round((perf_counter() - started) * 1000, 3), resultado_http=None,
                               error_tipo=type(exc).__name__, error=str(exc)[:300],
                               falla_inyectada=getattr(self.transport, "last_fault", None)))
                if attempt == self.max_retries:
                    raise SyncError(f"lote {lote_id} sin confirmar tras {attempt} intentos") from exc
                delay = self.backoff_base * (2 ** (attempt - 1))
                time.sleep(delay + self._random.uniform(0, delay))
        latency = round((perf_counter() - first_start) * 1000, 3)
        self.db.mark_synced(data["applied"] + data["duplicates"] + data["conflicts"], lote_id)
        result = {"tipo": "lote", "lote_id": lote_id, "device_id": self.device_id, "n_vales": len(events),
                  "enviado_en": request.enviado_en, "confirmado_en": data["confirmado_en"], "latencia_e2e_ms": latency,
                  "latencia_ultimo_intento_ms": elapsed, "duracion_servidor_ms": data["duracion_servidor_ms"], "espera_cola_ms": data.get("espera_cola_ms"),
                  "conciliacion_ms": data.get("conciliacion_ms"), "intentos": attempt,
                  "aplicados": len(data["applied"]), "duplicados": len(data["duplicates"]), "conflictos": len(data["conflicts"])}
        self._log(result)
        return result

    def push(self) -> list[dict]:
        results = []
        while True:
            events = self.db.pending(self.batch_size)
            if not events:
                return results
            results.append(self._send_lote(events))

    # ------------------------------------------------------------------- pull
    def pull(self, limit: int = 5000) -> dict:
        since, merged, conflicts = self.db.last_seq(self.device_id), 0, 0
        started = perf_counter()
        while True:
            response = self.client.get(self.base_url + "/api/v1/sync/changes", params={"since": since, "limit": limit})
            response.raise_for_status()
            changes = ChangesResponse.model_validate(response.json())
            self.db.upsert_catalog(changes.items)
            for event in changes.events:
                outcome = apply_remote(self.db, event)
                merged += outcome == "merged"
                conflicts += outcome == "conflict"
            since = changes.last_seq
            self.db.registrar_sync(self.device_id, since)
            if len(changes.events) < limit:
                break
        return {"eventos_fusionados": merged, "conflictos": conflicts, "last_seq": since,
                "duracion_ms": round((perf_counter() - started) * 1000, 3)}

    def sync(self) -> dict:
        lotes = self.push()
        return {"lotes": lotes, "pull": self.pull()}
