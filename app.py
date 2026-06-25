# -*- coding: utf-8 -*-
"""
Dashboard macro de Chile — datos en vivo desde la API del Banco Central (BDE).

Fuente: API Base de Datos Estadísticos (BDE) del Banco Central de Chile
(si3.bcentral.cl / SieteRestWS). Credenciales en dashboard/.env (BCCH_USER,
BCCH_PASS). Datos en vivo con caché.

Secciones: KPIs destacados, pestañas temáticas con series curadas (cada una con
proyección de tendencia) y un Explorador que busca entre las ~20.000 series del
catálogo del BCCh.

Diseño alineado al dashboard de Licitaciones (Inter, paleta teal, hero, KPIs en
tarjetas, gráficos Altair).
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

# ---------------- Paleta (teal moderno + neutros slate) ----------------
PRIMARIO = "#0F766E"
PRIM_OSC = "#115E59"
PRIM_TINTE = "#CCFBF1"
CIAN = "#0E7490"
FONDO = "#F5F7F7"
CARD = "#FFFFFF"
BORDE = "#E2E8F0"
TXT = "#0F172A"
TXT_MED = "#64748B"
TXT_SUAVE = "#94A3B8"
ROJO = "#DC2626"

TTL_CACHE = 60 * 60 * 6   # 6 horas
ANIOS = 8                 # histórico a traer por serie

# ---- Series curadas (códigos verificados del BCCh) por área temática ----
# (codigo, nombre legible, unidad: "$" | "%" | "idx")
CURADO: dict[str, list[tuple[str, str, str]]] = {
    "Tipo de cambio": [
        ("F073.TCO.PRE.Z.D", "Dólar observado", "$"),
        ("F072.CLP.EUR.N.O.D", "Euro", "$"),
    ],
    "Unidades reajustables": [
        ("F073.UFF.PRE.Z.D", "Unidad de Fomento (UF)", "$"),
        ("F073.UTR.PRE.Z.M", "Unidad Tributaria Mensual (UTM)", "$"),
    ],
    "Precios": [
        ("F074.IPC.VAR.Z.Z.C.M", "IPC · variación mensual", "%"),
        ("G073.IPC.V12.2023.M", "IPC · variación anual", "%"),
    ],
    "Actividad": [
        ("F032.IMC.IND.Z.Z.EP18.Z.Z.0.M", "IMACEC · índice", "idx"),
    ],
    "Política monetaria": [
        ("F022.TPM.TIN.D001.NO.Z.D", "Tasa de Política Monetaria (TPM)", "%"),
    ],
    "Empleo": [
        ("F049.DES.TAS.INE9.10.M", "Tasa de desempleo", "%"),
    ],
}

# KPIs de la fila superior: (codigo, etiqueta corta, unidad)
DESTACADOS = [
    ("F073.TCO.PRE.Z.D", "Dólar", "$"),
    ("F073.UFF.PRE.Z.D", "UF", "$"),
    ("F073.UTR.PRE.Z.M", "UTM", "$"),
    ("F074.IPC.VAR.Z.Z.C.M", "IPC mensual", "%"),
    ("F022.TPM.TIN.D001.NO.Z.D", "TPM", "%"),
    ("F049.DES.TAS.INE9.10.M", "Desempleo", "%"),
]

st.set_page_config(page_title="Macro Chile · Banco Central", layout="wide",
                   page_icon="📊", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, .stApp, [class*="st-"] {{ font-family:'Inter', -apple-system, 'Segoe UI', sans-serif; }}
    span[data-testid="stIconMaterial"] {{ font-family:'Material Symbols Rounded' !important; }}
    .stApp {{ background-color:{FONDO}; }}
    .block-container {{ padding-top:1.2rem; padding-bottom:2rem; max-width:1280px; }}
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
        y=alt.Y("valor:Q", title=unidad if unidad in ("$", "%", "US$") else "Índice",
                scale=alt.Scale(zero=False), axis=alt.Axis(**AXIS)))
    capas.append(base.mark_area(opacity=0.12, color=PRIMARIO))
    capas.append(base.mark_line(color=PRIMARIO, strokeWidth=2.2).encode(
        tooltip=[alt.Tooltip("fecha:T", title="Fecha", format="%d-%m-%Y"),
                 alt.Tooltip("valor:Q", title=nombre, format=",.2f")]))
    if not proy.empty:
        puente = pd.concat([df.tail(1)[["fecha", "valor"]], proy], ignore_index=True)
        capas.append(alt.Chart(puente).mark_line(
            color=ROJO, strokeWidth=2.2, strokeDash=[6, 4]).encode(
            x="fecha:T", y="valor:Q",
            tooltip=[alt.Tooltip("fecha:T", format="%b %Y"),
                     alt.Tooltip("valor:Q", title="Proyección", format=",.2f")]))
    st.altair_chart(alt.layer(*capas).properties(height=340, background="transparent")
                    .configure_view(strokeWidth=0), width="stretch")


def panel_serie(codigo: str, nombre: str, unidad: str, meses_proy: int, key: str):
    df = serie(codigo)
    if df.empty:
        st.warning(f"Sin datos para «{nombre}» ({codigo}).")
        return
    var = variacion_12m(df)
    k = st.columns(4)
    k[0].metric("Último valor", fmt(df["valor"].iloc[-1], unidad),
                delta=f"{var:+.1f}% 12m" if var is not None else None,
                delta_color="normal" if unidad not in ("%", "idx") else "off",
                help=f"Al {df['fecha'].max().date()}")
    k[1].metric("Mínimo período", fmt(df["valor"].min(), unidad))
    k[2].metric("Máximo período", fmt(df["valor"].max(), unidad))
    k[3].metric("Promedio período", fmt(df["valor"].mean(), unidad))
    with st.container(border=True, key=f"card_{key}"):
        st.markdown(f"##### {nombre}  ·  `{codigo}`")
        grafico_serie(df, nombre, unidad, meses_proy)


# --------------------------- Cabecera ---------------------------
cab = st.columns([5, 1])
if cab[1].button("🔄 Actualizar", key="refresh", width="stretch"):
    st.cache_data.clear()
    st.rerun()

hero = st.empty()
hero.markdown(
    '<div class="hero"><p class="hero-title">Panorama Macroeconómico de Chile</p>'
    '<p class="hero-sub">Indicadores en vivo desde la API del Banco Central de Chile (BDE)</p>'
    '<span class="hero-badge">⏱ Cargando…</span></div>', unsafe_allow_html=True)

with st.spinner("Cargando indicadores desde el Banco Central…"):
    dest_df = {cod: serie(cod) for cod, _, _ in DESTACADOS}
fechas = [d["fecha"].max() for d in dest_df.values() if not d.empty]
ult = max(fechas).date() if fechas else "—"

hero.markdown(
    '<div class="hero"><p class="hero-title">Panorama Macroeconómico de Chile</p>'
    '<p class="hero-sub">Indicadores en vivo desde la API del Banco Central de Chile (BDE)</p>'
    f'<span class="hero-badge">⏱ Último dato: {ult}</span>'
    '<span class="hero-badge">🔴 Datos en vivo (caché 6 h)</span>'
    '<span class="hero-badge">🏦 Fuente: BCCh · Base de Datos Estadísticos</span></div>',
    unsafe_allow_html=True)

# KPIs destacados
cols = st.columns(len(DESTACADOS))
for col, (cod, etiqueta, unidad) in zip(cols, DESTACADOS):
    df = dest_df[cod]
    if df.empty:
        col.metric(etiqueta, "—")
        continue
    var = variacion_12m(df)
    col.metric(etiqueta, fmt(df["valor"].iloc[-1], unidad),
               delta=f"{var:+.1f}% 12m" if var is not None else None,
               delta_color="normal" if unidad not in ("%", "idx") else "off",
               help=f"Último dato: {df['fecha'].max().date()}")

st.write("")

# --------------------------- Pestañas ---------------------------
areas = list(CURADO.keys())
tabs = st.tabs(areas + ["🔎 Explorador de series"])

# Control de proyección compartido (en cada pestaña temática)
for tab, area in zip(tabs[:-1], areas):
    with tab:
        meses = st.slider("Meses de proyección", 0, 12, 6, key=f"proy_{area}")
        for i, (cod, nombre, unidad) in enumerate(CURADO[area]):
            panel_serie(cod, nombre, unidad, meses, key=f"{area}_{i}")
            st.write("")

# --------------------------- Explorador ---------------------------
with tabs[-1]:
    st.markdown("##### Explorador del catálogo del Banco Central")
    st.caption("Busca entre las ~20.000 series de la Base de Datos Estadísticos. "
               "Escribe palabras clave (ej. «exportaciones cobre», «tasa interés», «PIB minería»).")
    c = st.columns([3, 1])
    q = c[0].text_input("Buscar serie", placeholder="palabras clave…", key="exp_q")
    freq_sel = c[1].multiselect("Frecuencia", ["DAILY", "MONTHLY", "QUARTERLY", "ANNUAL"],
                                key="exp_freq")
    if q and len(q.strip()) >= 3:
        # El catálogo solo se descarga al buscar (es grande); luego queda cacheado.
        with st.spinner("Cargando catálogo de series del BCCh…"):
            cat = catalogo()
        filt = cat
        if freq_sel:
            filt = filt[filt["frecuencia"].isin(freq_sel)]
        if cat.empty:
            st.warning("No se pudo cargar el catálogo de series.")
        else:
            for palabra in q.lower().split():
                filt = filt[filt["titulo"].str.lower().str.contains(palabra, na=False)]
            st.caption(f"{len(filt):,} coincidencias".replace(",", "."))
            if not filt.empty:
                opciones = filt.head(300)
                etiqueta = {f"{r.titulo}  ·  [{r.codigo}]": r.codigo
                            for r in opciones.itertuples()}
                elegido = st.selectbox("Resultados (máx. 300)", list(etiqueta), key="exp_sel")
                cod = etiqueta[elegido]
                meses = st.slider("Meses de proyección", 0, 12, 6, key="exp_proy")
                df = serie(cod)
                if df.empty:
                    st.warning("Esa serie no devolvió datos.")
                else:
                    var = variacion_12m(df)
                    k = st.columns(4)
                    k[0].metric("Último valor", fmt(df["valor"].iloc[-1], ""),
                                delta=f"{var:+.1f}% 12m" if var is not None else None,
                                delta_color="off", help=f"Al {df['fecha'].max().date()}")
                    k[1].metric("Mínimo", fmt(df["valor"].min(), ""))
                    k[2].metric("Máximo", fmt(df["valor"].max(), ""))
                    k[3].metric("Observaciones", f"{len(df):,}".replace(",", "."))
                    with st.container(border=True, key="card_exp"):
                        st.markdown(f"##### {elegido}")
                        grafico_serie(df, "valor", "", meses)
                    tabla = df.copy(); tabla["fecha"] = tabla["fecha"].dt.date
                    st.download_button("⬇ Descargar CSV",
                                       tabla.to_csv(index=False).encode("utf-8-sig"),
                                       file_name=f"{cod}.csv", mime="text/csv")
    else:
        st.info("Escribe al menos 3 caracteres para buscar.")

st.caption("Proyecciones por regresión lineal de tendencia; referenciales, no constituyen "
           "asesoría de inversión. Fuente: API BDE, Banco Central de Chile.")
