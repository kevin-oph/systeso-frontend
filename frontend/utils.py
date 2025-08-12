# utils.py
import json
import time
from datetime import datetime, timedelta
import base64

import streamlit as st
import extra_streamlit_components as stx

# ---------------------- Reglas de validación ----------------------
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

# ---------------------- Constantes ----------------------
COOKIE_NAME = "systeso_auth"   # nombre del cookie
COOKIE_DAYS = 7                # duración del login (días)

# -----------------------------------------------------------------
# CookieManager
#   - En app.py tú creas UNA instancia única:
#       st.session_state["cookie_manager"] = stx.CookieManager(key="systeso_cm")
#   - En cada render lees todos los cookies UNA sola vez y los cacheas:
#       cookies = cm.get_all(key="boot")
#       st.session_state["_cookies_cache"] = cookies
# -----------------------------------------------------------------

def _cm() -> stx.CookieManager:
    """Devuelve la instancia ÚNICA de CookieManager (o crea un fallback)."""
    cm = st.session_state.get("cookie_manager")
    if cm is not None:
        return cm
    # Fallback para evitar crash si se llama fuera de orden
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager"]

def _cookie_cache() -> dict | None:
    """Devuelve la caché de cookies leída en app.py (get_all una sola vez)."""
    return st.session_state.get("_cookies_cache")

def _cookie_get(name: str) -> dict | None:
    """Lee y decodifica un cookie JSON desde la caché."""
    cookies = _cookie_cache()
    if not cookies:
        return None
    raw = cookies.get(name)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def _cookie_set(name: str, value: dict, days: int = COOKIE_DAYS) -> None:
    """Escribe cookie JSON con expiración y path correcto."""
    expires_at = datetime.utcnow() + timedelta(days=days)
    try:
        _cm().set(
            name,
            json.dumps(value),
            expires_at=expires_at,
            path="/",        # MUY IMPORTANTE: visible en toda la app
            secure=True,     # estás bajo HTTPS (Railway)
        )
    except TypeError:
        # Si la versión del paquete no acepta 'secure'
        _cm().set(name, json.dumps(value), expires_at=expires_at, path="/")

def _cookie_delete(name: str) -> None:
    """Borra el cookie usando el MISMO path con el que fue creado."""
    try:
        _cm().delete(name, path="/")
    except Exception:
        pass
    # Además lo vencemos explícitamente por si el navegador lo dejó en memoria
    try:
        _cm().set(
            name, "0",
            expires_at=datetime.utcnow() - timedelta(days=1),
            path="/",
            secure=True,
        )
    except Exception:
        pass

# ---------------------- API pública ----------------------
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None) -> None:
    """
    Guarda token + datos en cookie y en session_state.
    """
    payload = {
        "token": token,
        "rol": rol,
        "nombre": nombre or "",
        "rfc": rfc or "",
    }

    # 1) Cookie persistente
    _cookie_set(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # 2) Session state inmediato (para que la UI responda sin recargar)
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    # 3) Forzamos rerun para que el navegador “fije” el cookie
    st.rerun()

def borrar_token() -> None:
    """
    Cierra sesión:
      - Borra el cookie y lo vence
      - Limpia session_state y caché de cookies
      - Te envía al login y hace rerun
    """
    _cookie_delete(COOKIE_NAME)

    # Limpiar caché y datos en memoria
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)

    # Cambiar vista y limpiar parámetros
    st.session_state["view"] = "login"
    try:
        st.query_params.clear()
    except Exception:
        pass

    st.rerun()

def hard_logout() -> None:
    """
    Variante de logout “duro”: además de borrar cookie y memoria,
    limpia Local/SessionStorage en el navegador y recarga la página.
    Úsalo solo si quieres máxima limpieza.
    """
    _cookie_delete(COOKIE_NAME)
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)
    st.session_state["view"] = "login"

    # Limpieza de storages y reload en la misma ruta
    st.components.v1.html("""
    <script>
      try { localStorage.removeItem('systeso_auth'); } catch(e) {}
      try { sessionStorage.removeItem('systeso_auth'); } catch(e) {}
      location.replace(location.pathname);
    </script>
    """, height=0)

def restaurar_sesion_completa() -> None:
    """
    Si ya hay token en memoria, no toca nada.
    Si no hay, intenta restaurar desde cookie.
    Si no hay cookie válido, asegura vista=login y deja la sesión vacía.
    """
    if st.session_state.get("token"):
        
        if st.session_state.get("view") in (None, "", "login"):
            st.session_state["view"] = "recibos"
        return

    data = _cookie_get(COOKIE_NAME)
    if not data:
        # Asegura sesión limpia y vista en login
        for k in ("token", "rol", "nombre", "rfc"):
            st.session_state.pop(k, None)
        if st.session_state.get("view") != "login":
            st.session_state["view"] = "login"
        return

    # Restaurar sesión desde cookie
    st.session_state["token"]  = data.get("token", "")
    st.session_state["rol"]    = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "Empleado")
    st.session_state["rfc"]    = data.get("rfc", "")
    if st.session_state.get("view") in (None, "", "login"):
        st.session_state["view"] = "recibos"

def obtener_token() -> str | None:
    """
    Devuelve el token desde memoria, o lo reconstruye desde el cookie si hace falta.
    """
    tok = st.session_state.get("token")
    if tok:
        return tok

    data = _cookie_get(COOKIE_NAME)
    if not data:
        return None

    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "")
    st.session_state["rfc"] = data.get("rfc", "")
    return st.session_state["token"]

def obtener_rol() -> str | None:
    rol = st.session_state.get("rol")
    if rol:
        return rol
    tok = obtener_token()
    if not tok:
        return None
    return st.session_state.get("rol")

# --------- Utilidades para diagnosticar/validar JWT (opcional) ----------
def _jwt_payload(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception:
        return None

def jwt_exp_unix(token: str) -> int | None:
    p = _jwt_payload(token)
    return p.get("exp") if p else None

def is_jwt_expired(token: str) -> bool:
    exp = jwt_exp_unix(token)
    if not exp:
        return True
    return int(time.time()) >= int(exp)
