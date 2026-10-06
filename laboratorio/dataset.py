"""Dataset sintético reproducible (Plan, secc. 3.1): 1,000 transacciones en 5 nodos.

* 850 vales nuevos (170 por nodo): SALIDA ~70 % / INGRESO ~30 %, concentrados en los
  materiales críticos Cemento, Arena y Acero, que todos los nodos mueven concurrentemente.
* 150 operaciones solapadas (30 por nodo) sobre 50 vales compartidos que la central emitió
  antes de la desconexión: anulaciones concurrentes, reasignaciones de proyecto y
  observaciones concurrentes (``overlap: true``).

El oráculo (estado final esperado) se calcula aquí, de forma independiente del código
CRDT del prototipo, a partir de la semántica del dominio.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DEVICES = [f"CLI-{i}" for i in range(1, 6)]
SEED_NODE = "LOGISTICA"
CATALOGO = [
    {"id": "CEMENTO", "descripcion": "Cemento Portland tipo I", "unidad_medida": "BOLSA", "stock_referencia": 5000, "critico": True},
    {"id": "ARENA", "descripcion": "Arena gruesa", "unidad_medida": "M3", "stock_referencia": 3000, "critico": True},
    {"id": "ACERO", "descripcion": "Acero corrugado 1/2\"", "unidad_medida": "VARILLA", "stock_referencia": 4000, "critico": True},
    {"id": "LADRILLO", "descripcion": "Ladrillo King Kong", "unidad_medida": "UND", "stock_referencia": 8000, "critico": False},
    {"id": "TUBO_PVC", "descripcion": "Tubo PVC 4\"", "unidad_medida": "UND", "stock_referencia": 1500, "critico": False},
    {"id": "CABLE", "descripcion": "Cable THW 14 AWG", "unidad_medida": "ROLLO", "stock_referencia": 2500, "critico": False},
]
PROYECTOS = ["PROY-A", "PROY-B", "PROY-C"]
N_EXCLUSIVOS, N_COMPARTIDOS, OPS_POR_NODO = 170, 50, 200
# Patrón de las tres operaciones concurrentes sobre cada vale compartido (g % 5).
PATRONES = [("ANULAR", "ANULAR", "OBSERVAR"), ("REASIGNAR", "REASIGNAR", "OBSERVAR"), ("OBSERVAR", "OBSERVAR", "REASIGNAR"),
            ("ANULAR", "REASIGNAR", "OBSERVAR"), ("REASIGNAR", "ANULAR", "OBSERVAR")]


def _signed(tipo: str, cantidad: float) -> float:
    return cantidad if tipo == "INGRESO" else -cantidad


def generate(seed: int) -> dict:
    rng = random.Random(seed)
    criticos = [i["id"] for i in CATALOGO if i["critico"]]
    otros = [i["id"] for i in CATALOGO if not i["critico"]]
    seed_vales = [{"vale_id": f"S-{g:03}", "tipo": "INGRESO", "material": criticos[g % 3], "cantidad": float(rng.randint(20, 60)),
                   "proyecto": PROYECTOS[g % 3]} for g in range(N_COMPARTIDOS)]
    ops = {d: [] for d in DEVICES}
    for d_index, device in enumerate(DEVICES):
        for k in range(N_EXCLUSIVOS):
            tipo = "SALIDA" if rng.random() < .7 else "INGRESO"
            material = rng.choice(criticos) if rng.random() < .75 else rng.choice(otros)
            cantidad = float(rng.randint(1, 20) if tipo == "SALIDA" else rng.randint(10, 50))
            ops[device].append({"op": "REGISTRAR", "vale_id": f"{device}-{k:03}", "tipo": tipo, "material": material,
                                "cantidad": cantidad, "proyecto": rng.choice(PROYECTOS), "overlap": False})
    for g in range(N_COMPARTIDOS):
        for offset, kind in enumerate(PATRONES[g % 5]):
            device = DEVICES[(g + offset) % 5]
            op = {"op": kind, "vale_id": f"S-{g:03}", "overlap": True}
            if kind == "REASIGNAR":
                op["proyecto"] = f"PROY-R{offset}"
            if kind == "OBSERVAR":
                op["observacion"] = f"obs {device} g{g}"
            ops[device].append(op)
    for device in DEVICES:
        exclusive = [o for o in ops[device] if not o["overlap"]]
        shared = [o for o in ops[device] if o["overlap"]]
        positions = sorted(rng.sample(range(OPS_POR_NODO), len(shared)))
        merged, it_e, it_s = [], iter(exclusive), iter(shared)
        for pos in range(OPS_POR_NODO):
            merged.append(next(it_s) if pos in positions else next(it_e))
        ops[device] = [dict(o, seq=i) for i, o in enumerate(merged)]
        assert len(ops[device]) == OPS_POR_NODO
    dataset = {"seed": seed, "catalogo": CATALOGO, "seed_vales": seed_vales, "devices": ops}
    dataset["oraculo"] = oracle(dataset)
    return dataset


def oracle(dataset: dict) -> dict:
    """Estado final esperado según la semántica de negocio (sin usar shared.crdt)."""
    stock = {i["id"]: float(i["stock_referencia"]) for i in dataset["catalogo"]}
    vales = {}
    for v in dataset["seed_vales"]:
        vales[v["vale_id"]] = {"tipo": v["tipo"], "material": v["material"], "cantidad": v["cantidad"], "estado": "ACTIVO",
                               "proyecto": v["proyecto"], "observacion": "", "nodo_origen": SEED_NODE,
                               "_writers": {"proyecto": None, "observacion": None}}
    for device, ops in dataset["devices"].items():
        for o in ops:
            if o["op"] == "REGISTRAR":
                vales[o["vale_id"]] = {"tipo": o["tipo"], "material": o["material"], "cantidad": o["cantidad"], "estado": "ACTIVO",
                                       "proyecto": o["proyecto"], "observacion": "", "nodo_origen": device,
                                       "_writers": {"proyecto": None, "observacion": None}}
    for device, ops in dataset["devices"].items():
        for o in ops:
            v = vales[o["vale_id"]]
            if o["op"] == "ANULAR":
                v["estado"] = "ANULADO"  # la anulación prevalece y es idempotente
            elif o["op"] in ("REASIGNAR", "OBSERVAR"):
                field = "proyecto" if o["op"] == "REASIGNAR" else "observacion"
                # Escrituras concurrentes del mismo nivel causal: desempate determinista por nodo.
                if v["_writers"][field] is None or device > v["_writers"][field]:
                    v["_writers"][field], v[field] = device, o[field]
    for v in vales.values():
        if v["estado"] == "ACTIVO":
            stock[v["material"]] += _signed(v["tipo"], v["cantidad"])
        v.pop("_writers")
    movimientos = len(vales) + sum(1 for v in vales.values() if v["estado"] == "ANULADO")
    return {"stocks": {k: round(s, 6) for k, s in stock.items()}, "vales": vales, "movimientos_esperados": movimientos,
            "eventos_esperados": len(dataset["seed_vales"]) + sum(len(o) for o in dataset["devices"].values())}


def write(dataset: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
