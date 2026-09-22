"""Dataset reproducible: 1,000 operaciones, cinco nodos y 15 % solapadas."""
from __future__ import annotations
import json
from pathlib import Path

DEVICES = [f"CLI-{index}" for index in range(1, 6)]

def generate(output: Path) -> dict:
    assignments = {device: [] for device in DEVICES}
    # 850 agregados exclusivos: 170 operaciones por nodo.
    for index, device in enumerate(DEVICES):
        assignments[device].extend({"aggregate_id": f"U-{index + 1}-{item:03}", "cantidad": float(item % 9 + 1), "codigo": f"U-{index + 1}-{item:03}", "material": "Cemento", "overlap": False} for item in range(170))
    # 50 agregados x tres réplicas = 150 operaciones (30 por nodo).
    for group in range(50):
        for offset in range(3):
            device = DEVICES[(group + offset) % len(DEVICES)]
            assignments[device].append({"aggregate_id": f"C-{group:03}", "cantidad": float(offset + 1), "codigo": f"C-{group:03}", "material": ("Arena", "Acero", "Cemento")[offset], "cancelar": offset == 2 and group % 5 == 0, "overlap": True})
    for device, operations in assignments.items():
        assert len(operations) == 200
        for marker in (50, 150):
            operations[marker]["fault_marker"] = True
    dataset = {"devices": assignments, "expected": {"operations": 1000, "nodes": 5, "overlap_operations": 150, "fault_markers_per_node": [50, 150]}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    return dataset

if __name__ == "__main__":
    generate(Path("outputs/plan/dataset.json"))
