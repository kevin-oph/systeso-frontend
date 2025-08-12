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

# =========================================================
# LocalStorage helpers
# =========================================================
def _ls_get(key: str):
    """Lee localStorage. En el primer render puede devolver None."""
    try:
        return streamlit_js_eval(
            js_expressions=f"window.localStorage.getItem('{key}')",
            key="ls_get_boot",
            want_output=True,
        )
    except Exception:
        return None

def _ls_set(key: str, obj: dict):
    """Escribe en localStorage (vía streamlit_js_eval)."""
    try:
        payload = json.dumps(obj)
        streamlit_js_eval(
            js_expressions=f"window.localStorage.setItem('{key}', {json.dumps(payload)})",
            key="ls_set_save",
            want_output=False,
        )
    except Exception:
        pass

def _ls_set_fallback_js(key: str, obj: dict):
    """Segundo intento: inyecta <script> que guarda en localStorage y también un cookie JS."""
    payload = json.dumps(obj)
    max_age = COOKIE_DAYS * 24 * 3600
    st.components.v1.html(
        f"""
        <script>
          try {{
            localStorage.setItem('{key}', {json.dumps(payload)});
          }} catch (e) {{}}
          try {{
            document.cookie = '{COOKIE_NAME}=' + encodeURIComponent({json.dumps(payload)}) +
                              '; Max-Age={max_age}; Path=/; SameSite=Strict; Secure';
          }} catch (e) {{}}
        </script>
        """,
        height=0,
    )

def _ls_del(key: str):
    try:
        streamlit_js_eval(
            js_expressions=f"window.localStorage.removeItem('{key}')",
            key="ls_del",
            want_output=False,
        )
    except Exception:
        pass

# =========================================================
# Cookie helpers (respaldo)
# =========================================================
def _cookie_manager():
    if "cookie_manager" in st.session_state:
        return st.session_state["cookie_manager"]
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
            path="/",
            secure=True,   # en Railway es https
        )
    except TypeError:
        _cookie_manager().set(name, json.dumps(value), expires_at=expires_at, path="/")

def _cookie_get_all():
    # Solo se llena una vez por render en app.py
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

# =========================================================
# API pública
# =========================================================
def guardar_token(token: str, rol: str, nombre: str | None = None, rfc: str | None = None):
    """
    Guarda token + datos en localStorage (robusto) y cookie (respaldo), y en session_state.
    """
    payload = {
        "token": token,
        "rol": rol,
        "nombre": nombre or "",
        "rfc": rfc or "",
    }

    # 1) localStorage por dos vías (eval + fallback JS)
    _ls_set(COOKIE_NAME, payload)
    _ls_set_fallback_js(COOKIE_NAME, payload)

    # 2) Cookie de respaldo
    _cookie_set(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # 3) Memoria inmediata
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    # Pequeña pausa para que el script escriba y luego rerun
    time.sleep(0.05)
    st.rerun()

def borrar_token():
    """
    Cierra sesión limpiando localStorage, cookies (varias variantes) y session_state.
    """
    # localStorage
    _ls_del(COOKIE_NAME)

    # cookie manager
    cm = st.session_state.get("cookie_manager")
    if cm:
        try:
            cm.delete(COOKIE_NAME, path="/")
        except Exception:
            pass
        try:
            cm.set(
                COOKIE_NAME,
                "0",
                expires_at=datetime.utcnow() - timedelta(days=1),
                path="/",
                secure=True,
            )
        except Exception:
            pass

    # Barrido JS de cookies
    st.components.v1.html(
        """
        <script>
          (function(){
            var n='systeso_auth';
            var paths=['/',''];
            var attrs=['','SameSite=Lax','SameSite=Strict','SameSite=None; Secure'];
            for (var p of paths){
              for (var a of attrs){
                try { document.cookie = n + '=; Max-Age=0; Path=' + p + (a?'; '+a:''); } catch(e){}
              }
            }
            try { localStorage.removeItem('systeso_auth'); } catch(e){}
          })();
        </script>
        """,
        height=0,
    )

    # limpiar memoria/caché
    st.session_state.pop("_cookies_cache", None)
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)

    st.session_state["view"] = "login"
    try:
        st.query_params.clear()
    except Exception:
        pass

    time.sleep(0.05)
    st.rerun()

def restaurar_sesion_completa():
    """
    1) Si ya hay token en session_state, no hace nada.
    2) Intenta primero desde localStorage (esperando hidratación).
    3) Si no, usa el cookie cacheado desde app.py.
    4) Si no hay nada, deja la vista en login.
    """
    if st.session_state.get("token"):
        return

    # 1) Intentar localStorage
    raw = _ls_get(COOKIE_NAME)
    if raw is None:
        # localStorage aún no está listo: corta render para próximo ciclo
        st.empty().write("🔄 Restaurando sesión…")
        st.stop()

    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
        if data:
            st.session_state["token"]  = data.get("token", "")
            st.session_state["rol"]    = data.get("rol", "")
            st.session_state["nombre"] = data.get("nombre", "Empleado")
            st.session_state["rfc"]    = data.get("rfc", "")
            if st.session_state.get("view") in (None, "", "login"):
                st.session_state["view"] = "recibos"
            return

    # 2) Fallback: cookie (ya cacheado en app.py)
    data = _cookie_get(COOKIE_NAME)
    if data:
        st.session_state["token"]  = data.get("token", "")
        st.session_state["rol"]    = data.get("rol", "")
        st.session_state["nombre"] = data.get("nombre", "Empleado")
        st.session_state["rfc"]    = data.get("rfc", "")
        if st.session_state.get("view") in (None, "", "login"):
            st.session_state["view"] = "recibos"
        return

    # 3) Nada: asegúrate de quedar en login
    for k in ("token", "rol", "nombre", "rfc"):
        st.session_state.pop(k, None)
    if st.session_state.get("view") != "login":
        st.session_state["view"] = "login"

def obtener_token():
    """Devuelve el token desde memoria; si no hay, intenta restaurar."""
    tok = st.session_state.get("token")
    if tok:
        return tok

    # Reintentar localStorage
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

    # Cookie fallback
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

# =========================================================
# Utilidades JWT (diagnóstico)
# =========================================================
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
