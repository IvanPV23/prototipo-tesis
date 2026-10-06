"""Fase 3b - Procesamiento estadístico de los datos en bruto.

Lee los CSV de resultados/01_recoleccion_en_bruto y produce en resultados/02_analisis_estadistico:
  tablas/*.csv, figuras/*.png, resultados_estadisticos.json y datos_jamovi/*.csv

Unidad de análisis:
  * lote (n = 300 por condición): distribución de tiempos, desviación estándar de los lotes;
  * corrida (n = 30 por condición): unidad independiente para las pruebas de hipótesis, porque
    los 10 lotes de una corrida comparten servidor y compiten por él (no son independientes).

Ejecutar con un Python que tenga pandas, scipy, matplotlib:  python analisis/estadistica.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "resultados" / "01_recoleccion_en_bruto"
OUT = ROOT / "resultados" / "02_analisis_estadistico"
META_LOTE_MS = 2500.0  # Plan, Tabla 1: < 2.5 s por lote de 100 vales
ALPHA = 0.05
RNG = np.random.default_rng(20261006)
COND = {"limpia": "Red limpia (EP02/EP03)", "fallos": "Cortes inyectados (EP04)"}
COLOR = {"limpia": "#2a78d6", "fallos": "#eb6834"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .6,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150, "savefig.bbox": "tight",
                     "legend.frameon": False, "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 10})


# ------------------------------------------------------------------ utilidades
def describe(x) -> dict:
    x = np.asarray(x, dtype=float)
    n = len(x)
    mean, sd = x.mean(), x.std(ddof=1) if n > 1 else 0.0
    se = sd / np.sqrt(n) if n > 1 else 0.0
    tcrit = stats.t.ppf(1 - ALPHA / 2, n - 1) if n > 1 else np.nan
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    return {"n": n, "media": mean, "de": sd, "ee": se, "ic95_media_inf": mean - tcrit * se, "ic95_media_sup": mean + tcrit * se,
            "cv_pct": 100 * sd / mean if mean else np.nan, "min": x.min(), "q1": q1, "mediana": med, "q3": q3, "riq": q3 - q1,
            "p90": np.percentile(x, 90), "p95": np.percentile(x, 95), "p99": np.percentile(x, 99), "max": x.max(),
            "asimetria": stats.skew(x) if n > 2 else np.nan, "curtosis_exceso": stats.kurtosis(x) if n > 3 else np.nan}


def bootstrap_ci(x, statistic=np.mean) -> tuple[float, float]:
    res = stats.bootstrap((np.asarray(x, float),), statistic, n_resamples=10000, confidence_level=0.95, method="BCa", random_state=RNG)
    return float(res.confidence_interval.low), float(res.confidence_interval.high)


def proportion(k: int, n: int) -> dict:
    ci = stats.binomtest(int(k), int(n)).proportion_ci(confidence_level=0.95, method="exact")
    return {"k": int(k), "n": int(n), "pct": 100 * k / n, "ic95_inf_pct": 100 * ci.low, "ic95_sup_pct": 100 * ci.high}


def normality(x) -> dict:
    x = np.asarray(x, float)
    sw = stats.shapiro(x)
    out = {"shapiro_W": sw.statistic, "shapiro_p": sw.pvalue, "normal_alpha05": bool(sw.pvalue >= ALPHA)}
    if len(x) >= 20:
        k2 = stats.normaltest(x)
        out.update({"dagostino_K2": k2.statistic, "dagostino_p": k2.pvalue})
    return out


def vs_goal(x, goal: float) -> dict:
    """H0: mu >= meta ; H1: mu < meta (una cola)."""
    x = np.asarray(x, float)
    t = stats.ttest_1samp(x, goal, alternative="less")
    w = stats.wilcoxon(x - goal, alternative="less")
    sd = x.std(ddof=1)
    tcrit = stats.t.ppf(1 - ALPHA, len(x) - 1)
    return {"meta_ms": goal, "t": t.statistic, "gl": len(x) - 1, "p_t_una_cola": t.pvalue,
            "limite_sup_unilateral95_media": x.mean() + tcrit * sd / np.sqrt(len(x)),
            "wilcoxon_W": w.statistic, "p_wilcoxon_una_cola": w.pvalue, "d_cohen": (x.mean() - goal) / sd,
            "bajo_meta": proportion((x < goal).sum(), len(x)), "rechaza_H0": bool(t.pvalue < ALPHA and w.pvalue < ALPHA)}


def cliffs_delta(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    greater = (a[:, None] > b[None, :]).sum()
    less = (a[:, None] < b[None, :]).sum()
    return (greater - less) / (len(a) * len(b))


def es(v, dec=0) -> str:
    """Formato del plan de validación (es-PE): coma de miles y punto decimal."""
    return f"{v:,.{dec}f}"


def save(fig, name: str) -> str:
    path = OUT / "figuras" / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path.name


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if np.isnan(obj) else round(float(obj), 6)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


# ------------------------------------------------------------------ análisis
def main() -> None:
    for sub in ("tablas", "figuras", "datos_jamovi"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    corridas = pd.read_csv(RAW / "corridas.csv")
    lotes = pd.read_csv(RAW / "lotes.csv")
    ops = pd.read_csv(RAW / "operaciones_offline.csv")
    sondas = pd.read_csv(RAW / "sondas_conectividad.csv")
    nodos = pd.read_csv(RAW / "convergencia_nodos.csv")
    intentos = pd.read_csv(RAW / "intentos.csv")
    saldos = pd.read_csv(RAW / "saldos_items.csv")
    lotes["tp_ms_por_vale"] = lotes["latencia_e2e_ms"] / lotes["n_vales"]
    lotes["red_serializacion_ms"] = lotes["latencia_ultimo_intento_ms"] - lotes["duracion_servidor_ms"]
    lotes["sobrecosto_recuperacion_ms"] = lotes["latencia_e2e_ms"] - lotes["latencia_ultimo_intento_ms"]
    lotes["fallas_inyectadas"] = lotes["fallas_inyectadas"].fillna("")
    lotes["n_fallas"] = lotes["fallas_inyectadas"].apply(lambda s: 0 if not s else len(s.split("|")))
    R: dict = {"meta": {"meta_lote_ms": META_LOTE_MS, "alpha": ALPHA, "corridas": int(len(corridas)),
                        "corridas_por_condicion": corridas.groupby("condicion").size().to_dict(), "lotes": int(len(lotes)),
                        "vales_transmitidos": int(corridas["id_transmitidos"].sum())}}

    # ---------------- 1. Indicadores de proporción (Id, Tr, Do) ----------------
    ind_rows = []
    R["indicadores"] = {}
    for cond in ["limpia", "fallos", "global"]:
        c = corridas if cond == "global" else corridas[corridas.condicion == cond]
        block = {
            "Id": proportion(c.id_consistentes.sum(), c.id_transmitidos.sum()),
            "Tr": proportion(c.tr_movimientos_trazados.sum(), c.tr_movimientos.sum()),
            "Do": proportion(c.do_exitos.sum(), c.do_intentos.sum()),
            "convergencia_replicas": proportion(c.replicas_convergentes.sum(), 5 * len(c)),
            "corridas_sin_duplicados": proportion(((c.eventos_duplicados == 0) & (c.movimientos_duplicados == 0)).sum(), len(c)),
            "corridas_invariante_saldo": proportion(c.invariante_items_ok.sum(), len(c)),
            "corridas_saldos_igual_oraculo": proportion(c.saldos_iguales_oraculo.sum(), len(c)),
            "lotes_confirmados": proportion(c.lotes_confirmados.sum(), c.lotes.sum()),
        }
        for name in ("Id", "Tr", "Do"):
            per_run = c[{"Id": "id_pct", "Tr": "tr_pct", "Do": "do_pct"}[name]]
            block[name]["por_corrida_min_pct"], block[name]["por_corrida_max_pct"] = per_run.min(), per_run.max()
            block[name]["por_corrida_de"] = per_run.std(ddof=1)
        R["indicadores"][cond] = block
        for name, v in block.items():
            ind_rows.append({"condicion": cond, "indicador": name, **{k: v[k] for k in ("k", "n", "pct", "ic95_inf_pct", "ic95_sup_pct")}})
    pd.DataFrame(ind_rows).to_csv(OUT / "tablas" / "t01_indicadores_proporcion.csv", index=False)

    # ---------------- 2. Tp: tiempo por lote de 100 vales ----------------
    R["tp"] = {}
    desc_rows, run_level = [], {}
    for cond in ["limpia", "fallos"]:
        lc = lotes[lotes.condicion == cond]
        x = lc.latencia_e2e_ms.to_numpy()
        per_run = lc.groupby("repeticion").latencia_e2e_ms.mean()
        run_level[cond] = per_run
        block = {
            "lote": {**describe(x), "ic95_bca_media": bootstrap_ci(x), "ic95_bca_mediana": bootstrap_ci(x, np.median),
                     "normalidad": normality(x), "contraste_meta": vs_goal(x, META_LOTE_MS)},
            "corrida": {**describe(per_run), "ic95_bca_media": bootstrap_ci(per_run), "normalidad": normality(per_run),
                        "contraste_meta": vs_goal(per_run, META_LOTE_MS)},
            "tp_ms_por_vale": describe(lc.tp_ms_por_vale),
            "componentes_ms": {k: describe(lc[k]) for k in ("espera_cola_ms", "conciliacion_ms", "red_serializacion_ms",
                                                              "sobrecosto_recuperacion_ms", "duracion_servidor_ms")},
            "max_lote_por_corrida": describe(lc.groupby("repeticion").latencia_e2e_ms.max()),
            "de_lotes_por_corrida": describe(lc.groupby("repeticion").latencia_e2e_ms.std(ddof=1)),
        }
        # Orden de llegada: 1.º vs 2.º lote de cada nodo (cola en reconexión masiva)
        a, b = lc[lc.lote_ordinal == 0].latencia_e2e_ms, lc[lc.lote_ordinal == 1].latencia_e2e_ms
        mw = stats.mannwhitneyu(a, b)
        block["orden_lote"] = {"primero": describe(a), "segundo": describe(b), "U": mw.statistic, "p": mw.pvalue, "delta_cliff": cliffs_delta(a, b)}
        kw = stats.kruskal(*[g.latencia_e2e_ms for _, g in lc.groupby("device_id")])
        block["por_nodo"] = {"H": kw.statistic, "p": kw.pvalue,
                             "medianas": lc.groupby("device_id").latencia_e2e_ms.median().to_dict()}
        R["tp"][cond] = block
        for unit, src in (("lote", x), ("corrida (media de 10 lotes)", per_run)):
            desc_rows.append({"condicion": cond, "unidad": unit, **{k: v for k, v in describe(src).items()}})
        desc_rows.append({"condicion": cond, "unidad": "Tp por vale (ms/vale)", **describe(lc.tp_ms_por_vale)})
    pd.DataFrame(desc_rows).to_csv(OUT / "tablas" / "t02_descriptivos_tiempo_lote.csv", index=False)

    hyp = []
    for cond in ["limpia", "fallos"]:
        for unit in ("lote", "corrida"):
            h = R["tp"][cond][unit]["contraste_meta"]
            hyp.append({"condicion": cond, "unidad": unit, "n": R["tp"][cond][unit]["n"], "media_ms": R["tp"][cond][unit]["media"],
                        "limite_sup_95_ms": h["limite_sup_unilateral95_media"], "t": h["t"], "gl": h["gl"], "p_t": h["p_t_una_cola"],
                        "wilcoxon_W": h["wilcoxon_W"], "p_wilcoxon": h["p_wilcoxon_una_cola"], "d_cohen": h["d_cohen"],
                        "pct_bajo_meta": h["bajo_meta"]["pct"], "ic95_inf_pct_bajo_meta": h["bajo_meta"]["ic95_inf_pct"],
                        "shapiro_W": R["tp"][cond][unit]["normalidad"]["shapiro_W"], "shapiro_p": R["tp"][cond][unit]["normalidad"]["shapiro_p"],
                        "decision": "Se rechaza H0 (μ ≥ 2.5 s)" if h["rechaza_H0"] else "No se rechaza H0"})
    pd.DataFrame(hyp).to_csv(OUT / "tablas" / "t03_contraste_meta_tp.csv", index=False)

    # ---------------- 3. Comparación limpia vs fallos (diseño pareado por repetición) ----------------
    paired = pd.concat(run_level, axis=1).dropna()
    diff = paired["fallos"] - paired["limpia"]
    wil = stats.wilcoxon(paired["fallos"], paired["limpia"])
    tt = stats.ttest_rel(paired["fallos"], paired["limpia"])
    la, lf = lotes[lotes.condicion == "limpia"].latencia_e2e_ms, lotes[lotes.condicion == "fallos"].latencia_e2e_ms
    mw = stats.mannwhitneyu(lf, la)
    R["comparacion"] = {"pares": int(len(paired)), "diferencia_media_ms": diff.mean(), "diferencia_de_ms": diff.std(ddof=1),
                        "ic95_bca_diferencia": bootstrap_ci(diff), "wilcoxon_pareado_W": wil.statistic, "p_wilcoxon": wil.pvalue,
                        "t_pareado": tt.statistic, "p_t_pareado": tt.pvalue, "dz_cohen": diff.mean() / diff.std(ddof=1),
                        "normalidad_diferencias": normality(diff),
                        "lotes_mann_whitney_U": mw.statistic, "lotes_p": mw.pvalue, "lotes_delta_cliff": cliffs_delta(lf, la),
                        "incremento_mediana_pct": 100 * (lf.median() / la.median() - 1)}
    pd.DataFrame([R["comparacion"]]).drop(columns=["normalidad_diferencias"]).to_csv(OUT / "tablas" / "t04_comparacion_condiciones.csv", index=False)

    # ---------------- 4. Resiliencia (EP04) ----------------
    lf_df = lotes[lotes.condicion == "fallos"].copy()
    fallas_tipo = intentos[(intentos.condicion == "fallos") & intentos.falla_inyectada.notna() & (intentos.resultado_http.isna())]
    by_intentos = lf_df.groupby("intentos").latencia_e2e_ms.agg(["count", "mean", "std", "median"]).reset_index()
    lf_df["primera_falla"] = lf_df.fallas_inyectadas.str.split("|").str[0]
    by_tipo = lf_df.groupby("primera_falla").agg(lotes=("latencia_e2e_ms", "size"), media_ms=("latencia_e2e_ms", "mean"),
                                                 de_ms=("latencia_e2e_ms", "std"), mediana_ms=("latencia_e2e_ms", "median"),
                                                 sobrecosto_medio_ms=("sobrecosto_recuperacion_ms", "mean"),
                                                 duplicados_reconocidos=("duplicados", "sum")).reset_index()
    kw = stats.kruskal(*[g.latencia_e2e_ms for _, g in lf_df.groupby("primera_falla")])
    post_commit = int((fallas_tipo.falla_inyectada == "POST_CONFIRMACION").sum())
    cf = corridas[corridas.condicion == "fallos"]
    R["resiliencia"] = {
        "fallas_inyectadas": int(len(fallas_tipo)), "por_tipo": fallas_tipo.falla_inyectada.value_counts().to_dict(),
        "lotes_afectados": int((lf_df.n_fallas > 0).sum()), "lotes": int(len(lf_df)),
        "lotes_recuperados": proportion(int(cf.lotes_confirmados.sum()), int(cf.lotes.sum())),
        "reintentos": int(cf.reintentos.sum()), "intentos_por_lote": describe(lf_df.intentos),
        "eventos_reconocidos_duplicados": int(lf_df.duplicados.sum()),
        "cortes_post_confirmacion": post_commit,
        "movimientos_duplicados_en_central": int(corridas.movimientos_duplicados.sum()),
        "eventos_duplicados_en_central": int(corridas.eventos_duplicados.sum()),
        "tasa_duplicacion_por_reintento": proportion(int(corridas.movimientos_duplicados.clip(lower=0).sum()), int(cf.reintentos.sum())),
        "pendientes_finales": int(corridas.pendientes_finales.sum()),
        "latencia_por_tipo_kruskal": {"H": kw.statistic, "p": kw.pvalue}, "sobrecosto_recuperacion_ms": describe(lf_df.sobrecosto_recuperacion_ms),
    }
    by_intentos.to_csv(OUT / "tablas" / "t05_latencia_por_intentos.csv", index=False)
    by_tipo.to_csv(OUT / "tablas" / "t06_latencia_por_tipo_falla.csv", index=False)

    # ---------------- 5. EP01: operación sin red ----------------
    R["ep01"] = {"latencia_registro_ms": describe(ops.latencia_ms), "por_operacion": {k: describe(g.latencia_ms) for k, g in ops.groupby("op")},
                 "ic95_bca_media": bootstrap_ci(ops.latencia_ms.sample(5000, random_state=1) if len(ops) > 5000 else ops.latencia_ms),
                 "sondas": proportion(int((sondas.resultado == "SIN_RED").sum()), len(sondas)),
                 "duracion_ep01_nodo_ms": describe(nodos.ep01_duracion_ms)}
    pd.DataFrame([{"operacion": k, **describe(g.latencia_ms)} for k, g in ops.groupby("op")] +
                 [{"operacion": "TODAS", **describe(ops.latencia_ms)}]).to_csv(OUT / "tablas" / "t07_ep01_latencia_registro_local.csv", index=False)

    # ---------------- 6. Convergencia ----------------
    R["convergencia"] = {}
    for cond in ["limpia", "fallos"]:
        c = corridas[corridas.condicion == cond]
        R["convergencia"][cond] = {"tiempo_convergencia_ms": describe(c.tiempo_convergencia_ms), "tiempo_push_ms": describe(c.tiempo_reconexion_push_ms),
                                   "actualizaciones_concurrentes": describe(c.actualizaciones_concurrentes_resueltas),
                                   "conflictos_inmutables": int(c.conflictos_inmutables.sum())}
    R["convergencia"]["pull_ms"] = describe(nodos.pull_duracion_ms)
    R["convergencia"]["saldos_items"] = {"filas": int(len(saldos)), "invariante_ok": int(saldos.invariante_ok.sum()),
                                         "central_igual_oraculo": int(saldos.central_igual_oraculo.sum()),
                                         "replicas_iguales_central": int(saldos.replicas_iguales_central.sum())}
    pd.DataFrame([{"condicion": cond, "metrica": m, **describe(corridas[corridas.condicion == cond][col])}
                  for cond in ["limpia", "fallos"] for m, col in (("tiempo de convergencia (ms)", "tiempo_convergencia_ms"),
                                                                  ("tiempo de reconexión-push (ms)", "tiempo_reconexion_push_ms"))]
                 ).to_csv(OUT / "tablas" / "t08_convergencia.csv", index=False)

    # ---------------- figuras ----------------
    R["figuras"] = figures(lotes, corridas, ops, paired)

    # ---------------- exportación Jamovi / R ----------------
    lotes[["run_id", "condicion", "repeticion", "device_id", "lote_ordinal", "n_vales", "latencia_e2e_ms", "tp_ms_por_vale", "duracion_servidor_ms",
           "espera_cola_ms", "conciliacion_ms", "red_serializacion_ms", "intentos", "n_fallas", "fallas_inyectadas", "aplicados", "duplicados"]
          ].to_csv(OUT / "datos_jamovi" / "lotes.csv", index=False)
    corridas.assign(latencia_media_lote_ms=corridas.apply(lambda r: run_level[r.condicion].get(r.repeticion), axis=1)).to_csv(
        OUT / "datos_jamovi" / "corridas.csv", index=False)
    paired.reset_index().rename(columns={"limpia": "latencia_limpia_ms", "fallos": "latencia_fallos_ms"}).to_csv(
        OUT / "datos_jamovi" / "pareado_por_repeticion.csv", index=False)
    shutil.copy(Path(__file__).with_name("analisis_reproducible.R"), OUT / "analisis_reproducible.R")
    (OUT / "resultados_estadisticos.json").write_text(json.dumps(clean(R), indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(clean({"Id": R["indicadores"]["global"]["Id"], "Tr": R["indicadores"]["global"]["Tr"], "Do": R["indicadores"]["global"]["Do"],
                            "Tp_limpia": {k: R["tp"]["limpia"]["lote"][k] for k in ("media", "de", "p95", "max")},
                            "Tp_fallos": {k: R["tp"]["fallos"]["lote"][k] for k in ("media", "de", "p95", "max")}}), indent=1, ensure_ascii=False))


def figures(lotes, corridas, ops, paired) -> list[str]:
    names = []
    conds = ["limpia", "fallos"]

    # F1 histograma de latencia por lote (paneles separados: sin mezcla de colores por transparencia)
    fig, axes = plt.subplots(2, 1, figsize=(7, 4.6), sharex=True, sharey=True)
    bins = np.linspace(0, max(lotes.latencia_e2e_ms.max(), META_LOTE_MS) * 1.05, 45)
    for ax, cond in zip(axes, conds):
        x = lotes[lotes.condicion == cond].latencia_e2e_ms
        ax.hist(x, bins=bins, color=COLOR[cond], edgecolor="white", linewidth=.6)
        ax.axvline(META_LOTE_MS, color=INK2, ls="--", lw=1.2)
        ax.text(META_LOTE_MS, ax.get_ylim()[1] * .92, " meta 2,500 ms", color=INK2, va="top", fontsize=8)
        ax.axvline(x.mean(), color=INK, lw=1)
        ax.text(x.mean(), ax.get_ylim()[1] * .92, f" media {es(x.mean())} ms", color=INK, va="top", fontsize=8, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
        ax.set(ylabel="Lotes", title=f"{COND[cond]} (n = {len(x)})")
        ax.title.set_fontweight("normal")
    axes[1].set_xlabel("Latencia extremo a extremo por lote de 100 vales (ms)")
    fig.suptitle("Distribución del tiempo de conciliación por lote", fontweight="bold", fontsize=10)
    names.append(save(fig, "f01_histograma_latencia_lote"))

    # F2 boxplot por condición y orden de lote
    fig, ax = plt.subplots(figsize=(7, 3.6))
    data, labels, colors = [], [], []
    for cond in conds:
        for o in (0, 1):
            data.append(lotes[(lotes.condicion == cond) & (lotes.lote_ordinal == o)].latencia_e2e_ms)
            labels.append(f"{'Limpia' if cond == 'limpia' else 'Con cortes'}\nlote {o + 1} del nodo")
            colors.append(COLOR[cond])
    bp = ax.boxplot(data, patch_artist=True, widths=.5, medianprops={"color": INK, "lw": 1.4}, flierprops={"marker": "o", "ms": 3, "alpha": .5})
    for patch, c in zip(bp["boxes"], colors):
        patch.set(facecolor=c, alpha=.6, edgecolor=INK2)
    ax.set_xticks(range(1, 5), labels)
    ax.axhline(META_LOTE_MS, color=INK2, ls="--", lw=1.2)
    ax.text(4.45, META_LOTE_MS, "meta", color=INK2, va="bottom", fontsize=8, ha="right")
    ax.set(ylabel="Latencia por lote (ms)", title="Latencia por condición y orden de envío del lote")
    names.append(save(fig, "f02_boxplot_condicion_orden"))

    # F3 Q-Q
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.2))
    for ax, cond in zip(axes, conds):
        (osm, osr), (slope, inter, _) = stats.probplot(lotes[lotes.condicion == cond].latencia_e2e_ms, dist="norm")
        ax.scatter(osm, osr, s=8, color=COLOR[cond], alpha=.7)
        ax.plot(osm, slope * np.asarray(osm) + inter, color=INK2, lw=1)
        ax.set(title=COND[cond], xlabel="Cuantiles teóricos N(0,1)", ylabel="Latencia observada (ms)")
    names.append(save(fig, "f03_qq_normalidad"))

    # F4 medias por corrida con IC95
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for i, cond in enumerate(conds):
        g = lotes[lotes.condicion == cond].groupby("repeticion").latencia_e2e_ms
        m, s, n = g.mean(), g.std(ddof=1), g.size()
        err = stats.t.ppf(.975, n - 1) * s / np.sqrt(n)
        ax.errorbar(m.index + (i - .5) * .25, m, yerr=err, fmt="o", ms=4, color=COLOR[cond], elinewidth=1, capsize=2, label=COND[cond])
    ax.axhline(META_LOTE_MS, color=INK2, ls="--", lw=1.2)
    ax.text(30.5, META_LOTE_MS, "meta", color=INK2, va="bottom", ha="right", fontsize=8)
    ax.set(xlabel="Repetición", ylabel="Media de latencia por lote (ms) ± IC95 %", title="Media por corrida (10 lotes) con IC 95 %")
    ax.set_ylim(0, max(META_LOTE_MS * 1.1, ax.get_ylim()[1]))
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.18), ncol=2)
    names.append(save(fig, "f04_medias_por_corrida"))

    # F5 ECDF
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for cond in conds:
        x = np.sort(lotes[lotes.condicion == cond].latencia_e2e_ms)
        ax.step(x, np.arange(1, len(x) + 1) / len(x), where="post", color=COLOR[cond], lw=2, label=COND[cond])
    ax.axvline(META_LOTE_MS, color=INK2, ls="--", lw=1.2)
    ax.text(META_LOTE_MS, .5, "meta 2,500 ms ", color=INK2, fontsize=8, ha="right")
    ax.set(xlabel="Latencia por lote (ms)", ylabel="Proporción acumulada de lotes", title="Función de distribución empírica (ECDF)")
    ax.legend(loc="upper left")
    names.append(save(fig, "f05_ecdf_latencia"))

    # F6 descomposición
    fig, ax = plt.subplots(figsize=(7, 3.0))
    comps = [("conciliacion_ms", "Conciliación CRDT + commit", "#2a78d6"), ("espera_cola_ms", "Espera en cola del escritor", "#1baf7a"),
             ("red_serializacion_ms", "Red + serialización", "#9a9890"), ("sobrecosto_recuperacion_ms", "Reintentos (backoff + intentos fallidos)", "#eb6834")]
    for i, cond in enumerate(conds):
        left = 0
        lc = lotes[lotes.condicion == cond]
        for col, label, color in comps:
            v = lc[col].mean()
            ax.barh(i, v, left=left, color=color, edgecolor="white", linewidth=2, height=.55, label=label if i == 0 else None)
            if v > 120:
                ax.text(left + v / 2, i, es(v), ha="center", va="center", color="white", fontsize=8)
            left += v
        ax.text(left + 20, i, f"{es(left)} ms", va="center", color=INK, fontsize=8)
    ax.set_yticks([0, 1], [COND[c] for c in conds])
    ax.invert_yaxis()
    ax.set(xlabel="Tiempo medio por lote (ms)", title="Descomposición del tiempo medio por lote")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.28), ncol=2, fontsize=8)
    names.append(save(fig, "f06_descomposicion_tiempo"))

    # F7 latencia por intentos (EP04)
    lf = lotes[lotes.condicion == "fallos"]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    groups = sorted(lf.intentos.unique())
    bp = ax.boxplot([lf[lf.intentos == k].latencia_e2e_ms for k in groups], patch_artist=True, widths=.5,
                    medianprops={"color": INK, "lw": 1.4}, flierprops={"marker": "o", "ms": 3, "alpha": .5})
    for patch in bp["boxes"]:
        patch.set(facecolor=COLOR["fallos"], alpha=.6, edgecolor=INK2)
    ax.set_xticks(range(1, len(groups) + 1), [f"{k} intentos\n(n={int((lf.intentos == k).sum())})" for k in groups])
    ax.axhline(META_LOTE_MS, color=INK2, ls="--", lw=1.2)
    ax.set(ylabel="Latencia por lote (ms)", title="EP04: latencia según número de intentos hasta confirmar")
    names.append(save(fig, "f07_latencia_por_intentos"))

    # F8 indicadores con IC
    fig, ax = plt.subplots(figsize=(7, 3.0))
    rows = []
    for name, (k, n) in {"Integridad (Id)": (corridas.id_consistentes.sum(), corridas.id_transmitidos.sum()),
                         "Trazabilidad (Tr)": (corridas.tr_movimientos_trazados.sum(), corridas.tr_movimientos.sum()),
                         "Disponibilidad local (Do)": (corridas.do_exitos.sum(), corridas.do_intentos.sum())}.items():
        rows.append((name, proportion(k, n)))
    for i, (name, p) in enumerate(rows):
        ax.errorbar(p["pct"], i, xerr=[[p["pct"] - p["ic95_inf_pct"]], [p["ic95_sup_pct"] - p["pct"]]], fmt="o", color="#2a78d6", ms=6, capsize=3)
        ax.text((p["ic95_inf_pct"] + 100) / 2, i + .22, f"{es(p['k'])}/{es(p['n'])} = 100 %   ·   IC 95 % [{es(p['ic95_inf_pct'], 3)} %; 100 %]",
                ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.set_ylim(-.5, len(rows) - .2)
    lo = min(p["ic95_inf_pct"] for _, p in rows)
    ax.set_xlim(lo - .002, 100.001)
    ax.ticklabel_format(axis="x", useOffset=False, style="plain")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: es(v, 3)))
    ax.axvline(100, color=INK2, ls="--", lw=1)
    ax.set(xlabel="Porcentaje (%) con IC 95 % exacto de Clopper-Pearson", title="Indicadores de proporción frente a la meta del 100 %")
    names.append(save(fig, "f08_indicadores_ic"))

    # F9 EP01 latencia de registro local
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = ops.latencia_ms
    ax.hist(x.clip(upper=x.quantile(.995)), bins=50, color="#2a78d6", alpha=.7, edgecolor="white", linewidth=.5)
    ax.axvline(x.median(), color=INK, lw=1.2)
    ax.text(x.median(), ax.get_ylim()[1] * .95, f" mediana {es(x.median(), 2)} ms", fontsize=8, va="top")
    ax.set(xlabel="Latencia de registro local sin red (ms; recortado al p99.5)", ylabel="Operaciones",
           title=f"EP01: persistencia local de {es(len(x))} operaciones sin red")
    names.append(save(fig, "f09_ep01_registro_local"))

    # F10 diferencia pareada
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for rep, row in paired.iterrows():
        ax.plot([0, 1], [row.limpia, row.fallos], color=GRID, lw=1, zorder=1)
    ax.scatter(np.zeros(len(paired)), paired.limpia, color=COLOR["limpia"], s=14, zorder=2, label=COND["limpia"])
    ax.scatter(np.ones(len(paired)), paired.fallos, color=COLOR["fallos"], s=14, zorder=2, label=COND["fallos"])
    ax.set_xticks([0, 1], ["Red limpia", "Con cortes"])
    ax.set_xlim(-.5, 1.5)
    ax.set(ylabel="Media de latencia por lote (ms)", title="Comparación pareada por repetición (mismo dataset)")
    names.append(save(fig, "f10_pareado_condiciones"))
    return names


if __name__ == "__main__":
    main()
