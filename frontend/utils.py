# utils.py
import streamlit as st

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

def guardar_token(token, rol, nombre=None, rfc=None):
    """Guarda todo solo en la sesión del navegador actual."""
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    if nombre is not None:
        st.session_state["nombre"] = nombre
    if rfc is not None:
        st.session_state["rfc"] = rfc

def restaurar_sesion_completa():
    """No leer de archivos ni variables globales. Cada navegador tiene su propia sesión."""
    # Si quisieras persistir entre recargas del MISMO navegador, usar cookies del navegador con una librería;
    # NO uses archivos en el servidor (rompe el aislamiento entre usuarios).
    return

def obtener_token():
    return st.session_state.get("token")

def obtener_rol():
    return st.session_state.get("rol")

def borrar_token():
    # Elimina solo lo relacionado con auth (no limpies todo para no romper otros estados de UI)
    for k in ["token", "rol", "nombre", "rfc"]:
        st.session_state.pop(k, None)
    # Por si cacheaste datos por usuario:
    try:
        st.cache_data.clear()
    except Exception:
        pass
