# utils.py
import json, base64, time
from datetime import datetime, timedelta
import streamlit as st
import extra_streamlit_components as stx

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7

# ---------- CookieManager único ----------
def _cm():
    cm = st.session_state.get("cookie_manager")
    if cm is not None:
        return cm
    # fallback si alguien llama fuera de orden (no ideal, pero evita crash)
    if "_cookie_manager_fallback" not in st.session_state:
        st.session_state["_cookie_manager_fallback"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager_fallback"]

def ensure_cookies_ready() -> None:
    """
    Hidrata CookieManager UNA sola vez y cachea los cookies para este render.
    Llama a esta función **solo en app.py** y lo más arriba posible.
    """
    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = stx.CookieManager(key="systeso_cm")

    if st.session_state.get("_cookies_cache") is None:
        cookies = st.session_state["cookie_manager"].get_all(key="cm_boot")
        if cookies is None:
            st.empty().write("🔄 Restaurando sesión...")
            st.stop()  # siguiente ciclo ya trae cookies
        st.session_state["_cookies_cache"] = cookies

# ---------- Helpers de cookie ----------
def _set_cookie(name: str, value: dict, days: int = COOKIE_DAYS):
    exp = datetime.utcnow() + timedelta(days=days)
    payload = json.dumps(value)
    try:
        _cm().set(name, payload, expires_at=exp, path="/", secure=True)
    except TypeError:
        # versiones antiguas no aceptan 'secure'
        _cm().set(name, payload, expires_at=exp, path="/")

def _delete_cookie(name: str):
    try:
        _cm().delete(name, path="/")
    except Exception:
        pass

def _read_cookie(name: str):
    cookies = st.session_state.get("_cookies_cache") or {}
    raw = cookies.get(name)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

# ---------- API de sesión ----------
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    data = {"token": token, "rol": rol, "nombre": nombre or "", "rfc": rfc or ""}
    _set_cookie(COOKIE_NAME, data, COOKIE_DAYS)
    st.session_state.update({
        "token": data["token"],
        "rol": data["rol"],
        "nombre": data["nombre"],
        "rfc": data["rfc"],
    })
    st.rerun()

def borrar_token():
    _delete_cookie(COOKIE_NAME)
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)
    st.session_state["view"] = "login"
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()

def restaurar_sesion_completa():
    """Restaura sesión desde cookie si en memoria no hay token."""
    if st.session_state.get("token"):
        return
    data = _read_cookie(COOKIE_NAME)
    if not data:
        # fuerza/respeta login si no hay cookie
        st.session_state["view"] = st.session_state.get("view", "login")
        return
    st.session_state["token"]  = data.get("token", "")
    st.session_state["rol"]    = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "Empleado")
    st.session_state["rfc"]    = data.get("rfc", "")
    if st.session_state.get("view") in (None, "", "login"):
        st.session_state["view"] = "recibos"

def obtener_token():
    tok = st.session_state.get("token")
    if tok:
        return tok
    data = _read_cookie(COOKIE_NAME)
    if not data:
        return None
    st.session_state["token"]  = data.get("token", "")
    st.session_state["rol"]    = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "")
    st.session_state["rfc"]    = data.get("rfc", "")
    return st.session_state["token"]

def obtener_rol():
    rol = st.session_state.get("rol")
    if rol:
        return rol
    tok = obtener_token()
    return st.session_state.get("rol") if tok else None

# ---------- Diagnóstico opcional de JWT ----------
def _jwt_payload(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        s = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(s.encode()).decode())
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
