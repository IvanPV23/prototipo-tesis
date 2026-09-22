import httpx

class PostCommitDisconnectTransport(httpx.BaseTransport):
    """La primera respuesta se corta tras enviar el request al servidor.

    Reproduce el caso crítico: el servidor confirma pero el cliente desconoce la
    respuesta y reintenta el mismo lote, que debe deduplicarse por event_id.
    """
    def __init__(self):
        self.inner = httpx.HTTPTransport()
        self.calls = 0
    def handle_request(self, request):
        self.calls += 1
        response = self.inner.handle_request(request)
        if self.calls == 1:
            response.close()
            raise httpx.ReadError("corte de laboratorio post-confirmación", request=request)
        return response
    def close(self):
        self.inner.close()
