# -*- coding: utf-8 -*-
"""
Dashboard macro de Chile — datos en vivo desde la API del Banco Central (BDE).
Bilingüe (ES/EN): lee ?lang de la URL y tiene su propio selector de idioma.

Fuente: API Base de Datos Estadísticos (BDE) del Banco Central de Chile.
Credenciales en dashboard/.env (BCCH_USER, BCCH_PASS).
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import bcentral

# ---------------- Paleta ----------------
PRIMARIO = "#0F766E"; PRIM_OSC = "#115E59"; PRIM_TINTE = "#CCFBF1"; CIAN = "#0E7490"
FONDO = "#F5F7F7"; CARD = "#FFFFFF"; BORDE = "#E2E8F0"; TXT = "#0F172A"
TXT_MED = "#64748B"; TXT_SUAVE = "#94A3B8"; ROJO = "#DC2626"

TTL_CACHE = 60 * 60 * 6
ANIOS = 8

# ---- Series curadas por área. (key, {es,en} título), [(codigo, {es,en}, unidad)] ----
AREAS = [
    ("fx", {"es": "Tipo de cambio", "en": "Exchange rate"}, [
        ("F073.TCO.PRE.Z.D", {"es": "Dólar observado", "en": "Observed US dollar"}, "$"),
        ("F072.CLP.EUR.N.O.D", {"es": "Euro", "en": "Euro"}, "$"),
    ]),
    ("unidades", {"es": "Unidades reajustables", "en": "Indexation units"}, [
        ("F073.UFF.PRE.Z.D", {"es": "Unidad de Fomento (UF)", "en": "Unidad de Fomento (UF)"}, "$"),
        ("F073.UTR.PRE.Z.M", {"es": "Unidad Tributaria Mensual (UTM)", "en": "Monthly Tax Unit (UTM)"}, "$"),
    ]),
    ("precios", {"es": "Precios", "en": "Prices"}, [
        ("F074.IPC.VAR.Z.Z.C.M", {"es": "IPC · variación mensual", "en": "CPI · monthly change"}, "%"),
        ("G073.IPC.V12.2023.M", {"es": "IPC · variación anual", "en": "CPI · annual change"}, "%"),
    ]),
    ("actividad", {"es": "Actividad", "en": "Activity"}, [
        ("F032.IMC.IND.Z.Z.EP18.Z.Z.0.M", {"es": "IMACEC · índice", "en": "IMACEC · index"}, "idx"),
    ]),
    ("monetaria", {"es": "Política monetaria", "en": "Monetary policy"}, [
        ("F022.TPM.TIN.D001.NO.Z.D", {"es": "Tasa de Política Monetaria (TPM)", "en": "Monetary Policy Rate (MPR)"}, "%"),
    ]),
    ("empleo", {"es": "Empleo", "en": "Employment"}, [
        ("F049.DES.TAS.INE9.10.M", {"es": "Tasa de desempleo", "en": "Unemployment rate"}, "%"),
    ]),
]

DESTACADOS = [
    ("F073.TCO.PRE.Z.D", {"es": "Dólar", "en": "USD"}, "$"),
    ("F073.UFF.PRE.Z.D", {"es": "UF", "en": "UF"}, "$"),
    ("F073.UTR.PRE.Z.M", {"es": "UTM", "en": "UTM"}, "$"),
    ("F074.IPC.VAR.Z.Z.C.M", {"es": "IPC mensual", "en": "CPI monthly"}, "%"),
    ("F022.TPM.TIN.D001.NO.Z.D", {"es": "TPM", "en": "MPR"}, "%"),
    ("F049.DES.TAS.INE9.10.M", {"es": "Desempleo", "en": "Unemployment"}, "%"),
]

# ---------------- Traducciones de interfaz ----------------
T = {
    "es": {
        "volver": "← Volver al portafolio", "actualizar": "🔄 Actualizar",
        "hero_t": "Panorama Macroeconómico de Chile",
        "hero_s": "Indicadores en vivo desde la API del Banco Central de Chile (BDE)",
        "b_cargando": "⏱ Cargando…", "b_ultimo": "⏱ Último dato:",
        "b_envivo": "🔴 Datos en vivo (caché 6 h)",
        "b_fuente": "🏦 Fuente: BCCh · Base de Datos Estadísticos",
        "spinner": "Cargando indicadores desde el Banco Central…",
        "explorador": "🔎 Explorador de series",
        "meses": "Meses de proyección",
        "ultimo_valor": "Último valor", "min": "Mínimo período", "max": "Máximo período",
        "prom": "Promedio período", "al": "Al", "ultimo_dato": "Último dato:",
        "sin_datos": "Sin datos para", "fecha": "Fecha", "proyeccion": "Proyección",
        "indice": "Índice",
        "exp_titulo": "Explorador del catálogo del Banco Central",
        "exp_sub": "Busca entre las ~20.000 series de la Base de Datos Estadísticos. "
                   "Escribe palabras clave (ej. «exportaciones cobre», «tasa interés», «PIB minería»).",
        "exp_buscar": "Buscar serie", "exp_ph": "palabras clave…", "exp_freq": "Frecuencia",
        "exp_coinc": "coincidencias", "exp_result": "Resultados (máx. 300)",
        "exp_sindata": "Esa serie no devolvió datos.", "exp_min": "Mínimo", "exp_max": "Máximo",
        "exp_obs": "Observaciones", "descargar": "⬇ Descargar CSV",
        "exp_min3": "Escribe al menos 3 caracteres para buscar.",
        "exp_nocat": "No se pudo cargar el catálogo de series.",
        "exp_cargacat": "Cargando catálogo de series del BCCh…",
        "footer": "Proyecciones por regresión lineal de tendencia; referenciales, no constituyen "
                  "asesoría de inversión. Fuente: API BDE, Banco Central de Chile.",
    },
    "en": {
        "volver": "← Back to portfolio", "actualizar": "🔄 Refresh",
        "hero_t": "Chilean Macroeconomic Overview",
        "hero_s": "Live indicators from the Central Bank of Chile API (BDE)",
        "b_cargando": "⏱ Loading…", "b_ultimo": "⏱ Latest data:",
        "b_envivo": "🔴 Live data (6h cache)",
        "b_fuente": "🏦 Source: Central Bank · Statistics Database",
        "spinner": "Loading indicators from the Central Bank…",
        "explorador": "🔎 Series explorer",
        "meses": "Projection months",
        "ultimo_valor": "Latest value", "min": "Period minimum", "max": "Period maximum",
        "prom": "Period average", "al": "As of", "ultimo_dato": "Latest data:",
        "sin_datos": "No data for", "fecha": "Date", "proyeccion": "Projection",
        "indice": "Index",
        "exp_titulo": "Central Bank catalog explorer",
        "exp_sub": "Search across the ~20,000 series of the Statistics Database. "
                   "Type keywords (e.g. «copper exports», «interest rate», «mining GDP»).",
        "exp_buscar": "Search series", "exp_ph": "keywords…", "exp_freq": "Frequency",
        "exp_coinc": "matches", "exp_result": "Results (max 300)",
        "exp_sindata": "That series returned no data.", "exp_min": "Minimum", "exp_max": "Maximum",
        "exp_obs": "Observations", "descargar": "⬇ Download CSV",
        "exp_min3": "Type at least 3 characters to search.",
        "exp_nocat": "Could not load the series catalog.",
        "exp_cargacat": "Loading the Central Bank series catalog…",
        "footer": "Trend projections via linear regression; indicative only, not investment "
                  "advice. Source: BDE API, Central Bank of Chile.",
    },
}

st.set_page_config(page_title="Macro Chile · Banco Central", layout="wide",
                   page_icon="https://dgonzsim.cl/favicon.svg",
                   initial_sidebar_state="collapsed")


def _get_lang() -> str:
    q = st.query_params.get("lang", "es")
    return q if q in ("es", "en") else "es"


LANG = _get_lang()
def t(k: str) -> str: return T[LANG].get(k, k)


st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, .stApp, [class*="st-"] {{ font-family:'Inter', -apple-system, 'Segoe UI', sans-serif; }}
    span[data-testid="stIconMaterial"] {{ font-family:'Material Symbols Rounded' !important; }}
    .stApp {{ background-color:{FONDO}; }}
    header[data-testid="stHeader"] {{ display:none; }}
    div[data-testid="stToolbar"] {{ display:none; }}
    .block-container {{ padding-top:2rem; padding-bottom:2rem; max-width:1280px; }}
    h1,h2,h3,h4 {{ color:{TXT}; font-weight:700; letter-spacing:-0.3px; }}
    .hero {{ background:linear-gradient(120deg, #0B3B36 0%, {PRIM_OSC} 55%, {PRIMARIO} 100%);
        border-radius:18px; padding:26px 32px 22px 32px; margin-bottom:18px;
        box-shadow:0 8px 24px rgba(11,59,54,0.18); }}
    .hero-title {{ color:#FFFFFF; font-size:1.65rem; font-weight:800; letter-spacing:-0.6px; margin:0; }}
    .hero-sub {{ color:#A7E8DF; font-size:0.88rem; margin-top:4px; font-weight:500; }}
    .hero-badge {{ display:inline-block; background:rgba(255,255,255,0.14); color:#E6FFFA;
        border:1px solid rgba(255,255,255,0.22); border-radius:999px;
        padding:3px 12px; font-size:0.72rem; font-weight:600; margin-top:10px; margin-right:6px; }}
    div[class*="st-key-card"] {{ background:{CARD} !important; border:1px solid {BORDE} !important;
        border-radius:16px !important; padding:14px 20px !important;
        box-shadow:0 1px 2px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04) !important; }}
    div[data-testid="stMetric"] {{ background:{CARD}; border:1px solid {BORDE}; border-radius:16px;
        padding:16px 20px; min-height:112px;
        box-shadow:0 1px 2px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04); }}
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] > div {{
        color:{TXT}; font-weight:800; letter-spacing:-0.5px; font-size:1.45rem !important; }}
    div[data-testid="stMetricLabel"] p {{ color:{TXT_MED} !important; font-size:0.72rem !important;
        font-weight:600 !important; text-transform:uppercase; letter-spacing:0.6px; }}
    button[data-baseweb="tab"] {{ font-weight:600; color:{TXT_MED}; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color:{PRIMARIO}; }}
    div[data-baseweb="tab-highlight"] {{ background-color:{PRIMARIO} !important; height:3px; border-radius:3px; }}
    div[data-testid="stButton"] > button {{ background:{PRIMARIO}; color:#fff; border:none;
        border-radius:10px; font-weight:600; }}
    div[data-testid="stButton"] > button:hover {{ background:{PRIM_OSC}; color:#fff; }}
    div[data-testid="stDownloadButton"] > button {{ background:{CARD}; color:{PRIMARIO};
        border:1.5px solid {PRIMARIO}; border-radius:10px; font-weight:600; }}
</style>
""", unsafe_allow_html=True)


