import os
import streamlit as st

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"


TOKEN_FILE = "token.txt"

def guardar_token(token, rol, nombre=None, rfc=None):
    # Guarda en archivo y también en la sesión
    with open(TOKEN_FILE, "w") as f:
        f.write(f"{token}|{rol}|{nombre or ''}|{rfc or ''}")
    st.session_state["token"] = token
    st.session_state["rol"] = rol
    st.session_state["nombre"] = nombre
    st.session_state["rfc"] = rfc
    
    
def restaurar_sesion_completa():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            partes = f.read().split("|")
            if len(partes) >= 4:
                token, rol, nombre, rfc = partes
                st.session_state["token"] = token
                st.session_state["rol"] = rol
                st.session_state["nombre"] = nombre or "Empleado"
                st.session_state["rfc"] = rfc



def obtener_token():
    if "token" in st.session_state:
        return st.session_state["token"]
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            parts = f.read().split("|")
            st.session_state["token"] = parts[0]
            st.session_state["rol"] = parts[1]
            st.session_state["nombre"] = parts[2] if len(parts) > 2 else ""
            st.session_state["rfc"] = parts[3] if len(parts) > 3 else ""
            return parts[0]
    return None

def obtener_rol():
    if "rol" in st.session_state:
        return st.session_state["rol"]
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            parts = f.read().split("|")
            st.session_state["rol"] = parts[1]
            st.session_state["nombre"] = parts[2] if len(parts) > 2 else ""
            st.session_state["rfc"] = parts[3] if len(parts) > 3 else ""
            return parts[1]
    return None

def borrar_token():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    st.session_state.clear()