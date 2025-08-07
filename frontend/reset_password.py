import streamlit as st
import requests

def mostrar_formulario_reset(token):
    # Estado para los campos de contraseña (esto NO persiste tras recargar, pero así queda limpio al hacer rerun)
    if "reset_pass" not in st.session_state:
        st.session_state.reset_pass = ""
    if "reset_pass_confirm" not in st.session_state:
        st.session_state.reset_pass_confirm = ""

    st.title("🔑 Restablecer Contraseña")
    nueva = st.text_input("Nueva contraseña", type="password", value=st.session_state.reset_pass, key="reset_pass")
    confirmar = st.text_input("Confirmar contraseña", type="password", value=st.session_state.reset_pass_confirm, key="reset_pass_confirm")

    if st.button("Cambiar contraseña"):
        if not nueva or not confirmar:
            st.warning("Debes llenar ambos campos.")
        elif nueva != confirmar:
            st.error("Las contraseñas no coinciden.")
            st.session_state.reset_pass = ""
            st.session_state.reset_pass_confirm = ""
        else:
            with st.spinner("Procesando..."):
                resp = requests.post(
                    "systeso-backend-production.up.railway.app/users/reset_password",
                    json={"token": token, "nueva_password": nueva}  # <= RECUERDA: debe coincidir con el backend
                )
                if resp.status_code == 200:
                    st.success("Contraseña cambiada correctamente. Ya puedes iniciar sesión.")
                    st.toast("✅ Listo. Inicia sesión con tu nueva contraseña.")
                    # Limpiar campos y regresar a login
                    st.session_state.reset_pass = ""
                    st.session_state.reset_pass_confirm = ""
                    if st.button("🔐 Ir a Login"):
                        st.session_state.view = "login"
                        st.rerun()
                else:
                    detail = resp.json().get("detail", "Error al cambiar la contraseña.")
                    st.error(detail)