# --------------------------- Credenciales (.env) ---------------------------
def _cargar_env():
    f = Path(__file__).resolve().parent / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_cargar_env()


# --------------------------- Datos (cacheados) ---------------------------
@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def serie(codigo: str) -> pd.DataFrame:
    try:
        return bcentral.get_series(codigo, anios_atras=ANIOS)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["fecha", "valor"])


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def catalogo() -> pd.DataFrame:
    try:
        return bcentral.get_catalog()
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["codigo", "titulo", "frecuencia"])


def variacion_12m(df: pd.DataFrame):
    if len(df) < 2:
        return None
    ult = df["valor"].iloc[-1]
    hace12 = df[df["fecha"] >= df["fecha"].max() - pd.Timedelta(days=365)]
    base = hace12["valor"].iloc[0] if len(hace12) else None
    return (ult / base - 1) * 100 if base else None


def proyectar(df: pd.DataFrame, meses: int) -> pd.DataFrame:
    if len(df) < 3 or meses <= 0:
        return pd.DataFrame(columns=["fecha", "valor"])
    x = df["fecha"].map(datetime.toordinal).to_numpy(dtype=float)
    y = df["valor"].to_numpy(dtype=float)
    a, b = np.polyfit(x, y, 1)
    fut = pd.date_range(df["fecha"].max() + pd.offsets.MonthBegin(1), periods=meses, freq="MS")
    return pd.DataFrame({"fecha": fut, "valor": a * np.array([f.toordinal() for f in fut]) + b})


