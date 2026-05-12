# app.py
import re
import time
import json
import requests
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from urllib.parse import unquote

from utils import (
    COOKIE_NAME,
    guardar_token,
    borrar_token,
    EMAIL_REGEX, PASSWORD_REGEX,
    jwt_exp_unix, is_jwt_expired,
)

from auth import login_user, register_user
from recibos import mostrar_recibos, subir_zip
from cargar_excel import cargar_excel_empleados
from verificacion import verificar_email
from reset_password import mostrar_formulario_reset

# ------------------- CONFIG -------------------
st.set_page_config(page_title="Sistema de Recibos", layout="centered", page_icon="📄")
BASE_URL = "https://api.zapatamorelos.gob.mx"

# ------------------- BOOT COOKIES -------------------
if "cookie_manager" not in st.session_state:
    st.session_state["cookie_manager"] = stx.CookieManager(key="systeso_cm")
cm = st.session_state["cookie_manager"]

cookies = cm.get_all(key="boot")
if cookies is None:
    st.empty().write("🔄 Restaurando sesión...")
    st.stop()

st.session_state["_cookies_cache"] = cookies

raw = cookies.get(COOKIE_NAME)
payload = None
if raw is not None:
    try:
        if isinstance(raw, dict):
            payload = raw
        elif isinstance(raw, (bytes, bytearray)):
            payload = json.loads(raw.decode("utf-8", "ignore"))
        elif isinstance(raw, str):
            tried = [raw]
            try:
                tried.append(unquote(raw))
            except Exception:
                pass
            for candidate in tried:
                try:
                    payload = json.loads(candidate); break
                except Exception:
                    continue
    except Exception:
        payload = None

if payload and not st.session_state.get("token"):
    st.session_state["token"]  = payload.get("token", "")
    st.session_state["rol"]    = payload.get("rol", "")
    st.session_state["nombre"] = payload.get("nombre", "Empleado")
    st.session_state["rfc"]    = payload.get("rfc", "")
    if st.session_state.get("view") in (None, "", "login"):
        st.session_state["view"] = "recibos"

token        = st.session_state.get("token", "")
rol_guardado = st.session_state.get("rol", "")

# Expiración JWT
if token and is_jwt_expired(token):
    borrar_token()
    st.warning("Tu sesión expiró. Vuelve a iniciar sesión.")
    st.stop()

# ------------------- ENLACES ESPECIALES -------------------
params = st.query_params
if "reset_password" in params and "token" in params:
    mostrar_formulario_reset(params["token"])
    st.stop()
if "token" in params:
    verificar_email()
    st.stop()

# ------------------- ESTILOS -------------------
st.markdown("""
<style>
body, .stApp { background-color: #eaeaea; color: #10312B; }
input, select, textarea { background-color: white; color: #10312B; border-radius: 6px; padding: 0.5em; border: 1px solid #235B4E; width: 100%; }
label { font-weight: bold; margin-bottom: 0.2em; color: #10312B; }
div.stButton > button { background-color: #235B4E; color: white; border-radius: 6px; font-weight: bold; padding: 0.5em 1em; margin-top: 1em; }
div.stButton > button:hover { background-color: #BC955C; color: white; }
</style>
""", unsafe_allow_html=True)

