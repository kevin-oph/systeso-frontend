# utils.py
import time
import streamlit as st
import extra_streamlit_components as stx

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 días

def _cookie_manager():
    # Instancia única por sesión de Streamlit; debe “renderizarse”
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager()
    return st.session_state.cookie_manager

def init_auth_cookies():
    """
    Llama a esta función una vez al inicio (en app.py) para
    hidratar st.session_state desde la cookie si existe.
    """
    cm = _cookie_manager()
    # La primera ejecución del componente puede no tener cookies listas todavía.
    # Intentamos leer un par de veces (rápido) para evitar un None fugaz.
    token_pack = None
    for _ in range(2):
        token_pack = cm.get(COOKIE_NAME)
        if token_pack:
            break
        time.sleep(0.05)

    if token_pack and isinstance(token_pack, dict):
        st.session_state["token"] = token_pack.get("token")
        st.session_state["rol"] = token_pack.get("rol")
        st.session_state["nombre"] = token_pack.get("nombre")
        st.session_state["rfc"] = token_pack.get("rfc")

def guardar_token(token, rol, nombre=None, rfc=None):
    """Guarda en session_state y también en cookie del NAVEGADOR actual."""
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    if nombre is not None:
        st.session_state["nombre"] = nombre
    if rfc is not None:
        st.session_state["rfc"] = rfc

    cm = _cookie_manager()
    cm.set(
        COOKIE_NAME,
        {
            "token": token,
            "rol": rol,
            "nombre": st.session_state.get("nombre"),
            "rfc": st.session_state.get("rfc"),
        },
        max_age=COOKIE_MAX_AGE,
        path="/",
        secure=True,   # usa HTTPS (en Railway sí)
    )

def restaurar_sesion_completa():
    """Ya no usa archivos; init_auth_cookies() hace la hidratación desde cookie."""
    return

def obtener_token():
    return st.session_state.get("token")

def obtener_rol():
    return st.session_state.get("rol")

def borrar_token():
    # Limpia session_state
    for k in ["token", "rol", "nombre", "rfc"]:
        st.session_state.pop(k, None)
    # Borra cookie
    cm = _cookie_manager()
    cm.delete(COOKIE_NAME, path="/")
    # Limpia caches per-user si las usas
    try:
        st.cache_data.clear()
    except Exception:
        pass
