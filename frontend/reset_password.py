# reset_password.py
import streamlit as st
import requests

BACKEND_BASE = "https://systeso-backend-production.up.railway.app"

def mostrar_formulario_reset(token: str):
    st.title("🔑 Restablecer Contraseña")

    # Usamos un form para submit y así evitar modificar session_state de los widgets
    with st.form("reset_form", clear_on_submit=True):
        nueva = st.text_input("Nueva contraseña", type="password", key="reset_pass")
        confirmar = st.text_input("Confirmar contraseña", type="password", key="reset_pass_confirm")
        submit = st.form_submit_button("Cambiar contraseña")

    if not submit:
        return

    # Validaciones básicas
    if not nueva or not confirmar:
        st.warning("Debes llenar ambos campos.")
        return
    if nueva != confirmar:
        st.error("Las contraseñas no coinciden.")
        return

    # Llamada al backend
    with st.spinner("Procesando..."):
        try:
            resp = requests.post(
                f"{BACKEND_BASE}/users/reset_password",
                json={"token": token, "nueva_password": nueva},
                timeout=20,
            )
        except requests.RequestException as e:
            st.error(f"Error de red: {e}")
            return

    if resp.status_code == 200:
        # Guardamos un 'flash' para mostrarlo al cargar la vista de login
        st.session_state["_flash_login"] = ("success", "Contraseña cambiada correctamente. Ya puedes iniciar sesión.")
        # Limpia los query params para que no re-entre al flujo de reset
        try:
            st.experimental_set_query_params()
        except Exception:
            pass
        # Redirige a la vista de login
        st.session_state["view"] = "login"
        st.rerun()
    else:
        detail = "Error al cambiar la contraseña."
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        st.error(detail)
