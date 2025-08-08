# utils.py
import json
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"   # nombre del cookie para tu app
COOKIE_DAYS = 7                # duración del login

def _cm():
    # Un único CookieManager
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager()
    return st.session_state["_cookie_manager"]

def _set_cookie(name: str, value: dict, days: int = COOKIE_DAYS):
    """
    Guarda un cookie con expiración en 'days' días.
    extra_streamlit_components acepta 'expires_at' como datetime.
    """
    expires_at = datetime.utcnow() + timedelta(days=days)
    _cm().set(name, json.dumps(value), expires_at=expires_at)

def _get_cookie(name: str):
    raw = _cm().get(name)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def _delete_cookie(name: str):
    # OJO: CookieManager.delete NO acepta 'path'
    _cm().delete(name)

def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    """
    Guarda token + datos en cookie y en session_state.
    """
    payload = {
        "token": token,
        "rol": rol,
        "nombre": nombre or "",
        "rfc": rfc or "",
    }

    # Guardar en cookie (persistente por COOKIE_DAYS)
    _set_cookie(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # Guardar en session_state para usar inmediatamente
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    # Forzamos un ciclo para que el navegador aplique el cookie
    st.rerun()

def restaurar_sesion_completa():
    """
    Si no hay sesión en memoria, intenta restaurar desde cookie.
    Llamar al inicio de app.py.
    """
    if "token" in st.session_state and st.session_state["token"]:
        return  # ya hay sesión en memoria

    data = _get_cookie(COOKIE_NAME)
    if not data:
        return

    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "Empleado")
    st.session_state["rfc"] = data.get("rfc", "")

def obtener_token():
    """
    Devuelve el token desde la sesión, o lo reconstruye desde el cookie si hace falta.
    """
    tok = st.session_state.get("token")
    if tok:
        return tok

    data = _get_cookie(COOKIE_NAME)
    if not data:
        return None

    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "")
    st.session_state["rfc"] = data.get("rfc", "")
    return st.session_state["token"]

def obtener_rol():
    """
    Similar a obtener_token, pero para el rol.
    """
    rol = st.session_state.get("rol")
    if rol:
        return rol

    data = _get_cookie(COOKIE_NAME)
    if not data:
        return None

    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "")
    st.session_state["rfc"] = data.get("rfc", "")
    return st.session_state["rol"]

def borrar_token():
    """
    Logout: borra cookie + limpia session_state.
    """
    _delete_cookie(COOKIE_NAME)
    # Limpia todos los valores de sesión relevantes
    for k in ("token", "rol", "nombre", "rfc", "_cookie_manager"):
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()
