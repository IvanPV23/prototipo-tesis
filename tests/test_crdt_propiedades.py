"""P2/P4 - Propiedades algebraicas del join CRDT (Shapiro et al., 2011)."""
import itertools
import random

import pytest

from shared.crdt import (ImmutableFieldConflict, compare, counter_value, merge_clock, merge_component_maps,
                         merge_item_counter, merge_vale)


def _vale(estado="ACTIVO", proyecto="P0", pv=(1, "N0", "e0"), vv=None, cantidad=10.0, tipo="SALIDA"):
    return {"id": "V1", "codigo": "V1", "tipo": tipo, "material": "CEMENTO", "cantidad": cantidad, "unidad_medida": "BOLSA",
            "nodo_origen": "N0", "estado": estado, "proyecto": proyecto, "observacion": "",
            "field_versions": {"proyecto": list(pv), "observacion": [1, "N0", "e0"]}, "version_vector": vv or {"N0": 1}}


VARIANTES = [_vale(), _vale(estado="ANULADO", vv={"N0": 1, "A": 1}),
             _vale(proyecto="P1", pv=(2, "B", "e2"), vv={"N0": 1, "B": 1}),
             _vale(proyecto="P2", pv=(2, "C", "e3"), vv={"N0": 1, "C": 1})]


def _fold(states):
    acc = None
    for state in states:
        acc = merge_vale(acc, state)
    return acc


def test_vector_clock_relaciones_y_join():
    assert compare({"a": 1}, {"b": 1}) == "concurrent"
    assert compare({"a": 1}, {"a": 2}) == "before"
    assert compare({"a": 2, "b": 1}, {"a": 1}) == "after"
    a, b, c = {"A": 2}, {"B": 3}, {"A": 1, "C": 4}
    assert merge_clock(a, b) == merge_clock(b, a)
    assert merge_clock(merge_clock(a, b), c) == merge_clock(a, merge_clock(b, c))
    assert merge_clock(a, a) == a


def test_join_del_vale_es_conmutativo_asociativo_e_idempotente():
    reference = _fold(VARIANTES)
    for order in itertools.permutations(VARIANTES):
        assert _fold(order) == reference  # cualquier orden de entrega converge
    assert merge_vale(reference, reference) == reference
    assert reference["estado"] == "ANULADO"  # anulación monótona
    assert reference["proyecto"] == "P2"  # LWW: (2,'C') > (2,'B')


def test_pn_counter_compensa_una_sola_vez_ante_anulaciones_concurrentes():
    activo, anulado = _vale(), _vale(estado="ANULADO")
    p, n = merge_item_counter({}, {}, activo)
    assert counter_value(p, n) == -10
    for _ in range(3):  # tres nodos anulan concurrentemente: idempotente
        p, n = merge_item_counter(p, n, anulado)
    assert counter_value(p, n) == 0
    assert merge_component_maps(p, p) == p


def test_hechos_fisicos_son_inmutables():
    with pytest.raises(ImmutableFieldConflict):
        merge_vale(_vale(), _vale(cantidad=12))


def test_convergencia_aleatoria_de_saldos():
    rng = random.Random(7)
    vales = []
    for i in range(60):
        base = {**_vale(), "id": f"V{i}", "codigo": f"V{i}", "tipo": rng.choice(["SALIDA", "INGRESO"]), "cantidad": rng.randint(1, 9)}
        vales.append(base)
        if rng.random() < .3:
            vales.append({**base, "estado": "ANULADO"})
    expected = sum((1 if v["tipo"] == "INGRESO" else -1) * v["cantidad"] for v in vales
                   if not any(o["id"] == v["id"] and o["estado"] == "ANULADO" for o in vales) and v["estado"] == "ACTIVO")
    results = set()
    for _ in range(20):
        rng.shuffle(vales)
        p, n = {}, {}
        for v in vales + vales[:10]:  # entregas duplicadas incluidas
            p, n = merge_item_counter(p, n, v)
        results.add(counter_value(p, n))
    assert results == {expected}
