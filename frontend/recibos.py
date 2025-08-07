import streamlit as st
import requests
import pandas as pd
import base64
from streamlit_pdf_viewer import pdf_viewer
from utils import obtener_token


def mostrar_recibos():
    token = obtener_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("https://systeso-backend-production.up.railway.app/recibos/", headers=headers)

    if response.status_code != 200:
        st.error("Error al obtener recibos")
        return

    recibos = response.json()

    if not recibos:
        st.info("No hay recibos disponibles.")
        return

    st.subheader("📁 Consulta tus Recibos de Nómina")
    st.markdown("Filtra por año, mes y selecciona un recibo quincenal:")

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

