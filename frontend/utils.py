# utils.py
import json
from datetime import datetime, timedelta
import base64
import json as _json
import streamlit as st
import extra_streamlit_components as stx

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7

# ---------- JWT helpers (para diagnosticar expiración) ----------
def _b64pad(s: str) -> str:
    return s + "=" * (-len(s) % 4)

def _jwt_payload(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = _b64pad(parts[1].replace("-", "+").replace("_", "/"))
        data = base64.b64decode(payload_b64).decode("utf-8")
        return _json.loads(data)
    except Exception:
        return None

def jwt_exp_unix(token: str) -> int | None:
    p = _jwt_payload(token)
    return p.get("exp") if isinstance(p, dict) else None

def is_jwt_expired(token: str, drift_sec: int = 15) -> bool:
    exp = jwt_exp_unix(token)
    if not isinstance(exp, int):
        return True
    return int(datetime.utcnow().timestamp()) >= (exp - drift_sec)

# ---------- Cookie Manager único ----------
def cm() -> stx.CookieManager:
    """Instancia ÚNICA creada en app.py. Si falta, crea fallback."""
    mgr = st.session_state.get("cookie_manager")
    if mgr is None:
        # fallback si alguien llama antes de tiempo
        mgr = stx.CookieManager(key="systeso_cm_fallback")
        st.session_state["cookie_manager"] = mgr
    return mgr

def boot_cookies_once():
    """
    Llamar al iniciar app.py:
    - Crea CookieManager con key estable (si no existe)
    - Lee get_all() UNA sola vez y lo cachea en _cookies_cache
    - Si aún no están hidratadas las cookies => st.stop() para rerender
    """
    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = stx.CookieManager(key="systeso_cm")

    if "_cookies_cache" not in st.session_state:
        cookies = st.session_state["cookie_manager"].get_all(key="boot")
        if cookies is None:
            st.stop()  # siguiente ciclo ya viene hidratado
        st.session_state["_cookies_cache"] = cookies

def _get_cookie_value(name: str) -> str | None:
    cookies = st.session_state.get("_cookies_cache") or {}
    return cookies.get(name)

def get_auth() -> dict | None:
    raw = _get_cookie_value(COOKIE_NAME)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def set_auth(payload: dict, days: int = COOKIE_DAYS):
    """Guarda cookie persistente con path '/'. No uses sameSite aquí (lib no lo soporta)."""
    expires_at = datetime.utcnow() + timedelta(days=days)
    cm().set(COOKIE_NAME, json.dumps(payload), expires_at=expires_at, path="/")
    # actualizar cache para este render
    st.session_state["_cookies_cache"] = st.session_state.get("_cookies_cache", {})
    st.session_state["_cookies_cache"][COOKIE_NAME] = json.dumps(payload)

def clear_auth():
    cm().delete(COOKIE_NAME, path="/")
    for k in ("token", "rol", "nombre", "rfc", "_cookies_cache"):
        st.session_state.pop(k, None)
    st.rerun()

# ---------- API de alto nivel usada por app.py ----------
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    payload = {"token": token, "rol": rol, "nombre": nombre or "", "rfc": rfc or ""}
    set_auth(payload, days=COOKIE_DAYS)
    st.session_state.update(payload)
    st.rerun()

def restaurar_sesion_completa():
    if st.session_state.get("token"):
        return
    data = get_auth()
    if not data:
        return
    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "Empleado")
    st.session_state["rfc"] = data.get("rfc", "")
    # Si por alguna razón view estaba vacío o en 'login', pasar a 'recibos'
    if st.session_state.get("view") in (None, "", "login"):
        st.session_state["view"] = "recibos"

def obtener_token() -> str | None:
    tok = st.session_state.get("token")
    if tok:
        return tok
    data = get_auth()
    if not data:
        return None
    st.session_state.update({
        "token": data.get("token",""),
        "rol": data.get("rol",""),
        "nombre": data.get("nombre",""),
        "rfc": data.get("rfc",""),
    })
    return st.session_state["token"]

def obtener_rol() -> str | None:
    r = st.session_state.get("rol")
    if r:
        return r
    data = get_auth()
    if not data:
        return None
    st.session_state.update({
        "token": data.get("token",""),
        "rol": data.get("rol",""),
        "nombre": data.get("nombre",""),
        "rfc": data.get("rfc",""),
    })
    return st.session_state["rol"]

def borrar_token():
    clear_auth()
