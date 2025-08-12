# utils.py
import json
import time
import base64
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx
from streamlit_js_eval import streamlit_js_eval

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7


# =============== LocalStorage helpers (con claves únicas por render) ===============
def _ls_eval(js: str, want_output: bool):
    """Ejecuta JS con una key única para evitar colisiones de Streamlit."""
    seq = st.session_state.get("_ls_seq", 0) + 1
    st.session_state["_ls_seq"] = seq
    return streamlit_js_eval(js_expressions=js, key=f"ls_{seq}", want_output=want_output)

def ensure_ls_boot():
    """
    Asegura que el front ya está hidratado para usar localStorage.
    En el primer ciclo puede devolver None: cortamos y el siguiente ya está listo.
    """
    probe = _ls_eval("window.localStorage.getItem('__ls_probe__')", want_output=True)
    if probe is None:
        st.write("🔄 Restaurando sesión…")
        st.stop()

def _ls_get_json(key: str):
    val = _ls_eval(f"window.localStorage.getItem('{key}')", want_output=True)
    if val is None:  # si aún no hidrató, el caller debe haber llamado ensure_ls_boot()
        return None
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None

def _ls_set_json(key: str, obj: dict):
    # ojo: hay que pasar string JSON como string JS
    payload = json.dumps(obj)
    _ls_eval(f"window.localStorage.setItem('{key}', {json.dumps(payload)})", want_output=False)

def _ls_del(key: str):
    _ls_eval(f"window.localStorage.removeItem('{key}')", want_output=False)


# ================= Cookie helpers (respaldo) =================
def _cm():
    # Usa la instancia creada en app.py, o crea de emergencia
    if "cookie_manager" in st.session_state:
        return st.session_state["cookie_manager"]
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager"]

def _cookie_set(name: str, value: dict, days: int = COOKIE_DAYS):
    expires_at = datetime.utcnow() + timedelta(days=days)
    try:
        _cm().set(name, json.dumps(value), expires_at=expires_at, path="/", secure=True)
    except TypeError:
        _cm().set(name, json.dumps(value), expires_at=expires_at, path="/")

def _cookie_get_all_cached():
    return st.session_state.get("_cookies_cache")

def _cookie_get(name: str):
    cookies = _cookie_get_all_cached()
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
        _cm().delete(name, path="/")
    except Exception:
        pass


# ================== API pública de sesión ==================
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    """
    Guarda token + datos en localStorage (persistente) y cookie (respaldo),
    y los carga en session_state para uso inmediato.
    """
    payload = {"token": token, "rol": rol, "nombre": nombre or "", "rfc": rfc or ""}

    # 1) localStorage
    _ls_set_json(COOKIE_NAME, payload)

    # 2) Cookie (respaldo)
    _cookie_set(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # 3) Memoria inmediata
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    st.rerun()


def borrar_token():
    """
    Cierra sesión: borra localStorage y cookie y regresa a login.
    """
    # 1) localStorage
    _ls_del(COOKIE_NAME)

    # 2) Cookie
    _cookie_del(COOKIE_NAME)
    try:
        _cm().set(COOKIE_NAME, "0",
                  expires_at=datetime.utcnow() - timedelta(days=1),
                  path="/", secure=True)
    except Exception:
        pass

    # 3) Limpieza de estado y forzar nueva boot-key del CookieManager
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)
    st.session_state["cm_boot_key"] = f"boot_{int(time.time()*1000)}"

    st.session_state["view"] = "login"
    try:
        st.query_params.clear()
    except Exception:
        pass

    time.sleep(0.05)
    st.rerun()


def restaurar_sesion_completa():
    """
    Si no hay sesión en memoria, intenta restaurar desde localStorage.
    Si no existe, usa cookie de respaldo. Ajusta la vista a 'recibos' si procede.
    """
    if st.session_state.get("token"):
        if st.session_state.get("view", "login") == "login":
            st.session_state["view"] = "recibos"
        return

    # 1) Primero localStorage (ya debe estar hidratado por ensure_ls_boot)
    data = _ls_get_json(COOKIE_NAME)
    if not data:
        # 2) Respaldo: cookie
        data = _cookie_get(COOKIE_NAME)

    if not data:
        # Nada que restaurar
        for k in ("token", "rol", "nombre", "rfc"):
            st.session_state.pop(k, None)
        st.session_state["view"] = "login"
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
    data = _ls_get_json(COOKIE_NAME)
    if not data:
        data = _cookie_get(COOKIE_NAME)
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
    if not tok:
        return None
    return st.session_state.get("rol")


# ---- utilidades de JWT (opcional para debug) ----
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
