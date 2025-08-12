# utils.py
import json
from datetime import datetime, timedelta
import time

import streamlit as st
import extra_streamlit_components as stx

# ---------------- Reglas de validación ----------------
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

# ---------------- Config de sesión ----------------
COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7  # días de validez del login

# ======================================================
# ===============  HELPER: COOKIE MANAGER ==============
# ======================================================

def _cm():
    """
    Devuelve la instancia ÚNICA del CookieManager creada en app.py.
    Si se llama fuera de orden, crea una de respaldo con otra key.
    """
    if "cookie_manager" in st.session_state:
        return st.session_state["cookie_manager"]
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager"]

def _cookie_get_all():
    """Lee el caché de cookies cargado en app.py."""
    return st.session_state.get("_cookies_cache")

def _cookie_get(name: str):
    cookies = _cookie_get_all()
    if not cookies:
        return None
    raw = cookies.get(name)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def _cookie_set(name: str, value: dict, days: int = COOKIE_DAYS):
    """
    Guarda un cookie JSON con expiración y path raíz.
    """
    expires_at = datetime.utcnow() + timedelta(days=days)
    val = json.dumps(value)
    cm = _cm()
    try:
        cm.set(name, val, expires_at=expires_at, path="/", secure=True)
    except TypeError:
        # versiones antiguas del componente no aceptan "secure"
        cm.set(name, val, expires_at=expires_at, path="/")

def _cookie_delete(name: str):
    """
    Borra el cookie usando el mismo path. Reintenta venciendo en el pasado.
    """
    cm = _cm()
    try:
        cm.delete(name, path="/")
    except Exception:
        pass
    try:
        cm.set(name, "0", expires_at=datetime.utcnow() - timedelta(days=1), path="/")
    except Exception:
        pass

# ======================================================
# ===============  API PÚBLICA DE SESIÓN ===============
# ======================================================

def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    """
    Guarda token + datos en cookie y en session_state y hace rerun.
    """
    payload = {
        "token": token,
        "rol": rol,
        "nombre": nombre or "",
        "rfc": rfc or "",
    }

    _cookie_set(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # Sesión en memoria para uso inmediato
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    st.rerun()

def restaurar_sesion_completa():
    """
    Si no hay sesión en memoria, intenta restaurar desde el cookie (cargado en app.py).
    No usa localStorage para evitar bucles y depender solo de cookie (estable).
    """
    if st.session_state.get("token"):
        return  # ya hay sesión

    data = _cookie_get(COOKIE_NAME)
    if not data:
        # No hay cookie válido -> asegurar estado 'no autenticado'
        for k in ("token", "rol", "nombre", "rfc"):
            st.session_state.pop(k, None)
        if st.session_state.get("view") != "login":
            st.session_state["view"] = "login"
        return

    # Poblar sesión desde cookie
    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "Empleado")
    st.session_state["rfc"] = data.get("rfc", "")
    if st.session_state.get("view") in (None, "", "login"):
        st.session_state["view"] = "recibos"

def obtener_token():
    """
    Devuelve el token desde memoria o, si falta, desde el cookie ya bootstrapeado.
    """
    tok = st.session_state.get("token")
    if tok:
        return tok

    data = _cookie_get(COOKIE_NAME)
    if data:
        st.session_state["token"] = data.get("token", "")
        st.session_state["rol"] = data.get("rol", "")
        st.session_state["nombre"] = data.get("nombre", "")
        st.session_state["rfc"] = data.get("rfc", "")
        return st.session_state["token"]

    return None

def obtener_rol():
    rol = st.session_state.get("rol")
    if rol:
        return rol
    tok = obtener_token()
    if not tok:
        return None
    return st.session_state.get("rol")

def borrar_token():
    """
    Logout: borra cookie + limpia session_state + cambia la clave de boot y forzar rerun.
    """
    _cookie_delete(COOKIE_NAME)

    # Limpia cachés y sesión
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)

    # Rompe el caché de get_all() del próximo ciclo
    st.session_state["cm_boot_key"] = f"boot_{int(time.time() * 1000)}"

    # Volver a login
    st.session_state["view"] = "login"
    try:
        st.query_params.clear()
    except Exception:
        pass

    st.rerun()

# ---------- utilidades JWT de diagnóstico (opcionales) ----------
import base64, time as _time

def _jwt_payload(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception:
        return None

def jwt_exp_unix(token: str):
    p = _jwt_payload(token)
    return p.get("exp") if p else None

def is_jwt_expired(token: str) -> bool:
    exp = jwt_exp_unix(token)
    if not exp:
        return True
    return int(_time.time()) >= int(exp)
