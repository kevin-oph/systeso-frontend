import streamlit as st
import requests
import pandas as pd
import base64
from streamlit_pdf_viewer import pdf_viewer
from utils import obtener_token


MESES_ORDEN = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sept", "Oct", "Nov", "Dic"]

def _extraer_mes(periodo: str) -> str:
    try:
        fecha_inicio = periodo.split(" al ")[0]  # "01-ene.-2025"
        _, mes, _ = fecha_inicio.split("-")
        return mes.strip().lower()  # ej. "ene."
    except Exception:
        return "otro"

def _extraer_anio(periodo: str) -> str:
    try:
        fecha_inicio = periodo.split(" al ")[0]
        return fecha_inicio.split("-")[-1]  # ej. "2025"
    except Exception:
        return "0000"

def mostrar_recibos():
    token = obtener_token()
    if not token:
        st.error("No hay token. Inicia sesión.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 1) Traer lista de recibos
<<<<<<< HEAD
    resp = requests.get("https://systeso-backend-production.up.railway.app/recibos/", headers=headers)
    if resp.status_code != 200:
        st.error("Error al obtener recibos")
        st.write({"status": resp.status_code, "body": resp.text[:300]})
        return

    data = resp.json()
    if not data:
=======
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
>>>>>>> 8211d8368335bf8e26de08f76d84ec508a9d20c8
        st.info("No hay recibos disponibles.")
        return

    # 2) Filtros (Año / Mes / Período)
    df = pd.DataFrame(data)
    df["anio"] = df["periodo"].apply(_extraer_anio)
    df["mes"]  = df["periodo"].apply(_extraer_mes)

    st.subheader("📁 Consulta tus Recibos de Nómina")
    st.markdown("Selecciona un recibo quincenal:")

    # 2) Selector simple (rápido para probar). Luego si quieres volvemos a meter filtros por año/mes.
    seleccionado = st.selectbox(
        "Elige un periodo:",
        options=recibos,
        format_func=lambda r: f"{r['periodo']} — {r['nombre_archivo']}",
        index=0
    )

    if not seleccionado:
        return

    # 3) Pedir el PDF
    pdf_url = f"https://systeso-backend-production.up.railway.app/recibos/{seleccionado['id']}/file"
    pdf_response = requests.get(pdf_url, headers=headers)

    # 4) Diagnóstico VERBOSO si falla
    if pdf_response.status_code != 200:
        st.error("No se pudo cargar el archivo PDF.")
        st.write({
            "pdf_url": pdf_url,
            "status": pdf_response.status_code,
            "content_type": pdf_response.headers.get("content-type",""),
            "body": pdf_response.text[:300],
        })
        st.stop()

    # 5) Validar que realmente sea PDF (cabecera y magic bytes)
    content_type = pdf_response.headers.get("content-type", "").lower()
    es_pdf_header = "application/pdf" in content_type
    es_pdf_magic = pdf_response.content[:5] == b"%PDF-"
    if not (es_pdf_header and es_pdf_magic):
        st.error("El backend no devolvió un PDF válido.")
        st.write({
            "content_type": content_type,
            "primeros_16_bytes": pdf_response.content[:16],
        })
        st.stop()

    # 6) Mostrar PDF con el viewer (y fallback a iframe)
    try:
        from streamlit_pdf_viewer import pdf_viewer
        pdf_viewer(pdf_response.content, width=1000, height=900)  # acepta bytes
    except Exception as e:
        st.warning(f"No se pudo usar streamlit_pdf_viewer ({e}). Mostrando en iframe.")
        import base64
        b64 = base64.b64encode(pdf_response.content).decode("utf-8")
        st.markdown(
            f"<iframe src='data:application/pdf;base64,{b64}' width='100%' height='900' style='border:none;'></iframe>",
            unsafe_allow_html=True
        )

    col_anio, col_mes, col_periodo = st.columns([1, 1, 2])

    with col_anio:
        anios = sorted(df["anio"].unique(), reverse=True)
        anio_filtro = st.selectbox("📅 Filtrar por año:", options=anios)

    with col_mes:
        meses_disp = [m for m in MESES_ORDEN if m in set(df.loc[df["anio"]==anio_filtro, "mes"])]
        if not meses_disp:
            meses_disp = sorted(df.loc[df["anio"]==anio_filtro, "mes"].unique())
        mes_filtro = st.selectbox("📅 Filtrar por mes:", options=meses_disp)

    df_filtro = df[(df["anio"]==anio_filtro) & (df["mes"]==mes_filtro)]
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

    # 3) Pedir el PDF (seguirá redirect 307 si viene de S3)
    pdf_url = f"https://systeso-backend-production.up.railway.app/recibos/{seleccionado['id']}/file"
    pdf_response = requests.get(pdf_url, headers=headers, allow_redirects=True)

    # 4) Diagnóstico si falla
    if pdf_response.status_code != 200:
        st.error("No se pudo cargar el archivo PDF.")
        st.write({
            "pdf_url": pdf_url,
            "status": pdf_response.status_code,
            "content_type": pdf_response.headers.get("content-type",""),
            "body": pdf_response.text[:300],
        })
        return

    # 5) Validar PDF y mostrar
    content_type = pdf_response.headers.get("content-type","").lower()
    es_pdf = "application/pdf" in content_type and pdf_response.content.startswith(b"%PDF-")
    if not es_pdf:
        st.error("El servidor no devolvió un PDF válido.")
        st.write({"content_type": content_type, "primeros_16_bytes": pdf_response.content[:16]})
        return

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
    headers = {"Authorization": f"Bearer {token}"}

    st.subheader("📤 Carga de recibos quincenales")
    st.markdown("Aquí podrás subir tus recibos quincenalmente para mandárselos a cada uno de los trabajadores del ayuntamiento.")

    archivo = st.file_uploader("📁 Selecciona archivo ZIP con recibos", type="zip")

    if archivo:
        if st.button("🚀 Subir ZIP", use_container_width=True):
            with st.spinner("⏳ Procesando archivo..."):
                files = {"archivo": (archivo.name, archivo.getvalue())}
                response = requests.post("https://systeso-backend-production.up.railway.app/recibos/upload_zip", headers=headers, files=files)

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if response.status_code == 200:
                    st.success("✅ ZIP procesado correctamente")
                    st.json(response.json())
                else:
                    try:
                        error = response.json().get("detail", "Error desconocido al subir ZIP")
                    except Exception:
                        error = "Error al conectar con el servidor."
                    st.error(f"❌ {error}")
    else:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(" Selecciona un archivo ZIP para comenzar.")

