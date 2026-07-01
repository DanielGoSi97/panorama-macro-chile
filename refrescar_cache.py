# -*- coding: utf-8 -*-
"""Pre-descarga las series del BCCh a disco (cache/*.pkl) para que el dashboard
cargue instantáneo. Lo ejecuta un cron cada 6 h. Como el BCCh SÍ es accesible
desde el EC2, esto desacopla la descarga (lenta) del request del usuario.
"""
import os
from datetime import datetime
from pathlib import Path

import bcentral

BASE = Path(__file__).resolve().parent
CACHE = BASE / "cache"
CACHE.mkdir(exist_ok=True)

# credenciales desde .env
for line in (BASE / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# Series usadas por el dashboard (KPIs destacados + pestañas curadas)
CODES = [
    "F073.TCO.PRE.Z.D", "F072.CLP.EUR.N.O.D", "F073.UFF.PRE.Z.D",
    "F073.UTR.PRE.Z.M", "F074.IPC.VAR.Z.Z.C.M", "G073.IPC.V12.2023.M",
    "F032.IMC.IND.Z.Z.EP18.Z.Z.0.M", "F022.TPM.TIN.D001.NO.Z.D",
    "F049.DES.TAS.INE9.10.M",
]

ok = 0
for c in CODES:
    try:
        df = bcentral.get_series(c, anios_atras=8)
        if not df.empty:
            df.to_pickle(CACHE / f"{c}.pkl")
            ok += 1
    except Exception as e:  # noqa: BLE001
        print(f"[{datetime.now():%F %T}] FALLO {c}: {str(e)[:80]}")

print(f"[{datetime.now():%F %T}] refrescadas {ok}/{len(CODES)} series en cache/")
