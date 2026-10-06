"""Arnés multihilo; el servidor debe ser una única instancia uvicorn real."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from random import Random
from pathlib import Path
import httpx

from tests.simulation import ConstructionClock
from .node_simulator import SimulatedNode


def run_concurrent_lab(base_url: str, workspace: Path, nodes: int = 4, operations: int = 10, vale_id: str = "LAB-001") -> dict:
    """Ejecuta operaciones reales concurrentes y consolida métricas fuera de workers."""
    workspace.mkdir(parents=True, exist_ok=True)
    metrics: Queue = Queue()

    def worker(index: int):
        node = SimulatedNode(f"LAB-{index}", base_url, workspace)
        clock, randomizer = ConstructionClock(seed=20260712 + index), Random(index)
        for operation in range(operations):
            instant, _ = clock.next_event()
            # Cantidad objetivo local: ValeService la traduce a componente PN del nodo.
            node.operate(vale_id, operation + 1 + index, instant)
            if randomizer.random() < .45:
                node.sync()
        node.sync()
        metrics.put({"node": node.device_id, "operations": operations})
        return node

    with ThreadPoolExecutor(max_workers=nodes, thread_name_prefix="campo") as executor:
        replicas = list(executor.map(worker, range(nodes)))
    # La sincronización final tras la carrera es la aserción de convergencia central.
    for replica in replicas:
        replica.sync()
    results = [metrics.get() for _ in range(nodes)]
    quantities = [replica.quantity(vale_id) for replica in replicas]
    server_quantity = httpx.get(f"{base_url.rstrip('/')}/api/v1/vales/{vale_id}", timeout=10).json()["cantidad"]
    assert len(set(quantities + [server_quantity])) == 1, f"réplicas/servidor no convergieron: {quantities}, {server_quantity}"
    for result, quantity in zip(results, quantities):
        result["quantity_after_final_sync"] = quantity
    return {"nodes": results, "replica_quantity": quantities[0], "server_quantity": server_quantity, "consistent_replicas": len(quantities)}