def fmt(v, unidad: str) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if unidad == "%":
        s = f"{v:,.2f} %"
    elif unidad in ("$", "US$"):
        s = f"{unidad} {v:,.2f}"
    else:
        s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


AXIS = dict(labelColor=TXT_MED, titleColor=TXT_MED, gridColor="#EEF2F6")


def grafico_serie(df: pd.DataFrame, nombre: str, unidad: str, meses_proy: int):
    proy = proyectar(df, meses_proy)
    capas = []
    base = alt.Chart(df).encode(
        x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%b %y", **AXIS)),
        y=alt.Y("valor:Q", title=unidad if unidad in ("$", "%", "US$") else t("indice"),
                scale=alt.Scale(zero=False), axis=alt.Axis(**AXIS)))
    capas.append(base.mark_area(opacity=0.12, color=PRIMARIO))
    capas.append(base.mark_line(color=PRIMARIO, strokeWidth=2.2).encode(
        tooltip=[alt.Tooltip("fecha:T", title=t("fecha"), format="%d-%m-%Y"),
                 alt.Tooltip("valor:Q", title=nombre, format=",.2f")]))
    if not proy.empty:
        puente = pd.concat([df.tail(1)[["fecha", "valor"]], proy], ignore_index=True)
        capas.append(alt.Chart(puente).mark_line(
            color=ROJO, strokeWidth=2.2, strokeDash=[6, 4]).encode(
            x="fecha:T", y="valor:Q",
            tooltip=[alt.Tooltip("fecha:T", format="%b %Y"),
                     alt.Tooltip("valor:Q", title=t("proyeccion"), format=",.2f")]))
    st.altair_chart(alt.layer(*capas).properties(height=340, background="transparent")
                    .configure_view(strokeWidth=0), width="stretch")