st.image("banner-systeso.png", use_container_width=True)
if st.session_state.get("view") == "recibos":
    st.markdown(
        """
        <div style='text-align: center; margin-top: 1.5em; margin-bottom: 2em;'>
            <h1 style='color: #10312B; font-size: 2.5em; font-weight: 800;'>📄 Sistema de Recibos de Nómina</h1>
            <p style='font-size: 1.2em; color: #235B4E;'>Ayuntamiento de Emiliano Zapata · 2025-2027</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------- INIT SESSION STATE -------------------
init_keys = [
    ("view", st.session_state.get("view", "login")),
    ("mostrar_reenvio", False),
    ("registro_exitoso", False),
    ("login_email", ""),
    ("login_password", ""),
    ("register_email", ""),
    ("register_rfc", ""),
    ("register_clave", ""),
    ("register_password", ""),
    ("register_confirmar", ""),
    ("reset_email", ""),
    ("reset_login_fields", False),
    ("reset_register_fields", False),
    ("reset_reset_fields", False),
]
for k, v in init_keys:
    if k not in st.session_state:
        st.session_state[k] = v

# ------------------- COMPLETAR DATOS (suave) -------------------
if token and "rol" not in st.session_state:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/users/me", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            st.session_state.nombre = data.get("nombre", "Empleado")
            st.session_state.rol = data.get("rol", (rol_guardado or "usuario"))
            st.session_state.view = st.session_state.get("view", "recibos")
        elif r.status_code in (401, 403):
            borrar_token()
            st.warning("Tu sesión expiró o no es válida. Inicia sesión nuevamente.")
    except requests.RequestException:
        pass

# ------------------- HISTORIAL DE CARGAS (ADMIN) -------------------
def mostrar_historial_cargas():
    tok = st.session_state.get("token")
    if not tok:
        st.warning("No tienes sesión activa."); return
    headers = {"Authorization": f"Bearer {tok}"}
    try:
        response = requests.get(f"{BASE_URL}/empleados/historial_cargas", headers=headers, timeout=15)
    except Exception as e:
        st.error(f"Error de red: {e}"); return

    if response.status_code == 200:
        historial = response.json()
        st.markdown("### 📂 Historial de archivos Excel cargados:")
        if historial:
            df = pd.DataFrame(historial).rename(
                columns={"nombre_archivo":"Nombre del archivo","fecha_carga":"Fecha y hora","usuario":"Usuario"}
            )
            df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"])
            col1, col2, col3 = st.columns(3)
            usuarios = df["Usuario"].unique().tolist()
            usuario_sel = col1.selectbox("Filtrar por usuario", options=["Todos"] + usuarios, key="sel_hist_user")
            if usuario_sel != "Todos":
                df = df[df["Usuario"] == usuario_sel]
            fechas = df["Fecha y hora"].dt.date.unique()
            if len(fechas) > 0:
                fecha_ini = col2.date_input("Desde", value=min(fechas), key="date_hist_from")
                fecha_fin = col3.date_input("Hasta", value=max(fechas), key="date_hist_to")
                df = df[(df["Fecha y hora"].dt.date >= fecha_ini) & (df["Fecha y hora"].dt.date <= fecha_fin)]
            nombre_buscar = st.text_input("Buscar archivo por nombre", key="txt_hist_search")
            if nombre_buscar:
                df = df[df["Nombre del archivo"].str.contains(nombre_buscar, case=False, na=False)]
            st.dataframe(df.sort_values("Fecha y hora", ascending=False), use_container_width=True)
        else:
            st.info("No hay archivos registrados todavía.")
    else:
        st.error("Error al consultar el historial de cargas.")

# ------------------- RUTAS AUTENTICADAS -------------------
if token:
    rol = st.session_state.get("rol", "usuario")
    nombre = st.session_state.get("nombre", "Empleado")

    with st.sidebar:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 1em;">
                <img src="https://api.dicebear.com/7.x/identicon/svg?seed={nombre}" style="border-radius: 50%; width: 96px; height: 96px; border: 3px solid #235B4E; box-shadow: 0 2px 8px #235b4e2a;">
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### 👤 Usuario autenticado")
        st.markdown(f"👋 Bienvenido, **{nombre}**")

        if rol == "admin":
            if st.button("📄 Cargar Recibos ZIP", use_container_width=True, key="btn_to_zip"):
                st.session_state.view = "subir_zip"; st.rerun()
            if st.button("📅 Cargar Empleados", use_container_width=True, key="btn_to_excel"):
                st.session_state.view = "cargar_excel"; st.rerun()
            if st.button("📑 Historial Excel", use_container_width=True, key="btn_to_hist"):
                st.session_state.view = "historial_excel"; st.rerun()
        else:
            if st.button("📄 Ver Recibos", use_container_width=True, key="btn_to_recibos"):
                st.session_state.view = "recibos"; st.rerun()

        st.markdown("###")
        if st.button("🚪 Cerrar sesión", use_container_width=True, key="btn_logout"):
            borrar_token()

    if st.session_state.view == "subir_zip" and rol == "admin":
        subir_zip()
    elif st.session_state.view == "cargar_excel" and rol == "admin":
        cargar_excel_empleados()
    elif st.session_state.view == "historial_excel" and rol == "admin":
        mostrar_historial_cargas()
    else:
        mostrar_recibos()

# ------------------- LOGIN -------------------
elif st.session_state.view == "login":
    # 👇 Mostrar 'flash' si viene de recuperar/restablecer contraseña o registro
    flash = st.session_state.pop("_flash_login", None)
    if flash:
        kind, text = flash  # "success" | "info" | "warning" | "error"
        getattr(st, kind)(text)
        st.toast("✅ Operación completada.")

    st.title("Consulta tus Recibos de Nómina")
    st.subheader("🔐 Iniciar Sesión", divider="grey")

    if st.session_state.reset_login_fields:
        st.session_state.login_email = ""
        st.session_state.login_password = ""
        st.session_state.reset_login_fields = False

    if st.session_state.registro_exitoso:
        st.success("📧 Registro exitoso. Revisa tu correo para verificar tu cuenta.")
        st.session_state.registro_exitoso = False

    email = st.text_input("📧 Email", value=st.session_state.login_email, key="login_email")
    password = st.text_input("🔑 Contraseña", type="password", value=st.session_state.login_password, key="login_password")

    col1, col2 = st.columns([1, 1])
    
       
    def _emit_validation(detail):
    # "detail" puede venir como dict {"detail":[...]} o ya como lista
        items = detail.get("detail", detail) if isinstance(detail, dict) else detail
        if not isinstance(items, list):
            st.error("❌ No pudimos validar los datos. Revisa el correo y la contraseña.")
            return

        for err in items:
            loc = [p for p in err.get("loc", []) if p != "body"]
            field = ".".join(loc) if loc else ""
            msg = err.get("msg", "Dato inválido")

            if field == "email" and "valid email" in msg:
                st.error("📧 El correo no es válido. Ejemplo: persona@dominio.com")
            elif field == "password" and ("field required" in msg or "none is not an allowed value" in msg):
                st.error("🔐 La contraseña es obligatoria.")
            else:
                st.error(f"❌ {(field.capitalize() + ': ') if field else ''}{msg}")


    with col1:
        if st.button("🔓 Ingresar", key="btn_login"):
            if not email or not password:
                st.warning("Por favor, completa ambos campos.")
            else:
                with st.spinner("🔄 Validando credenciales..."):
                    result = login_user(email, password)

                # Manejo de resultados
                if not isinstance(result, dict):
                    st.error("❌ Error desconocido. Intenta de nuevo.")
                elif "access_token" in result:
                    st.session_state.reset_login_fields = True
                    guardar_token(
                        result["access_token"],
                        result["rol"],
                        result.get("nombre"),
                        result.get("rfc"),
                    )
                else:
                    err = result.get("error")
                    if err == "no_verificado":
                        st.session_state.mostrar_reenvio = True
                        st.warning("⚠️ Tu correo aún no ha sido verificado. Puedes reenviar la verificación abajo.")
                    elif err == "credenciales_invalidas":
                        st.error("❌ Credenciales incorrectas. Revisa tu correo y contraseña.")
                    elif err == "validacion":
                        _emit_validation(result.get("detail"))
                    elif err == "conexion":
                        st.error(f"⚠️ Error de conexión con el servidor: {result.get('detail')}")
                    else:
                        # "otro_error" u otro caso
                        detail = result.get("detail")
                        st.error(f"❌ Ocurrió un problema al iniciar sesión. {detail if isinstance(detail, str) else ''}")

        with col2:
            if st.button("📝 Crear cuenta", key="btn_to_register"):
                st.session_state.view = "register"
                st.session_state.reset_login_fields = True
                st.rerun()

        st.markdown("---")

        if st.button("¿Olvidaste tu contraseña?", key="btn_to_forgot"):
            st.session_state.view = "recuperar_password"
            st.session_state.reset_login_fields = True
            st.rerun()

        if st.session_state.get("mostrar_reenvio", False):
            if st.button("📩 Reenviar correo de verificación", key="btn_resend_verify"):
                with st.spinner("📨 Reenviando correo..."):
                    try:
                        response = requests.post(f"{BASE_URL}/users/reenviar_verificacion", json={"email": email}, timeout=15)
                        if response.status_code == 200:
                            st.success("✅ Correo reenviado. Revisa tu bandeja de entrada.")
                            st.toast("📬 Verificación reenviada exitosamente.")
                            st.session_state.mostrar_reenvio = False
                        else:
                            st.error("❌ No se pudo reenviar el correo. Intenta más tarde.")
                            st.toast("⚠️ Falló el intento de reenvío.")
                    except Exception as e:
                        st.error(f"⚠️ Error al contactar backend: {e}")
                        st.toast("🔌 Error de conexión.")

# ------------------- REGISTRO -------------------
elif st.session_state.view == "register":
    st.title("Crea tu cuenta para consultar tus recibos")
    st.subheader("📝 Registrate aqui", divider="grey")

    if st.session_state.reset_register_fields:
        st.session_state.register_email = ""
        st.session_state.register_rfc = ""
        st.session_state.register_clave = ""
        st.session_state.register_password = ""
        st.session_state.register_confirmar = ""
        st.session_state.reset_register_fields = False

    clave = st.text_input("Clave de empleado", value=st.session_state.register_clave, key="register_clave")
    rfc = st.text_input("RFC", value=st.session_state.register_rfc, key="register_rfc")
    email = st.text_input("Correo electrónico", value=st.session_state.register_email, key="register_email")
    password = st.text_input("Contraseña", type="password", value=st.session_state.register_password, key="register_password")
    confirmar = st.text_input("Confirmar contraseña", type="password", value=st.session_state.register_confirmar, key="register_confirmar")

    if st.button("Registrar", key="btn_register"):
        errores = []
        if not clave: errores.append("La clave de empleado es obligatoria.")
        if not rfc: errores.append("El RFC es obligatorio.")
        if not email: errores.append("El correo electrónico es obligatorio.")
        if email and not re.match(EMAIL_REGEX, email):
            errores.append("El correo electrónico no tiene un formato válido. Ejemplo: usuario@ejemplo.com")
        if not password: errores.append("La contraseña es obligatoria.")
        if password and not re.match(PASSWORD_REGEX, password):
            errores.append("La contraseña debe tener mínimo 8 caracteres, al menos una mayúscula, una minúscula y un número.")
        if not confirmar: errores.append("Confirma tu contraseña.")
        if password != confirmar: errores.append("Las contraseñas no coinciden.")

        if errores:
            for err in errores: st.error(err)
        else:
            data = {"clave": clave, "rfc": rfc, "email": email, "password": password}
            with st.spinner("Registrando usuario..."):
                response = requests.post(f"{BASE_URL}/users/register", json=data, timeout=20)
            if response.status_code == 201:
                st.success("🎉 Registro exitoso. Revisa tu correo para verificar tu cuenta.")
                st.session_state.reset_register_fields = True
                st.session_state.view = "login"
                st.session_state.registro_exitoso = True
                st.rerun()
            else:
                try:
                    error = response.json().get("detail", "Error desconocido")
                except Exception:
                    error = "No se pudo interpretar la respuesta del servidor."
                st.error(f"❌ Error al registrar: {error}")

    if st.button("🔙 Volver al login", key="btn_back_login_from_register"):
        st.session_state.view = "login"
        st.session_state.reset_register_fields = True
        st.rerun()

# ------------------- REENVÍO VERIFICACIÓN -------------------
elif st.session_state.view == "reenviar":
    st.subheader("📩 Reenviar correo de verificación")
    email_reintento = st.text_input("📧 Ingresa tu correo registrado", key="reenviar_email")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("📨 Reenviar verificación", key="btn_resend_manual"):
            with st.spinner("🔄 Enviando correo de verificación..."):
                try:
                    response = requests.post(f"{BASE_URL}/users/reenviar_verificacion", json={"email": email_reintento}, timeout=15)
                    if response.status_code == 200:
                        st.success("✅ Se ha reenviado el correo correctamente.")
                        st.toast("📬 Verificación reenviada a tu correo.")
                        if st.button("🔐 Ir al Login", key="btn_go_login_after_resend"):
                            st.session_state.view = "login"; st.rerun()
                    else:
                        st.error("❌ No se pudo reenviar el correo. Verifica que el correo esté registrado.")
                        st.toast("⚠️ Falló el reenvío. ¿Correo válido?")
                except Exception:
                    st.error("⚠️ Error de conexión con el servidor.")
                    st.toast("🔌 No se pudo contactar al backend.")
    with col2:
        if st.button("🔙 Volver al inicio", key="btn_back_home_from_resend"):
            st.session_state.view = "login"; st.rerun()

# ------------------- RECUPERAR PASSWORD -------------------
elif st.session_state.view == "recuperar_password":
    st.subheader("🔑 Recuperar Contraseña")

    # Eliminamos el reset_reset_fields manual de aquí para que no interfiera con el form
    
    with st.form("solicitar_reset_form", clear_on_submit=False): # Cambiado a False para evitar pérdida de datos en el envío
        email_reset = st.text_input(
            "📧 Ingresa tu correo registrado para restablecer tu contraseña",
            key="reset_email_input" # Usamos una key nueva para evitar conflictos
        )
        send = st.form_submit_button("📨 Enviar enlace de recuperación")

    if send:
        if not email_reset:
            st.warning("⚠️ Debes ingresar un correo.")
        elif not re.match(EMAIL_REGEX, email_reset):
            st.error("❌ El formato del correo no es válido.")
        else:
            with st.spinner("Enviando correo..."):
                try:
                    # Usamos .strip() para evitar espacios accidentales
                    resp = requests.post(f"{BASE_URL}/users/solicitar_reset", json={"email": email_reset.strip()}, timeout=15)
                    
                    # Aceptamos 200 y 202 (proceso aceptado en background)
                    if resp.status_code in (200, 202):
                        st.session_state["_flash_login"] = (
                            "success",
                            "Te enviamos un enlace de recuperación. Revisa tu bandeja de entrada y la carpeta de SPAM."
                        )
                        st.session_state.view = "login"
                        st.rerun()
                    else:
                        st.error("❌ No se pudo procesar la solicitud. Verifica que el correo sea el correcto.")
                except Exception as e:
                    st.error(f"⚠️ Error de conexión: {e}")

    if st.button("🔙 Volver al login", key="btn_back_login_from_reset"):
        st.session_state.view = "login"
        st.rerun()
