import streamlit as st
import requests
import pandas as pd
import base64
from streamlit_pdf_viewer import pdf_viewer
from utils import obtener_token

# Etiquetas tal como las quieres ver en la UI
MESES_ORDEN = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sept", "Oct", "Nov", "Dic"]

# Normalización desde los textos del periodo (que vienen como "01-ene.-2025")
MESES_MAP = {
    "ene.": "Ene", "ene": "Ene",
    "feb.": "Feb", "feb": "Feb",
    "mar.": "Mar", "mar": "Mar",
    "abr.": "Abr", "abr": "Abr",
    "may.": "May",
    "jun.": "Jun", "jun": "Jun",
    "jul.": "Jul", "jul": "Jul",
    "ago.": "Ago", "ago": "Ago",
    "sept.": "Sept", "sep.": "Sept", "sept": "Sept", "sep": "Sept",
    "oct.": "Oct", "oct": "Oct",
    "nov.": "Nov", "nov": "Nov",
    "dic.": "Dic", "dic": "Dic",
}

def _extraer_mes(periodo: str) -> str:
    """
    Devuelve el mes normalizado para que coincida con MESES_ORDEN.
    Ej: "01-ene.-2025 al 15-ene.-2025" -> "Ene"
    """
    try:
        fecha_inicio = periodo.split(" al ")[0]          # "01-ene.-2025"
        _, mes_token, _ = fecha_inicio.split("-")        # "ene."
        m = mes_token.strip().lower()
        return MESES_MAP.get(m, m.capitalize())
    except Exception:
        return "Otro"

def _extraer_anio(periodo: str) -> str:
    try:
        fecha_inicio = periodo.split(" al ")[0]          # "01-ene.-2025"
        return fecha_inicio.split("-")[-1]               # "2025"
    except Exception:
        return "0000"

def mostrar_recibos():
    token = obtener_token()
    if not token:
        st.error("No hay token. Inicia sesión.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 1) Traer lista de recibos
    resp = requests.get(
        "https://systeso-backend-production.up.railway.app/recibos/",
        headers=headers
    )
    if resp.status_code != 200:
        st.error("Error al obtener recibos")
        st.write({
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "body": resp.text[:300],
        })
        return

    recibos = resp.json()
    if not recibos:
        st.info("No hay recibos disponibles.")
        return

    # 2) Filtros (Año / Mes / Período) — MISMA UI DE SIEMPRE
    df = pd.DataFrame(recibos)
    df["anio"] = df["periodo"].apply(_extraer_anio)
    df["mes"]  = df["periodo"].apply(_extraer_mes)

    st.subheader("📁 Consulta tus Recibos de Nómina")
    st.markdown("Filtra por año, mes y selecciona un recibo quincenal:")

    col_anio, col_mes, col_periodo = st.columns([1, 1, 2])

    with col_anio:
        anios = sorted(df["anio"].unique(), reverse=True)
        anio_filtro = st.selectbox("📅 Filtrar por año:", options=anios)

    with col_mes:
        meses_presentes = set(df.loc[df["anio"] == anio_filtro, "mes"])
        # Ordenar usando MESES_ORDEN para que siempre se vea en orden calendario
        meses_disp = [m for m in MESES_ORDEN if m in meses_presentes]
        if not meses_disp:
            meses_disp = sorted(list(meses_presentes))
        mes_filtro = st.selectbox("📅 Filtrar por mes:", options=meses_disp)

    df_filtro = df[(df["anio"] == anio_filtro) & (df["mes"] == mes_filtro)]
    if df_filtro.empty:
        st.warning("No hay recibos para ese filtro.")
        return

    with col_periodo:
        seleccionado = st.selectbox(
            "📁 Elige un periodo:",
            options=df_filtro.to_dict("records"),
            format_func=lambda r: f"{r['periodo']} — {r['nombre_archivo']}",
        )

    if not seleccionado:
        return

    # 3) Pedir el PDF (seguirá redirect 307 si viene de S3/B2)
    pdf_url = f"https://systeso-backend-production.up.railway.app/recibos/{seleccionado['id']}/file"
    pdf_response = requests.get(pdf_url, headers=headers, allow_redirects=True)

    # 4) Diagnóstico claro si falla (NO cambia la UI, solo muestra detalle)
    if pdf_response.status_code != 200:
        st.error("No se pudo cargar el archivo PDF.")
        st.write({
            "pdf_url": pdf_url,
            "status": pdf_response.status_code,
            "content_type": pdf_response.headers.get("content-type",""),
            "body": pdf_response.text[:300],
        })
        return

    # 5) Validar que realmente sea PDF (cabecera + magic bytes)
    content_type = pdf_response.headers.get("content-type","").lower()
    es_pdf = "application/pdf" in content_type and pdf_response.content.startswith(b"%PDF-")
    if not es_pdf:
        st.error("El servidor no devolvió un PDF válido.")
        st.write({"content_type": content_type, "primeros_16_bytes": pdf_response.content[:16]})
        return

    # 6) Mostrar PDF con el viewer (con fallback a iframe)
    try:
        pdf_viewer(pdf_response.content, width=1000, height=900)
    except Exception:
        b64 = base64.b64encode(pdf_response.content).decode("utf-8")
        st.markdown(
            f"<iframe src='data:application/pdf;base64,{b64}' width='100%' height='900' style='border:none;'></iframe>",
            unsafe_allow_html=True
        )

def subir_zip():
    token = obtener_token()
    if not token:
        st.error("No hay token. Inicia sesión.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    st.subheader("📤 Carga de recibos quincenales")
    st.markdown("Aquí podrás subir tus recibos quincenalmente para mandárselos a cada uno de los trabajadores del ayuntamiento.")

    archivo = st.file_uploader("📁 Selecciona archivo ZIP con recibos", type="zip")

    if not archivo:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(" Selecciona un archivo ZIP para comenzar.")
        return

    # Info del archivo (por si hay problemas de tamaño)
    st.caption(f"Nombre: {archivo.name} · Tamaño: {len(archivo.getvalue())/1024/1024:.2f} MB")

    if st.button("🚀 Subir ZIP", use_container_width=True):
        with st.spinner("⏳ Subiendo y procesando..."):
            files = {
                "archivo": (archivo.name, archivo.getvalue(), "application/zip")
            }

            try:
                # timeout generoso para uploads
                resp = requests.post(
                    "https://systeso-backend-production.up.railway.app/recibos/upload_zip",
                    headers=headers,
                    files=files,
                    timeout=120,           # súbelo si tu ZIP es muy grande o la red lenta
                    allow_redirects=True
                )
            except requests.RequestException as e:
                st.error("❌ No se pudo conectar con el backend.")
                st.write({"exception": e.__class__.__name__, "detail": str(e)})
                return

        # Si no es 200, mostramos diagnóstico detallado (sin depender de JSON)
        if resp.status_code != 200:
            detail = None
            try:
                detail = resp.json()
            except Exception:
                detail = {
                    "status": resp.status_code,
                    "headers": dict(resp.headers),
                    "body_snippet": resp.text[:500],
                }

            st.error("❌ Error al subir ZIP")
            st.write(detail)
            return

        # OK
        data = resp.json()
        st.success("✅ ZIP procesado correctamente")
        st.json(data)
        # pista rápida para ver si ‘reparados’ arregló rutas antiguas
        if isinstance(data, dict) and "reparados" in data:
            st.caption(f"Reparados: {data.get('reparados')} · Nuevos: {data.get('nuevo')} · Duplicados: {data.get('duplicados')}")
