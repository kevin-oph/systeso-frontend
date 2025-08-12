# utils.py
import json
import time
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7


# ------------- Cookie manager (una sola instancia) -------------
def _cm():
    # Si ya fue creado en app.py, úsalo
    if "cookie_manager" in st.session_state:
        return st.session_state["cookie_manager"]
    # Fallback para evitar crashes si se llama fuera de orden
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager"]


def _cookie_set(name: str, value: dict, days: int = COOKIE_DAYS):
    """Crea/actualiza el cookie con atributos adecuados."""
    expires_at = datetime.utcnow() + timedelta(days=days)
    try:
        _cm().set(
            name,
            json.dumps(value),
            expires_at=expires_at,
            path="/",      # visible en toda la app
            secure=True,   # en Railway vas por HTTPS
        )
    except TypeError:
        # versiones antiguas de la librería no aceptan 'secure'
        _cm().set(name, json.dumps(value), expires_at=expires_at, path="/")


def _cookie_get_all_cached():
    """Leemos del caché que llenas en app.py para evitar colisiones de keys."""
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


# ---------------- API pública de sesión ----------------
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    """Guarda token + datos en cookie y session_state."""
    payload = {
        "token": token,
        "rol": rol,
        "nombre": nombre or "",
        "rfc": rfc or "",
    }

    _cookie_set(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # En memoria para uso inmediato
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    st.rerun()


def borrar_token():
    """
    Logout robusto:
    - Borra y vence el cookie.
    - Inyecta un borrado por JS como plan C (variantes SameSite).
    - Limpia session_state.
    - Cambia la clave de boot del CookieManager para evitar cachés.
    """
    # Borrado estándar
    _cookie_del(COOKIE_NAME)

    # Vencer y sobreescribir con algo inválido
    try:
        _cm().set(
            COOKIE_NAME,
            "0",
            expires_at=datetime.utcnow() - timedelta(days=1),
            path="/",
            secure=True,
        )
    except Exception:
        pass

    # Plan C: intenta borrar variantes con JS
    st.components.v1.html(
        """
        <script>
          (function(){
            var n = 'systeso_auth';
            var paths = ['/', ''];
            var attrs = ['', 'SameSite=Lax', 'SameSite=Strict', 'SameSite=None; Secure'];
            for (var p of paths){
              for (var a of attrs){
                try { document.cookie = n + '=; Max-Age=0; Path=' + p + (a ? '; ' + a : ''); } catch(e) {}
              }
            }
          })();
        </script>
        """,
        height=0,
    )

    # Limpia memoria/caché
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)

    # Fuerza nueva clave de boot para el CookieManager en el próximo render
    st.session_state["cm_boot_key"] = f"boot_{int(time.time()*1000)}"

    # Vuelve al login y rerun
    st.session_state["view"] = "login"
    try:
        st.query_params.clear()
    except Exception:
        pass

    time.sleep(0.05)
    st.rerun()


def restaurar_sesion_completa():
    """
    Si no hay sesión en memoria, intenta restaurar desde cookie.
    Si la hay pero la vista sigue en 'login', la mueve a 'recibos'.
    """
    if st.session_state.get("token"):
        if st.session_state.get("view", "login") == "login":
            st.session_state["view"] = "recibos"
        return

    data = _cookie_get(COOKIE_NAME)
    if not data:
        # No hay cookie -> asegúrate de que la vista sea login
        st.session_state.pop("token", None)
        st.session_state.pop("rol", None)
        st.session_state.pop("nombre", None)
        st.session_state.pop("rfc", None)
        st.session_state["view"] = "login"
        return

    # Cookie válido -> poblar sesión
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
    data = _cookie_get(COOKIE_NAME)
    if not data:
        return None
    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "")
    st.session_state["rfc"] = data.get("rfc", "")
    return st.session_state["token"]


def obtener_rol():
    rol = st.session_state.get("rol")
    if rol:
        return rol
    tok = obtener_token()
    if not tok:
        return None
    return st.session_state.get("rol")


# --- utilidades para diagnosticar JWT (opcionales) ---
import base64

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
