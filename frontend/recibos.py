import streamlit as st
import requests
import pandas as pd
import base64
from streamlit_pdf_viewer import pdf_viewer
from utils import obtener_token


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

    # Procesar y normalizar datos
    def formatear_nombre(periodo):
        try:
            fecha_inicio = periodo.split(" al ")[0]
            dia, mes, anio = fecha_inicio.split("-")
            mes_nombre = {
                "01": "Enero", "02": "Febrero", "03": "Marzo",
                "04": "Abril", "05": "Mayo", "06": "Junio",
                "07": "Julio", "08": "Agosto", "09": "Septiembre",
                "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
            }.get(mes, mes)
            quincena = "1er Quincena" if int(dia) <= 15 else "2da Quincena"
            return f"Recibo de Nómina, {mes_nombre} {anio} ({quincena})"
        except:
            return periodo

    def extraer_mes(periodo):
        try:
            fecha_inicio = periodo.split(" al ")[0]
            _, mes, _ = fecha_inicio.split("-")
            return {
                "01": "Enero", "02": "Febrero", "03": "Marzo",
                "04": "Abril", "05": "Mayo", "06": "Junio",
                "07": "Julio", "08": "Agosto", "09": "Septiembre",
                "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
            }.get(mes, mes)
        except:
            return "Otro"

    def extraer_anio(periodo):
        try:
            fecha_inicio = periodo.split(" al ")[0]
            _, _, anio = fecha_inicio.split("-")
            return anio
        except:
            return "Otro"

    df = pd.DataFrame(recibos)
    df["quincena_legible"] = df["periodo"].apply(formatear_nombre)
    df["mes"] = df["periodo"].apply(extraer_mes)
    df["anio"] = df["periodo"].apply(extraer_anio)

    col1, col2, col3 = st.columns(3)
    with col1:
        anio_filtro = st.selectbox("📅 Filtrar por año:", options=["2025", "2026", "2027"])
    with col2:
        mes_filtro = st.selectbox("📆 Filtrar por mes:", options=sorted(df["mes"].unique()))

    df_filtrado = df[(df["anio"] == anio_filtro) & (df["mes"] == mes_filtro)]

    if df_filtrado.empty:
        st.warning("No hay recibos disponibles para la combinación seleccionada.")
        return

    with col3:
        seleccion = st.selectbox("🗂️ Elige un periodo:", options=df_filtrado.index,
                                 format_func=lambda idx: df_filtrado.loc[idx, "quincena_legible"])

    selected = df_filtrado.loc[seleccion]

    # Obtener PDF
    pdf_response = requests.get(
        f"https://systeso-backend-production.up.railway.app/recibos/{selected['id']}/file",
        headers=headers
    )

    if pdf_response.status_code != 200:
        st.error("No se pudo cargar el archivo PDF.")
        return

    st.markdown(f"### {selected['quincena_legible']}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col3:
        st.download_button(
            label="📅 Descargar recibo",
            data=pdf_response.content,
            file_name=selected["nombre_archivo"],
            mime="application/pdf"
        )

    # Vista previa PDF
    with st.container():
        st.markdown(
            f"""
            <iframe src="data:application/pdf;base64,{base64.b64encode(pdf_response.content).decode('utf-8')}"
                    width="100%" height="1000px" style="border:none;"></iframe>
            """,
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