def panel_serie(codigo: str, nombre: str, unidad: str, meses_proy: int, key: str):
    df = serie(codigo)
    if df.empty:
        st.warning(f"{t('sin_datos')} «{nombre}» ({codigo}).")
        return
    var = variacion_12m(df)
    k = st.columns(4)
    k[0].metric(t("ultimo_valor"), fmt(df["valor"].iloc[-1], unidad),
                delta=f"{var:+.1f}% 12m" if var is not None else None,
                delta_color="normal" if unidad not in ("%", "idx") else "off",
                help=f"{t('al')} {df['fecha'].max().date()}")
    k[1].metric(t("min"), fmt(df["valor"].min(), unidad))
    k[2].metric(t("max"), fmt(df["valor"].max(), unidad))
    k[3].metric(t("prom"), fmt(df["valor"].mean(), unidad))
    with st.container(border=True, key=f"card_{key}"):
        st.markdown(f"##### {nombre}  ·  `{codigo}`")
        grafico_serie(df, nombre, unidad, meses_proy)


# --------------------------- Cabecera ---------------------------
st.markdown(
    f'<a href="/?lang={LANG}" target="_self" style="color:{PRIMARIO};font-weight:600;'
    f'font-size:0.85rem;text-decoration:none;">{t("volver")}</a>',
    unsafe_allow_html=True)
cab = st.columns([5, 1.1, 1.1])
sel = cab[1].radio("idioma", ["ES", "EN"], index=0 if LANG == "es" else 1,
                   horizontal=True, label_visibility="collapsed")
if {"ES": "es", "EN": "en"}[sel] != LANG:
    st.query_params["lang"] = {"ES": "es", "EN": "en"}[sel]
    st.rerun()
if cab[2].button(t("actualizar"), key="refresh", width="stretch"):
    st.cache_data.clear()
    st.rerun()

hero = st.empty()
hero.markdown(
    f'<div class="hero"><p class="hero-title">{t("hero_t")}</p>'
    f'<p class="hero-sub">{t("hero_s")}</p>'
    f'<span class="hero-badge">{t("b_cargando")}</span></div>', unsafe_allow_html=True)

with st.spinner(t("spinner")):
    dest_df = {cod: serie(cod) for cod, _, _ in DESTACADOS}
fechas = [d["fecha"].max() for d in dest_df.values() if not d.empty]
ult = max(fechas).date() if fechas else "—"

