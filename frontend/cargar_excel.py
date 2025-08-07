# cargar_excel.py
import streamlit as st
import requests
from utils import obtener_token

def cargar_excel_empleados():
    st.subheader("📥 Carga de Empleados desde Excel")
    st.markdown("Sube un archivo Excel con los datos de empleados para agregarlos al sistema.")

    archivo = st.file_uploader("📂 Selecciona archivo Excel", type=["xlsx", "xls"])

    if archivo:
        if st.button("📤 Subir Excel", use_container_width=True):
            token = obtener_token()
            headers = {"Authorization": f"Bearer {token}"}

            with st.spinner("⏳ Procesando archivo..."):
                files = {"archivo": (archivo.name, archivo.getvalue())}
                response = requests.post("https://systeso-backend-production.up.railway.app/empleados/cargar_excel", headers=headers, files=files)

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if response.status_code == 200:
                    resultado = response.json()
                    st.success("✅ Archivo procesado correctamente")
                    st.markdown(f"👥 **Nuevos empleados agregados:** {resultado['insertados']}")
                    st.info(f"📌 Omitidos por duplicado: **{resultado['omitidos']}**")
                else:
                    try:
                        error = response.json().get("detail", "Error al procesar el archivo")
                    except Exception:
                        error = "Error de conexión con el servidor."
                    st.error(f"❌ {error}")
    else:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info("Sube tu archivo Excel para comenzar.")

