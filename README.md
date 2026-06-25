# Panorama Macroeconómico de Chile 📊

Dashboard en producción que consume **en vivo** la API de la **Base de Datos
Estadísticos (BDE)** del **Banco Central de Chile** (~20.000 series) y las
presenta con KPIs, gráficos interactivos y proyecciones de tendencia.

🔗 **App en vivo:** https://dgonzsim.cl

---

## Funcionalidades
- **KPIs destacados** en vivo: dólar, UF, UTM, IPC, TPM, desempleo (con variación a 12 meses).
- **Pestañas temáticas** con series curadas y proyección por regresión lineal:
  tipo de cambio, unidades reajustables, precios, actividad (IMACEC), política
  monetaria y empleo.
- **Explorador del catálogo:** buscador sobre las ~20.000 series del BCCh
  (PIB sectorial, exportaciones, agregados monetarios, tasas, etc.) con gráfico
  en vivo y descarga CSV.
- Datos en vivo con caché (6 h) y botón de actualización manual.

## Stack
`Python` · `Streamlit` · `Altair` · `pandas` · `NumPy` · API REST del Banco Central de Chile.

## Arquitectura y despliegue (AWS)
Desplegado en **infraestructura propia AWS EC2** (Amazon Linux 2023):

```
Internet ──HTTPS──> Nginx (reverse proxy, 443/80) ──> Streamlit (127.0.0.1:8501)
                         │                                   │
                   Let's Encrypt                       systemd service
                   (certbot, auto-renew)              (auto-arranque/restart)
                                                             │
                                                   API BDE Banco Central
```
- **Nginx** como proxy inverso con soporte **WebSocket** (requerido por Streamlit).
- **systemd** gestiona el proceso (arranque automático, reinicio ante fallos).
- **HTTPS** con certificado **Let's Encrypt** (certbot) y renovación automática.
- **Dominio propio** (`dgonzsim.cl`) con DNS en Cloudflare.

## Estructura
```
dashboard/
├── app.py            # aplicación Streamlit (KPIs, pestañas temáticas, explorador)
├── bcentral.py       # cliente de la API BDE del Banco Central (get_series, get_catalog)
├── requirements.txt
├── Dockerfile        # opcional: la app también es dockerizable
└── README.md
```

## Ejecutar en local
```bash
pip install -r requirements.txt
# Credenciales del Banco Central (registro gratuito en si3.bcentral.cl/Siete,
# requiere ACTIVAR el acceso a la API en el portal):
echo "BCCH_USER=tu_email" > .env
echo "BCCH_PASS=tu_clave" >> .env
streamlit run app.py
```

## Notas
- Las proyecciones (regresión lineal de tendencia) son **referenciales** y no
  constituyen asesoría de inversión.
- Las credenciales viven en `.env` (excluido del repositorio).

---
Fuente de datos: [API BDE — Banco Central de Chile](https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/index_es.htm).
