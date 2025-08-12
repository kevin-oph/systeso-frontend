# utils.py
from typing import Optional
import json
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"

# Nombre y duración del cookie de autenticación
COOKIE_NAME = "systeso_auth"
COOKIE_DAYS = 7


# ===================== Infra de cookies (una sola instancia) =====================

def _cm():
    """
    Devuelve la instancia ÚNICA del CookieManager creada en app.py (boot).
    Si no existe (llamada fuera de orden), crea una de emergencia con otra key.
    """
    cm = st.session_state.get("cookie_manager")
    if cm is not None:
        return cm

    # Fallback (no ideal, pero evita crash si se llamó antes del boot en app.py)
    if "_cookie_manager_fallback" not in st.session_state:
        st.session_state["_cookie_manager_fallback"] = stx.CookieManager(key="systeso_cm_fallback")
    return st.session_state["_cookie_manager_fallback"]


def _set_cookie(name: str, value: dict, days: int = COOKIE_DAYS) -> None:
    """
    Guarda un cookie con expiración y path="/".
    Intenta usar same_site/secure si la versión de extra_streamlit_components lo soporta;
    si no, hace fallback sin esos argumentos.
    """
    expires_at = datetime.utcnow() + timedelta(days=days)
    payload = json.dumps(value)

    cm = _cm()
    try:
        # Versiones recientes (algunas aceptan 'same_site' y 'secure')
        cm.set(
            name,
            payload,
            expires_at=expires_at,
            path="/",
            same_site="Lax",   # <- NOTA: 'same_site' con guion bajo
            secure=True,       # <- si la versión no lo soporta, cae al except
        )
    except TypeError:
        # Versiones antiguas: solo usa expires_at y path
        cm.set(
            name,
            payload,
            expires_at=expires_at,
            path="/",
        )


def _delete_cookie(name: str) -> None:
    """Borra el cookie usando el MISMO path con el que fue creado."""
    _cm().delete(name, path="/")


def _get_cookie(name: str) -> Optional[dict]:
    """
    Lee el cookie desde la CACHÉ que llenamos en app.py (st.session_state["_cookies_cache"]).
    No llama get_all() otra vez para evitar claves duplicadas por render.
    """
    cookies = st.session_state.get("_cookies_cache")

    # Emergencia: si no hay caché (se llamó sin pasar por el boot de app.py),
    # hacemos una única lectura y cacheamos.
    if cookies is None:
        cm = _cm()
        cookies = cm.get_all(key="fallback_read")
        if cookies is None:
            # Primer ciclo aún sin hidratar; force un único rerun
            if not st.session_state.get("_cookie_hydration_rerun_done"):
                st.session_state["_cookie_hydration_rerun_done"] = True
                st.rerun()
            return None
        st.session_state["_cookies_cache"] = cookies

    if not cookies:
        return None

    raw = cookies.get(name)
    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


# ===================== API para autenticación (front) =====================

def guardar_token(token: str, rol: str, nombre: Optional[str] = None, rfc: Optional[str] = None) -> None:
    """
    Guarda token + datos en cookie y en session_state.
    """
    payload = {"token": token, "rol": rol, "nombre": nombre or "", "rfc": rfc or ""}

    # 1) Guardar en cookie (persistente por COOKIE_DAYS)
    _set_cookie(COOKIE_NAME, payload, days=COOKIE_DAYS)

    # 2) Guardar en session_state para uso inmediato
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = payload["nombre"]
    st.session_state["rfc"] = payload["rfc"]

    # 3) (Opcional) Actualizar la caché de este render y rerun
    cache = st.session_state.get("_cookies_cache") or {}
    cache[COOKIE_NAME] = json.dumps(payload)
    st.session_state["_cookies_cache"] = cache

    st.rerun()


def restaurar_sesion_completa() -> None:
    """
    Si no hay sesión en memoria, intenta restaurar desde cookie.
    (Llamar al inicio de app.py, DESPUÉS del boot de cookies).
    """
    if st.session_state.get("token"):
        return  # ya hay sesión en memoria

    data = _get_cookie(COOKIE_NAME)
    if not data:
        return

    st.session_state["token"] = data.get("token", "")
    st.session_state["rol"] = data.get("rol", "")
    st.session_state["nombre"] = data.get("nombre", "Empleado")
    st.session_state["rfc"] = data.get("rfc", "")

    # Si la vista está vacía o en login, manda directo a 'recibos'
    if st.session_state.get("view") in (None, "", "login"):
        st.session_state["view"] = "recibos"


def obtener_token() -> Optional[str]:
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
    return st.session_state["token"] or None


def obtener_rol() -> Optional[str]:
    """Similar a obtener_token, pero para el rol."""
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
    return st.session_state["rol"] or None


def borrar_token() -> None:
    """
    Logout: borra cookie + limpia session_state y hace rerun.
    """
    _delete_cookie(COOKIE_NAME)
    for k in ("token", "rol", "nombre", "rfc", "_cookies_cache"):
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()
