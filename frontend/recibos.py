import streamlit as st
import requests
import pandas as pd
import base64
from streamlit_pdf_viewer import pdf_viewer
from utils import obtener_token

# === Meses tal y como los muestras en la UI ===
MESES_ORDEN = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sept", "Oct", "Nov", "Dic"]

# Normalización desde los textos del periodo (vienen como "01-ene.-2025")
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
    """De '01-ene.-2025 al 15-ene.-2025' devuelve 'Ene'."""
    try:
        fecha_inicio = periodo.split(" al ")[0]
        _, mes_token, _ = fecha_inicio.split("-")
        m = mes_token.strip().lower()
        return MESES_MAP.get(m, m.capitalize())
    except Exception:
        return "Otro"

def _extraer_anio(periodo: str) -> str:
    try:
        fecha_inicio = periodo.split(" al ")[0]
        return fecha_inicio.split("-")[-1]
    except Exception:
        return "0000"

def _descargar_pdf_bytes(pdf_endpoint: str, headers: dict):
    """Descarga el PDF (siguiendo redirects) y valida tipo."""
    try:
        r = requests.get(pdf_endpoint, headers=headers, allow_redirects=True, timeout=60)
    except Exception as e:
        return None, {"exception": type(e).__name__, "detail": str(e)}

    if r.status_code != 200:
        return None, {
            "status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
            "body_snippet": r.text[:300],
        }

    content_type = (r.headers.get("content-type") or "").lower()
    if not ("application/pdf" in content_type or r.content.startswith(b"%PDF-")):
        return None, {
            "error": "not_pdf",
            "content_type": content_type,
            "first_bytes": r.content[:16],
        }

    return r.content, None

def _mostrar_pdf_centrado(pdf_bytes: bytes, max_width_px: int = 1200, height_vh: int = 88):
    """
    1) Intento con streamlit_pdf_viewer (PDF.js interno).
    2) Fallback con <object data="data:application/pdf;base64,..."> centrado.
    """
    try:
        pdf_viewer(pdf_bytes, width=max_width_px, height=1200)
        return
    except Exception:
        pass

    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    html = f"""
    <div style="display:flex;justify-content:center;">
      <object data="data:application/pdf;base64,{b64}#zoom=page-width"
              type="application/pdf"
              style="width:100%;max-width:{max_width_px}px;height:{height_vh}vh;border:none;
                     border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
        <p>No se pudo mostrar el PDF. <a download="recibo.pdf" href="data:application/pdf;base64,{b64}">Descargar PDF</a></p>
      </object>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# =========================== PANTALLA RECIBOS ===========================
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

    # 2) Filtros (Año / Mes / Período) — SIN CAMBIOS VISUALES
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
        meses_disp = [m for m in MESES_ORDEN if m in meses_presentes] or sorted(list(meses_presentes))
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

    # 3) Descargar bytes y mostrar grande/centrado
    pdf_endpoint = f"https://systeso-backend-production.up.railway.app/recibos/{seleccionado['id']}/file"
    pdf_bytes, err = _descargar_pdf_bytes(pdf_endpoint, headers)

    if err:
        st.error("No se pudo cargar el archivo PDF.")
        st.write({"endpoint": pdf_endpoint, **err})
        return

    # Mantén tu layout; sólo el visor es más ancho.
    col_izq, col_ctr, col_der = st.columns([1, 5, 1])
    with col_ctr:
        _mostrar_pdf_centrado(pdf_bytes, max_width_px=1200, height_vh=88)

# =========================== SUBIDA DE ZIP (admin) ===========================
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

    st.caption(f"Nombre: {archivo.name} · Tamaño: {len(archivo.getvalue())/1024/1024:.2f} MB")

    if st.button("🚀 Subir ZIP", use_container_width=True):
        with st.spinner("⏳ Subiendo y procesando..."):
            files = {"archivo": (archivo.name, archivo.getvalue(), "application/zip")}
            try:
                resp = requests.post(
                    "https://systeso-backend-production.up.railway.app/recibos/upload_zip",
                    headers=headers,
                    files=files,
                    timeout=120,
                    allow_redirects=True
                )
            except requests.RequestException as e:
                st.error("❌ No se pudo conectar con el backend.")
                st.write({"exception": e.__class__.__name__, "detail": str(e)})
                return

        if resp.status_code != 200:
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

        data = resp.json()
        st.success("✅ ZIP procesado correctamente")
        st.json(data)
        if isinstance(data, dict) and "reparados" in data:
            st.caption(f"Reparados: {data.get('reparados')} · Nuevos: {data.get('nuevo')} · Duplicados: {data.get('duplicados')}")
