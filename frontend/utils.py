# utils.py
import json
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx
from streamlit_js_eval import streamlit_js_eval

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7

# ---------------------- Helpers: localStorage ----------------------
def _ls_get(key: str):
    """
    Lee localStorage. La primera pasada puede devolver None (hidratación).
    """
    try:
        return streamlit_js_eval(
            js_expressions=f"window.localStorage.getItem('{key}')",
            key="ls_get_boot",
            want_output=True,
        )
    except Exception:
        return None

def _ls_set(key: str, obj: dict):
    try:
        # Guardamos como string JSON
        payload = json.dumps(obj)
        streamlit_js_eval(
            js_expressions=f"window.localStorage.setItem('{key}', {json.dumps(payload)})",
            key="ls_set_save",
            want_output=False,
        )
    except Exception:
        pass

def _ls_del(key: str):
    try:
        streamlit_js_eval(
            js_expressions=f"window.localStorage.removeItem('{key}')",
            key="ls_del",
            want_output=False,
        )
    except Exception:
        pass

# ---------------------- Helpers: Cookie (respaldo) ----------------------
def _cookie_manager():
    if "cookie_manager" in st.session_state:
        return st.session_state["cookie_manager"]
    # Fallback (no ideal, pero evita crash si se invoca fuera de orden)
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager"]

def _cookie_set(name: str, value: dict, days: int = COOKIE_DAYS):
    expires_at = datetime.utcnow() + timedelta(days=days)
    try:
        _cookie_manager().set(
            name,
            json.dumps(value),
            expires_at=expires_at,
            path="/",      # crítico para que sea visible en toda la app
            secure=True,   # estás en https
            # HttpOnly False (por defecto) para que el componente pueda leerlo
        )
    except TypeError:
        # versiones antiguas de extra_streamlit_components no aceptan 'secure'
        _cookie_manager().set(name, json.dumps(value), expires_at=expires_at, path="/")

def _cookie_get_all():
    # Para evitar colisiones de key, solo llamamos una vez por render desde app.py.
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

def _cookie_del(name: str):
    try:
        _cookie_manager().delete(name, path="/")
    except Exception:
        pass

# ---------------------- API pública ----------------------
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    """
    Guarda token + datos en storage (localStorage + cookie) y en session_state.
    """
    payload = {
        "token": token,
        "rol": rol,
        "nombre": nombre or "",
        "rfc": rfc or "",
    }

    # 1) localStorage (persistente y estable al recargar)
    _ls_set(COOKIE_NAME, payload)

    # 2) Cookie como respaldo (por si el navegador bloquea localStorage)
    _cookie_set(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # 3) Session state inmediato
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    st.rerun()

def borrar_token():
    """
    Logout: borra localStorage + cookie y limpia session_state.
    """
    _ls_del(COOKIE_NAME)
    _cookie_del(COOKIE_NAME)

    for k in ("token", "rol", "nombre", "rfc", "_cookies_cache"):
        st.session_state.pop(k, None)
    st.rerun()

def restaurar_sesion_completa():
    """
    Si no hay sesión en memoria, intenta restaurar primero desde localStorage,
    luego desde cookie.
    """
    if st.session_state.get("token"):
        return

    # 1) Intento localStorage
    raw = _ls_get(COOKIE_NAME)
    if raw is None and not st.session_state.get("_ls_boot_rerun_done"):
        # Primer ciclo tras carga: el componente puede devolver None.
        st.session_state["_ls_boot_rerun_done"] = True
        st.rerun()
        return

    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
        if data:
            st.session_state["token"] = data.get("token", "")
            st.session_state["rol"] = data.get("rol", "")
            st.session_state["nombre"] = data.get("nombre", "Empleado")
            st.session_state["rfc"] = data.get("rfc", "")
            if st.session_state.get("view") in (None, "", "login"):
                st.session_state["view"] = "recibos"
            return

    # 2) Fallback cookie (si por alguna razón no hay localStorage)
    data = _cookie_get(COOKIE_NAME)
    if data:
        st.session_state["token"] = data.get("token", "")
        st.session_state["rol"] = data.get("rol", "")
        st.session_state["nombre"] = data.get("nombre", "Empleado")
        st.session_state["rfc"] = data.get("rfc", "")
        if st.session_state.get("view") in (None, "", "login"):
            st.session_state["view"] = "recibos"

def obtener_token():
    tok = st.session_state.get("token")
    if tok:
        return tok

    # Reintenta desde localStorage (ya hidratado por restaurar)
    raw = _ls_get(COOKIE_NAME)
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
        if data:
            st.session_state["token"] = data.get("token", "")
            st.session_state["rol"] = data.get("rol", "")
            st.session_state["nombre"] = data.get("nombre", "")
            st.session_state["rfc"] = data.get("rfc", "")
            return st.session_state["token"]

    # Fallback cookie
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

# --------- utilidades para diagnosticar/validar JWT (opcional) ----------
import base64, time
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
    return int(time.time()) >= int(exp)
