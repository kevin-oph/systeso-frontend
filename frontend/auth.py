import streamlit as st
import re
import requests
from utils import EMAIL_REGEX

BASE_URL = "https://systeso-backend-production.up.railway.app"

def login_user(email, password):
    try:
        response = requests.post(f"{BASE_URL}/users/login", json={
            "email": email,
            "password": password
        })

        if response.status_code == 200:
            return response.json()

        # Detectar si es por correo no verificado
        if response.status_code == 401:
            detail = response.json().get("detail", "")
            if "no verificado" in detail.lower():
                return {"error": "no_verificado", "email": email}
            else:
                # Cubre credenciales incorrectas, usuario no existe, etc.
                return {"error": "credenciales_invalidas", "detail": detail}

        # Cubre otros posibles errores del backend
        else:
            try:
                detail = response.json().get("detail", f"Error {response.status_code}")
            except Exception:
                detail = f"Error desconocido ({response.status_code})"
            return {"error": "otro_error", "detail": detail}

    except Exception as e:
        # Retornar mensaje de error por excepción de red, etc.
        return {"error": "conexion", "detail": str(e)}

def register_user():
    st.subheader("📝 Registro de nuevo usuario")

    with st.form(key="registro_form"):
        clave = st.number_input("🆔 Clave del empleado", step=1, key="clave")
        rfc = st.text_input("📄 RFC", key="rfc").strip().upper()
        email = st.text_input("📧 Email", key="reg_email").strip()
        password = st.text_input("🔑 Contraseña", type="password", key="reg_password")
        confirmar_password = st.text_input("🔁 Confirmar Contraseña", type="password", key="confirm_password")

        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("✅ Registrarse")
        with col2:
            back = st.form_submit_button("🔙 Iniciar sesión")

    if submit:
        errores = []

        if not clave:
            errores.append("La clave del empleado es obligatoria.")
        if not rfc or len(rfc) < 10:
            errores.append("RFC inválido o incompleto.")
        if not re.match(EMAIL_REGEX, email):
            errores.append("📧 Email inválido. Ej: usuario@ejemplo.com")
        if not re.match(PASSWORD_REGEX, password):
            errores.append("🔐 La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número.")
        if password != confirmar_password:
            errores.append("❌ Las contraseñas no coinciden.")

        if errores:
            for err in errores:
                st.markdown(
                    f"<div style='text-align: center; color: red; font-weight: bold;'>❌ {err}</div>",
                    unsafe_allow_html=True
                )
        else:
            data = {"clave": clave, "rfc": rfc, "email": email, "password": password}
            with st.spinner("📡 Enviando solicitud..."):
                response = requests.post("systeso-backend-production.up.railway.app/users/register", json=data)

            if response.status_code == 201:
                st.session_state.registro_exitoso = True
                st.session_state.view = "login"
                for key in ["clave", "rfc", "reg_email", "reg_password", "confirm_password"]:
                    st.session_state.pop(key, None)
                st.markdown(
                    "<div style='text-align: center; color: green; font-weight: bold;'>🎉 Registro exitoso</div>",
                    unsafe_allow_html=True
                )
                st.rerun()
            else:
                try:
                    error = response.json().get("detail", "Error desconocido")
                except:
                    error = "No se pudo interpretar la respuesta del servidor."
                st.markdown(
                    f"<div style='text-align: center; color: red; font-weight: bold;'>❌ Error al registrar: {error}</div>",
                    unsafe_allow_html=True
                )

    if back:
        st.session_state.view = "login"
        st.rerun()
