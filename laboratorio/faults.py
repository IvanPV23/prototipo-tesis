"""Inyección de fallas de red controladas (EP04) y simulación de desconexión (EP01).

Tipos de corte inyectados en la transmisión REST de un lote:

* ``PRE_ENVIO``: la conexión cae antes de que el request llegue al gateway (fallo de envío
  inicial). La central no recibe nada.
* ``CORTE_MITAD``: se transmiten las cabeceras y la mitad del cuerpo JSON y el socket se
  cierra. La central recibe un request incompleto que no puede conciliar.
* ``POST_CONFIRMACION``: la central concilia y confirma el lote, pero la respuesta se pierde.
  El cliente reintenta el mismo lote; la central debe reconocerlo como duplicado.
"""
from __future__ import annotations

import json
import socket
from threading import Lock

import httpx

FAULT_TYPES = ("PRE_ENVIO", "CORTE_MITAD", "POST_CONFIRMACION")


class OfflineTransport(httpx.BaseTransport):
    """Nodo sin cobertura: toda conexión falla antes de salir del dispositivo."""
    last_fault = "SIN_RED"

    def handle_request(self, request):
        raise httpx.ConnectError("sin cobertura de red (laboratorio)", request=request)


class FaultTransport(httpx.BaseTransport):
    """Aplica un plan de fallas {ordinal_de_lote: [falla_intento_1, falla_intento_2, ...]}."""

    def __init__(self, plan: dict[int, list[str | None]] | None = None):
        self.inner = httpx.HTTPTransport()
        self.plan = plan or {}
        self.lotes: dict[str, int] = {}
        self.attempts: dict[str, int] = {}
        self.last_fault: str | None = None
        self.injected: list[dict] = []
        self._lock = Lock()

    def _fault_for(self, request) -> str | None:
        if request.method != "POST" or not request.url.path.endswith("/sync/bulk"):
            return None
        lote_id = json.loads(request.content)["lote_id"]
        with self._lock:
            ordinal = self.lotes.setdefault(lote_id, len(self.lotes))
            attempt = self.attempts[lote_id] = self.attempts.get(lote_id, 0) + 1
        faults = self.plan.get(ordinal, [])
        fault = faults[attempt - 1] if attempt <= len(faults) else None
        if fault:
            self.injected.append({"lote_id": lote_id, "ordinal": ordinal, "intento": attempt, "falla": fault})
        return fault

    def handle_request(self, request):
        request.read()
        fault = self.last_fault = self._fault_for(request)
        if fault == "PRE_ENVIO":
            raise httpx.ConnectError("corte de laboratorio previo al envío", request=request)
        if fault == "CORTE_MITAD":
            self._send_half(request)
            raise httpx.WriteError("corte de laboratorio a mitad de la transmisión", request=request)
        response = self.inner.handle_request(request)
        if fault == "POST_CONFIRMACION":
            response.read()  # la central ya confirmó (commit) antes de emitir la respuesta
            response.close()
            raise httpx.ReadError("corte de laboratorio post-confirmación", request=request)
        return response

    @staticmethod
    def _send_half(request) -> None:
        body = request.content
        host, port = request.url.host, request.url.port or 80
        headers = [f"POST {request.url.raw_path.decode()} HTTP/1.1", f"Host: {host}:{port}", "Content-Type: application/json",
                   f"Content-Length: {len(body)}"]
        headers += [f"{k}: {v}" for k, v in request.headers.items() if k.lower().startswith("x-actor")]
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode() + body[: len(body) // 2])
            sock.shutdown(socket.SHUT_RDWR)

    def close(self):
        self.inner.close()


def plan_for(device_index: int, repetition: int, n_lotes: int, rng) -> dict[int, list[str | None]]:
    """Cada lote sufre al menos un corte; ~30 % sufre un segundo corte consecutivo."""
    plan = {}
    for ordinal in range(n_lotes):
        faults = [FAULT_TYPES[(device_index + ordinal + repetition) % len(FAULT_TYPES)]]
        if rng.random() < 0.3:
            faults.append(rng.choice(FAULT_TYPES))
        plan[ordinal] = faults
    return plan