hero.markdown(
    f'<div class="hero"><p class="hero-title">{t("hero_t")}</p>'
    f'<p class="hero-sub">{t("hero_s")}</p>'
    f'<span class="hero-badge">{t("b_ultimo")} {ult}</span>'
    f'<span class="hero-badge">{t("b_envivo")}</span>'
    f'<span class="hero-badge">{t("b_fuente")}</span></div>',
    unsafe_allow_html=True)

# KPIs destacados
cols = st.columns(len(DESTACADOS))
for col, (cod, etiqueta, unidad) in zip(cols, DESTACADOS):
    df = dest_df[cod]
    if df.empty:
        col.metric(etiqueta[LANG], "—")
        continue
    var = variacion_12m(df)
    col.metric(etiqueta[LANG], fmt(df["valor"].iloc[-1], unidad),
               delta=f"{var:+.1f}% 12m" if var is not None else None,
               delta_color="normal" if unidad not in ("%", "idx") else "off",
               help=f"{t('ultimo_dato')} {df['fecha'].max().date()}")

st.write("")

# --------------------------- Pestañas ---------------------------
tab_labels = [a[1][LANG] for a in AREAS] + [t("explorador")]
tabs = st.tabs(tab_labels)

for tab, (key, _lab, series_list) in zip(tabs[:-1], AREAS):
    with tab:
        meses = st.slider(t("meses"), 0, 12, 6, key=f"proy_{key}")
        for i, (cod, nombre, unidad) in enumerate(series_list):
            panel_serie(cod, nombre[LANG], unidad, meses, key=f"{key}_{i}")
            st.write("")

# --------------------------- Explorador ---------------------------
with tabs[-1]:
    st.markdown(f"##### {t('exp_titulo')}")
    st.caption(t("exp_sub"))
    c = st.columns([3, 1])
    q = c[0].text_input(t("exp_buscar"), placeholder=t("exp_ph"), key="exp_q")
    freq_sel = c[1].multiselect(t("exp_freq"), ["DAILY", "MONTHLY", "QUARTERLY", "ANNUAL"],
                                key="exp_freq")
    if q and len(q.strip()) >= 3:
        with st.spinner(t("exp_cargacat")):
            cat = catalogo()
        filt = cat
        if freq_sel:
            filt = filt[filt["frecuencia"].isin(freq_sel)]
        if cat.empty:
            st.warning(t("exp_nocat"))
        else:
            for palabra in q.lower().split():
                filt = filt[filt["titulo"].str.lower().str.contains(palabra, na=False)]
            st.caption(f"{len(filt):,} {t('exp_coinc')}".replace(",", "."))
            if not filt.empty:
                opciones = filt.head(300)
                etiqueta = {f"{r.titulo}  ·  [{r.codigo}]": r.codigo
                            for r in opciones.itertuples()}
                elegido = st.selectbox(t("exp_result"), list(etiqueta), key="exp_sel")
                cod = etiqueta[elegido]
                meses = st.slider(t("meses"), 0, 12, 6, key="exp_proy")
                df = serie(cod)
                if df.empty:
                    st.warning(t("exp_sindata"))
                else:
                    var = variacion_12m(df)
                    k = st.columns(4)
                    k[0].metric(t("ultimo_valor"), fmt(df["valor"].iloc[-1], ""),
                                delta=f"{var:+.1f}% 12m" if var is not None else None,
                                delta_color="off", help=f"{t('al')} {df['fecha'].max().date()}")
                    k[1].metric(t("exp_min"), fmt(df["valor"].min(), ""))
                    k[2].metric(t("exp_max"), fmt(df["valor"].max(), ""))
                    k[3].metric(t("exp_obs"), f"{len(df):,}".replace(",", "."))
                    with st.container(border=True, key="card_exp"):
                        st.markdown(f"##### {elegido}")
                        grafico_serie(df, "valor", "", meses)
                    tabla = df.copy(); tabla["fecha"] = tabla["fecha"].dt.date
                    st.download_button(t("descargar"),
                                       tabla.to_csv(index=False).encode("utf-8-sig"),
                                       file_name=f"{cod}.csv", mime="text/csv")
    else:
        st.info(t("exp_min3"))

st.caption(t("footer"))
