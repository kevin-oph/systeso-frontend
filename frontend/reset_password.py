# reset_password.py
import streamlit as st
import requests

BACKEND_BASE = "https://systeso-backend-production.up.railway.app"

def mostrar_formulario_reset(token: str):
    st.title("🔑 Restablecer Contraseña")

    # Form: evita tocar keys de widgets directamente
    with st.form("reset_form", clear_on_submit=True):
        nueva = st.text_input("Nueva contraseña", type="password", key="reset_pass")
        confirmar = st.text_input("Confirmar contraseña", type="password", key="reset_pass_confirm")
        submit = st.form_submit_button("Cambiar contraseña")

    if not submit:
        return

    if not nueva or not confirmar:
        st.warning("Debes llenar ambos campos."); return
    if nueva != confirmar:
        st.error("Las contraseñas no coinciden."); return

    with st.spinner("Procesando..."):
        try:
            resp = requests.post(
                f"{BACKEND_BASE}/users/reset_password",
                json={"token": token, "nueva_password": nueva},
                timeout=20,
            )
        except requests.RequestException as e:
            st.error(f"Error de red: {e}"); return

    if resp.status_code == 200:
        # Flash para login + redirección
        st.session_state["_flash_login"] = ("success", "Contraseña cambiada correctamente. Ya puedes iniciar sesión.")
        try:
            # limpiar query params (nuevo API)
            st.query_params.clear()
        except Exception:
            pass
        st.session_state["view"] = "login"
        st.rerun()
    else:
        detail = "Error al cambiar la contraseña."
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        st.error(detail)
