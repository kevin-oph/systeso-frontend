# frontend/verificacion.py

import streamlit as st
import requests

def verificar_email():
    st.title("🔐 Verificación de Correo Electrónico")

    query_params = st.query_params
    token = query_params.get("token", None)

    if not token:
        st.error("❌ No se proporcionó un token de verificación en la URL.")
        return

    try:
        url = f"https://systeso-backend-production.up.railway.app/users/verificar_email?token={token}"
        response = requests.get(url)

        if response.status_code == 200:
            st.success("✅ Tu correo fue verificado correctamente.")
            st.toast("✅ Verificación exitosa. Ahora puedes iniciar sesión.")
            st.session_state.view = "login"
            st.rerun()

        else:
            try:
                detalle = response.json().get("detail", "").lower()
            except ValueError:
                detalle = "Error inesperado del servidor."


            if "expirado" in detalle or "token" in detalle:
                st.warning("⚠️ El enlace ha expirado o es inválido.")
                st.toast("❌ Token expirado o inválido. Puedes solicitar un nuevo correo.")
                st.session_state.view = "reenviar"
                st.rerun()
            else:
                st.error(f"❌ {detalle}")

    except requests.exceptions.ConnectionError:
        st.error("❌ No se pudo conectar con el servidor.")



#-----------------------------------
# Resetear contraseña
#-----------------------------------
def reset_password_frontend(token):
    st.title("🔄 Restablecer contraseña")
    nueva_password = st.text_input("Nueva contraseña", type="password")
    confirmar_password = st.text_input("Confirmar contraseña", type="password")

    if st.button("Restablecer contraseña"):
        if nueva_password != confirmar_password:
            st.error("Las contraseñas no coinciden.")
        elif len(nueva_password) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
        else:
            with st.spinner("Restableciendo..."):
                resp = requests.post(
                    "https://systeso-backend-production.up.railway.app/users/reset_password",
                    json={"token": token, "nueva_password": nueva_password}
                )
                if resp.status_code == 200:
                    st.success("Contraseña restablecida exitosamente. Inicia sesión con tu nueva contraseña.")
                    if st.button("Ir al Login"):
                        st.session_state.view = "login"
                        st.rerun()
                else:
                    st.error("No se pudo restablecer la contraseña. El token podría estar vencido o incorrecto.")