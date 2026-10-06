"""Reúne en un JSON los datos que los informes .docx citan (tablas, muestras e inventario)."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "resultados" / "01_recoleccion_en_bruto"
STATS = ROOT / "resultados" / "02_analisis_estadistico"


def rows(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def main() -> None:
    corridas = pd.read_csv(RAW / "corridas.csv")
    lotes = pd.read_csv(RAW / "lotes.csv")
    ops = pd.read_csv(RAW / "operaciones_offline.csv")
    eventos = pd.read_csv(RAW / "tablas_centrales" / "evento_sincronizacion.csv", nrows=2000)
    bitacora = pd.read_csv(RAW / "tablas_centrales" / "bitacora_auditoria.csv", nrows=3000)
    intentos = pd.read_csv(RAW / "intentos.csv")
    inventario = []
    for path in sorted(list(RAW.glob("*.csv")) + list((RAW / "tablas_centrales").glob("*.csv"))):
        with path.open(encoding="utf-8") as f:
            n = sum(1 for _ in f) - 1
        inventario.append({"archivo": str(path.relative_to(RAW)).replace("\\", "/"), "filas": n, "kb": round(path.stat().st_size / 1024)})
    lat = lotes.groupby("run_id").agg(lat_media=("latencia_e2e_ms", "mean"), lat_de=("latencia_e2e_ms", "std"), lat_max=("latencia_e2e_ms", "max"))
    resumen = corridas.merge(lat, left_on="run_id", right_index=True).sort_values(["repeticion", "condicion"], ascending=[True, False])
    shared = eventos[eventos.vale_id.str.startswith("S-")].head(6)
    data = {
        "ambiente": json.loads((RAW / "ambiente.json").read_text(encoding="utf-8")),
        "estadistica": json.loads((STATS / "resultados_estadisticos.json").read_text(encoding="utf-8")),
        "inventario": inventario,
        "corridas": rows(resumen[["run_id", "condicion", "repeticion", "do_exitos", "do_intentos", "id_consistentes", "id_transmitidos",
                                  "tr_movimientos_trazados", "tr_movimientos", "eventos_central", "movimientos_duplicados", "replicas_convergentes",
                                  "fallas_inyectadas", "reintentos", "duplicados_detectados", "tiempo_convergencia_ms", "lat_media", "lat_de", "lat_max"]]),
        "muestra_lotes": rows(lotes[lotes.condicion == "fallos"].head(10)[["run_id", "device_id", "lote_ordinal", "latencia_e2e_ms", "duracion_servidor_ms",
                                                                        "espera_cola_ms", "conciliacion_ms", "intentos", "fallas_inyectadas", "aplicados", "duplicados"]].fillna("")),
        "muestra_intentos": rows(intentos[(intentos.condicion == "fallos")].head(8)[["run_id", "device_id", "intento_num", "duracion_ms", "resultado_http",
                                                                                     "error_tipo", "falla_inyectada"]].fillna("")),
        "muestra_ops": rows(ops.head(6)[["run_id", "device_id", "seq", "op", "vale_id", "overlap", "latencia_ms", "resultado"]]),
        "muestra_eventos": rows(shared[["run_id", "seq", "vale_id", "tipo_evento", "nodo_origen_id", "sello_tiempo_logico", "estado", "version_vector"]]),
        "muestra_bitacora": rows(bitacora[bitacora.vale_id.isin(shared.vale_id)].head(6)[["run_id", "vale_id", "accion", "nodo_id", "sello_logico",
                                                                                         "movimiento_id", "detalles"]].fillna("")),
        "tablas": {name: rows(pd.read_csv(p)) for name, p in ((p.stem, p) for p in sorted((STATS / "tablas").glob("*.csv")))},
    }
    (STATS / "datos_informe.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", len(data["corridas"]), "corridas")


if __name__ == "__main__":
    main()
