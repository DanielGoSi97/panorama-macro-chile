# -*- coding: utf-8 -*-
"""
Cliente de la API de Estadísticas del Banco Central de Chile (BDE / SieteRestWS).

Requiere credenciales (registro gratuito en https://si3.bcentral.cl/Siete/).
Se leen de variables de entorno BCCH_USER y BCCH_PASS (nunca se hardcodean).

Doc del servicio:
  GET https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx
      ?user=...&pass=...&function=GetSeries&timeseries=<CODIGO>
      &firstdate=YYYY-MM-DD&lastdate=YYYY-MM-DD
Respuesta JSON: { "Series": { "Obs": [ {"indexDateString":"dd-mm-yyyy",
                 "value":"123.45", "statusCode":"OK"}, ... ] } }
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests

BASE = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"


class BCentralError(RuntimeError):
    pass


def _credenciales() -> tuple[str, str]:
    user = os.getenv("BCCH_USER")
    pwd = os.getenv("BCCH_PASS")
    if not user or not pwd:
        raise BCentralError(
            "Faltan credenciales del Banco Central. Define BCCH_USER y BCCH_PASS "
            "como variables de entorno (ver dashboard/.env en el servidor)."
        )
    return user, pwd


def get_series(codigo: str, anios_atras: int = 8, timeout: int = 25) -> pd.DataFrame:
    """Devuelve un DataFrame [fecha, valor] para un código de serie del BCCh.

    Solo conserva observaciones con statusCode 'OK' (descarta nulos/feriados).
    """
    user, pwd = _credenciales()
    hoy = datetime.now()
    params = {
        "user": user, "pass": pwd,
        "function": "GetSeries", "timeseries": codigo,
        "firstdate": f"{hoy.year - anios_atras}-01-01",
        "lastdate": hoy.strftime("%Y-%m-%d"),
    }
    r = requests.get(BASE, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    cod = str(data.get("Codigo", "0"))
    if cod not in ("0", "OK"):
        raise BCentralError(f"API BCCh devolvió código {cod}: {data.get('Descripcion')}")

    obs = (data.get("Series") or {}).get("Obs") or []
    filas = []
    for o in obs:
        if o.get("statusCode") != "OK":
            continue
        try:
            filas.append({"fecha": o["indexDateString"], "valor": float(o["value"])})
        except (KeyError, ValueError, TypeError):
            continue
    if not filas:
        return pd.DataFrame(columns=["fecha", "valor"])
    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"], format="%d-%m-%Y", errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values("fecha").reset_index(drop=True)


def get_catalog(frequencies=("DAILY", "MONTHLY", "QUARTERLY", "ANNUAL"),
                timeout: int = 45) -> pd.DataFrame:
    """Catálogo de series disponibles: DataFrame [codigo, titulo, frecuencia].

    Usa la función SearchSeries del BCCh (devuelve ~20k series). Pensado para
    cachearse en la capa de la app (cambia muy poco).
    """
    user, pwd = _credenciales()
    filas = []
    for freq in frequencies:
        try:
            r = requests.get(BASE, params={
                "user": user, "pass": pwd,
                "function": "SearchSeries", "frequency": freq,
            }, timeout=timeout)
            r.raise_for_status()
            for s in (r.json().get("SeriesInfos") or []):
                titulo = s.get("spanishTitle") or s.get("englishTitle") or ""
                filas.append({"codigo": s.get("seriesId", ""),
                              "titulo": titulo.strip(), "frecuencia": freq})
        except Exception:  # noqa: BLE001
            continue
    df = pd.DataFrame(filas, columns=["codigo", "titulo", "frecuencia"])
    return df[df["codigo"] != ""].drop_duplicates("codigo").reset_index(drop=True)


def probar_credenciales(codigo_test: str = "F073.TCO.PRE.Z.D") -> int:
    """Verifica conectividad+credenciales devolviendo el N° de observaciones del dólar."""
    return len(get_series(codigo_test, anios_atras=1))
