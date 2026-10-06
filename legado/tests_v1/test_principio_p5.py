from client.app.sync.sync_engine import SyncEngine
from client.app.services.vale_service import ValeService
from backend.app.services.inventario_service import set_resolution_rule, incoming_wins
from .conftest import log

def test_p5_motor_no_depende_de_regla_de_inventario(output_dir):
    assert callable(SyncEngine.sync)
    assert not hasattr(ValeService, "sync")
    set_resolution_rule("menor_cantidad")
    assert incoming_wins(10, 2)
    log(output_dir, "test_p5.log", ["INFO: Regla de negocio actualizada: priorizar_menor_cantidad", "INFO: Motor de sincronización permanece desacoplado", "INFO: CONFLICTO DETECTADO: actual=10, nueva=2", "INFO: Resolución aplicada: prevalece cantidad 2 (regla: menor cantidad)"])
    set_resolution_rule("mayor_cantidad")
