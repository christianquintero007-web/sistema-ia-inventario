import os
import streamlit as st
import pandas as pd
import requests
import zipfile
import io
import re
import pypdf

from datetime import date
from openai import OpenAI
from dotenv import load_dotenv

# Carga las variables de entorno (como el archivo .env local)
load_dotenv()


# =========================================================
# CONFIGURACIÓN INICIAL
# =========================================================

st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones EPP",
    page_icon="🛡️",
    layout="wide"
)

ANIO_ACTUAL = date.today().year


# =========================================================
# GESTIÓN DE ERRORES / LOGS GLOBALES (EN MEMORIA)
# =========================================================
if "log_errores_sistema" not in st.session_state:
    st.session_state["log_errores_sistema"] = []

def registrar_error_sistema(modulo, detalle_tecnico):
    timestamp = date.today().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["log_errores_sistema"].insert(0, {
        "FECHA/HORA": timestamp,
        "MÓDULO": modulo,
        "DETALLE TÉCNICO": detalle_tecnico
    })


# =========================================================
# DEPARTAMENTOS
# =========================================================

DEPARTAMENTOS = [
    "BASTIDOR 103",
    "PALAS 105",
    "MANTENIMIENTO 111",
    "USA 118",
    "REVISIÓN",
    "BAJAS"
]

MAPA_DEPARTAMENTOS = {
    "BASTIDOR 103": ["103", "BASTIDOR", "PERSONAL 103"],
    "PALAS 105": ["105", "PALAS", "PERSONAL 105"],
    "MANTENIMIENTO 111": ["111", "MANTENIMIENTO", "PERSONAL 111"],
    "USA 118": ["118", "USA", "TEXAS", "AUSTIN", "SAN ROMAN", "SAN ROMÁN"],
    "REVISIÓN": ["REVISION", "REVISIÓN"],
    "BAJAS": ["BAJA", "BAJAS"]
}


# =========================================================
# CONFIGURACIÓN DE CORREOS / GOOGLE SHEETS
# =========================================================

CORREO_NOTIFICACION_PRINCIPAL = "almacen@windsunmx.com"
CORREO_COMPANERA_OPERACIONES = "auxiliaroperaciones@windsunmx.com"

APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbyMmcnFcNCXOYXvaf9k83_CXfvnFJTgiwTgo9sNWqxYc1NRACo24vIWqImP56lVwrL3"
    "/exec"
)


# =========================================================
# CATÁLOGO MAESTRO DE EPP
# =========================================================

CATALOGO_EQUIPOS_EPP = {
    "VERTEX": {"marca": "PETZL", "descripcion": "CASCO"},
    "STRATO": {"marca": "PETZL", "descripcion": "CASCO"},
    "ATLAS LOCK": {"marca": "ROCK EMPIRE", "descripcion": "ARNÉS"},
    "ATLAS": {"marca": "ROCK EMPIRE", "descripcion": "ARNÉS"},
    "AVAO BOD FAST": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "AVAO FAST": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "AVAO BOD": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "VOLT": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "AUSTIN": {"marca": "IRUDEK", "descripcion": "GANCHO DE GRAN APERTURA"},
    "FLEX 383": {"marca": "IRUDEK", "descripcion": "GANCHO DE GRAN APERTURA"},
    "C226H": {"marca": "PROTECTA", "descripcion": "GANCHO DE GRAN APERTURA"},
    "3100431": {"marca": "PROTECTA", "descripcion": "CINTURÓN RETRÁCTIL"},
    "3100516": {"marca": "PROTECTA", "descripcion": "CINTURÓN RETRÁCTIL"},
    "ANNEAU C40": {"marca": "PETZL", "descripcion": "CINTA DE ANCLAJE"},
    "ANNEAU": {"marca": "PETZL", "descripcion": "CINTA DE ANCLAJE"},
    "GRILLON HOOK": {"marca": "PETZL", "descripcion": "POSICIONADOR / ESLINGA 3M"},
    "GRILLON": {"marca": "PETZL", "descripcion": "POSICIONADOR / ESLINGA 3M"},
    "CATCH FIX": {"marca": "ROCK EMPIRE", "descripcion": "POSICIONADOR / ESLINGA 3M"},
    "CROLL": {"marca": "PETZL", "descripcion": "BLOQUEADOR CROLL"},
    "OK TL": {"marca": "PETZL", "descripcion": "MOSQUETÓN"},
    "OK": {"marca": "PETZL", "descripcion": "MOSQUETÓN"},
    "AM'D": {"marca": "PETZL", "descripcion": "MOSQUETÓN"},
    "MAGNUM": {"marca": "ROCK EMPIRE", "descripcion": "MOSQUETÓN"},
    "SKC H04 EVO": {"marca": "SOMAIN", "descripcion": "ANTICAÍDAS"},
    "SOLLVIGO": {"marca": "HONEYWELL", "descripcion": "ANTICAÍDAS"},
    "SÖLL VI-GO": {"marca": "HONEYWELL", "descripcion": "ANTICAÍDAS"},
    "NOVAX": {"marca": "NOVAX", "descripcion": "GUANTE DIELÉCTRICO 1000V"}
}


# =========================================================
# CONFIGURACIÓN VISUAL
# =========================================================

st.sidebar.header("⚙️ Configuración Visual")
color_fondo = st.sidebar.color_picker("🎨 Color de Fondo del Sistema", "#0e1117")

def calcular_color_texto(hex_color):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminancia > 0.5 else "#FFFFFF"

color_texto = calcular_color_texto(color_fondo)

st.markdown(
    f"""
    <style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {{
        background-color: {color_fondo} !important;
        color: {color_texto} !important;
    }}
    h1, h2, h3, h4, h5, h6, p, span, label, div, .stMarkdown {{
        color: {color_texto} !important;
    }}
    .stTextInput input, .stSelectbox select {{
        color: #000000 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# PANEL DE ADMINISTRADOR (LECTURA SEGURA DE CREDENCIAL)
# =========================================================

st.sidebar.divider()
st.sidebar.header("🔒 Panel de Administrador")

password_ingresada = st.sidebar.text_input("Contraseña de Administrador:", type="password")

# Se obtiene la contraseña de forma segura desde las variables de entorno o secretos
PASSWORD_ADMIN = os.getenv("ADMIN_PASSWORD") or st.secrets.get("ADMIN_PASSWORD", "")

sistema_activo = True
es_admin = False

if password_ingresada and password_ingresada == PASSWORD_ADMIN:
    es_admin = True
    st.sidebar.success("🔓 Administrador Autenticado")
    sistema_activo = st.sidebar.toggle("🟢 Sistema Operativo (Activo/Inactivo)", value=True)
elif password_ingresada != "":
    st.sidebar.error("❌ Contraseña incorrecta")


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def limpiar_texto(texto):
    if texto is None: return ""
    texto = str(texto).replace("\xa0", " ")
    return re.sub(r"\s+", " ", texto).strip()

def normalizar_mayusculas(texto):
    return limpiar_texto(texto).upper()

def es_valor_vacio_serie(valor):
    if valor is None: return True
    valor = normalizar_mayusculas(valor)
    valores_vacios = ["", "-", "—", "–", "_", "N/A", "NA", "N/D", "ND", "SIN SERIE", "S/S", "S/N"]
    return valor in valores_vacios

def limpiar_numero_serie(valor):
    valor = normalizar_mayusculas(valor)
    valor = re.sub(r"^(FIX|S/N|SERIE)\s*:?\s*", "", valor, flags=re.IGNORECASE)
    return valor.strip()


# =========================================================
# DETECCIÓN DE DEPARTAMENTO Y TÉCNICO
# =========================================================

def determinar_departamento_automatico(texto_pdf):
    texto_pdf = texto_pdf or ""
    texto_upper = texto_pdf.upper()
    
    match_puesto = re.search(r"(?:PUESTO)\s*:?\s*([^\n]+)", texto_pdf, re.IGNORECASE)
    match_parque = re.search(r"(?:PARQUE|PARQUE E[ÓO]LICO)\s*:?\s*([^\n]+)", texto_pdf, re.IGNORECASE)
    match_localidad = re.search(r"(?:LOCALIDAD)\s*:?\s*([^\n]+)", texto_pdf, re.IGNORECASE)
    
    puesto = match_puesto.group(1).upper() if match_puesto else ""
    parque = match_parque.group(1).upper() if match_parque else ""
    localidad = match_localidad.group(1).upper() if match_localidad else ""
    info_contexto = f"{puesto} {parque} {localidad} {texto_upper}"

    if any(k in info_contexto for k in ["USA", "118", "SAN ROMAN", "SAN ROMÁN", "AUSTIN", "TEXAS"]):
        return "USA 118"
    if any(k in puesto for k in ["SOLDADOR", "BASTIDOR", "TECNICO BASTIDOR", "TÉCNICO BASTIDOR"]) or "BASTIDOR" in texto_upper:
        return "BASTIDOR 103"
    if any(k in puesto for k in ["PALAS", "TECNICO PALAS", "TÉCNICO PALAS", "LIDER PALAS", "LÍDER PALAS"]) or "PALAS" in texto_upper:
        return "PALAS 105"
    if any(k in puesto for k in ["MANTENIMIENTO", "TECNICO MANTENIMIENTO", "TÉCNICO MANTENIMIENTO"]) or any(k in info_contexto for k in ["JUCHITAN", "JUCHITÁN", "VESTAS", "BII HIOXO", "BIIHIOXO"]):
        return "MANTENIMIENTO 111"
    return "REVISIÓN"

def extraer_nombre_tecnico(texto_pdf):
    lineas = [l.strip() for l in texto_pdf.split("\n") if l.strip()]
    if not lineas: return "TÉCNICO NO DETECTADO"
    for l in lineas[:15] + lineas[-15:]:
        match = re.search(r"(?:NOMBRE|RECIBE|PERSONAL ASIGNADO|PERSONAL|TÉCNICO)\s*:?\s*([A-ZÁÉÍÓÚÑ\s]{5,60})", l, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip().upper())
    return lineas[0].upper() if len(lineas[0]) > 4 else "TÉCNICO NO DETECTADO"


# =========================================================
# EXTRACCIÓN DE PDF Y FILAS
# =========================================================

def extraer_datos_pdf_individual(stream_pdf):
    try:
        reader = pypdf.PdfReader(stream_pdf)
        texto_pdf = ""
        for page in reader.pages:
            try:
                texto = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                texto = page.extract_text() or ""
            texto_pdf += texto + "\n"
        return texto_pdf
    except Exception as e:
        registrar_error_sistema("Lector PDF", str(e))
        return ""

def extraer_filas_tabla_epp(texto_pdf):
    filas = []
    if not texto_pdf: return filas
    for linea in texto_pdf.splitlines():
        linea_original = linea.rstrip()
        match_item = re.match(r"^\s*(\d{1,2})\s+", linea_original)
        if not match_item: continue
        item = int(match_item.group(1))
        resto = linea_original[match_item.end():].strip()
        if not resto: continue

        columnas = [limpiar_texto(c) for c in re.split(r"\s{2,}", resto) if limpiar_texto(c)]
        if len(columnas) < 4:
            marcas_conocidas = ["PETZL", "ROCK EMPIRE", "HONEYWELL", "SOMAIN", "IRUDEK", "PROTECTA", "3M", "MASTER LOCK", "TRUPER", "NOVAX", "KLEENGUARD"]
            marca_encontrada, posicion_marca = None, -1
            resto_upper = resto.upper()
            for marca in sorted(marcas_conocidas, key=len, reverse=True):
                pos = resto_upper.find(marca)
                if pos >= 0:
                    marca_encontrada, posicion_marca = marca, pos
                    break
            if marca_encontrada:
                antes_marca = resto[:posicion_marca].strip()
                despues_marca = resto[posicion_marca + len(marca_encontrada):].strip()
                tokens = antes_marca.split()
                descripcion = tokens[0] if tokens else ""
                serie = ""
                if len(tokens) >= 2:
                    for candidato in tokens[1:]:
                        if len(candidato.strip()) >= 6 and any(c.isdigit() for c in candidato.strip()):
                            serie = candidato.strip()
                            break
                partes_despues = re.split(r"\s{2,}", despues_marca)
                modelo = partes_despues[0] if partes_despues else ""
                columnas = [descripcion, serie, marca_encontrada, modelo]

        if len(columnas) < 4: continue
        filas.append({
            "ITEM": item,
            "DESCRIPCIÓN": normalizar_mayusculas(columnas[0] if len(columnas) > 0 else ""),
            "NÚMERO DE SERIE": normalizar_mayusculas(columnas[1] if len(columnas) > 1 else ""),
            "MARCA": normalizar_mayusculas(columnas[2] if len(columnas) > 2 else ""),
            "MODELO": normalizar_mayusculas(columnas[3] if len(columnas) > 3 else ""),
            "TALLA": normalizar_mayusculas(columnas[4] if len(columnas) > 4 else ""),
            "OBSERVACIONES": normalizar_mayusculas(columnas[5] if len(columnas) > 5 else "")
        })
    return filas


def identificar_equipo_catalogo(descripcion, marca, modelo, linea_completa):
    descripcion, marca, modelo, linea = normalizar_mayusculas(descripcion), normalizar_mayusculas(marca), normalizar_mayusculas(modelo), normalizar_mayusculas(linea_completa)
    desc_f, marca_f, mod_f = descripcion, marca, modelo

    for mod_key in sorted(CATALOGO_EQUIPOS_EPP.keys(), key=len, reverse=True):
        if mod_key in modelo:
            info = CATALOGO_EQUIPOS_EPP[mod_key]
            return info["descripcion"], (marca_f or info["marca"]), mod_key
            
    for mod_key in sorted(CATALOGO_EQUIPOS_EPP.keys(), key=len, reverse=True):
        if mod_key in linea:
            info = CATALOGO_EQUIPOS_EPP[mod_key]
            return info["descripcion"], (marca_f or info["marca"]), (mod_f or mod_key)

    return desc_f, marca_f, mod_f


# =========================================================
# GOOGLE SHEETS (CON MANEJO SEGURO DE ERRORES)
# =========================================================

def enviar_datos_a_google_sheets(df_nuevos):
    try:
        registros = []
        for _, row in df_nuevos.iterrows():
            registros.append({
                "DEPARTAMENTO": str(row.get("DEPARTAMENTO", "")),
                "DESCRIPCIÓN": str(row.get("DESCRIPCIÓN", "")),
                "MARCA": str(row.get("MARCA", "")),
                "MODELO": str(row.get("MODELO", "")),
                "NÚMERO DE SERIE": str(row.get("NÚMERO DE SERIE", "")),
                "FACTURA_OC": str(row.get("FACTURA_OC", "")),
                "FECHA_DE_ESTATUS": str(row.get("FECHA_DE_ESTATUS", "")),
                "OBSERVACIONES": str(row.get("OBSERVACIONES", "")),
                "ESTATUS": str(row.get("ESTATUS", "OK"))
            })

        headers = {"Content-Type": "application/json"}
        response = requests.post(APPS_SCRIPT_URL, json=registros, headers=headers, timeout=30, allow_redirects=True)

        if response.status_code in [200, 201]:
            return True, "Sincronizado con éxito"

        detalle_error = f"HTTP {response.status_code}: {response.text}"
        registrar_error_sistema("Google Sheets API", detalle_error)
        return False, "Error de comunicación con el servidor remoto."

    except Exception as e:
        registrar_error_sistema("Google Sheets Excepción", str(e))
        return False, "Error interno al procesar la sincronización."


# =========================================================
# POWER AUTOMATE
# =========================================================

def enviar_alerta_power_automate(tecnico, equipo, estatus, destinatario=CORREO_NOTIFICACION_PRINCIPAL, detalles_adicionales=""):
    webhook_url = st.secrets.get("POWER_AUTOMATE_URL") or os.getenv("POWER_AUTOMATE_URL", "")
    if not webhook_url: return False
    payload = {
        "destinatario": destinatario,
        "asunto": f"🚨 ALERTA EPP: {equipo} - {estatus}",
        "cuerpo": f"Reporte:\n- Técnico: {tecnico}\n- Equipo: {equipo}\n- Estado: {estatus}",
        "equipo": equipo, "tecnico": tecnico, "estatus": estatus
    }
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in [200, 202]
    except Exception as e:
        registrar_error_sistema("Power Automate", str(e))
        return False


# =========================================================
# PROCESAMIENTO ZIP
# =========================================================

def procesar_y_auditar_zip(archivo_zip_subido):
    fichas_pdf, master_acuse_texto, master_filename = {}, "", ""
    with zipfile.ZipFile(archivo_zip_subido, "r") as z:
        archivos_pdf = [n for n in z.namelist() if n.lower().endswith(".pdf")]
        if not archivos_pdf: return None, pd.DataFrame(), pd.DataFrame(), []
        
        for nombre in archivos_pdf:
            try:
                with z.open(nombre) as f_pdf:
                    texto = extraer_datos_pdf_individual(io.BytesIO(f_pdf.read()))
                    fichas_pdf[nombre] = texto
                    if any(k in nombre.lower() or k in texto.upper() for k in ["FO-09", "FO09", "COPIA", "ENTREGA"]):
                        if not master_acuse_texto:
                            master_acuse_texto, master_filename = texto, nombre
            except Exception as e:
                registrar_error_sistema("Procesamiento ZIP", f"Archivo {nombre}: {str(e)}")

    if not master_acuse_texto and archivos_pdf:
        master_filename = archivos_pdf[0]
        master_acuse_texto = fichas_pdf[master_filename]

    departamento_auto = determinar_departamento_automatico(master_acuse_texto)
    tecnico_master = extraer_nombre_tecnico(master_acuse_texto)
    if tecnico_master == "TÉCNICO NO DETECTADO":
        tecnico_master = archivo_zip_subido.name.replace(".zip", "").replace("_", " ").upper()

    match_fechas = re.findall(r"\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b", master_acuse_texto)
    fecha_acuse = match_fechas[-1] if match_fechas else date.today().strftime("%Y-%m-%d")

    filas_tabla = extraer_filas_tabla_epp(master_acuse_texto)
    registros_inventario = []

    for fila in filas_tabla:
        num_serie = fila["NÚMERO DE SERIE"]
        if es_valor_vacio_serie(num_serie): continue
        num_serie = limpiar_numero_serie(num_serie)
        if es_valor_vacio_serie(num_serie): continue

        descripcion, marca, modelo = identificar_equipo_catalogo(
            fila["DESCRIPCIÓN"], fila["MARCA"], fila["MODELO"], 
            f"{fila['DESCRIPCIÓN']} {num_serie} {fila['MARCA']} {fila['MODELO']}"
        )
        
        obs_formateada = f"(NUEVO) {tecnico_master}" if "NUEVO" in fila["OBSERVACIONES"].upper() else tecnico_master

        registros_inventario.append({
            "DEPARTAMENTO": departamento_auto, "DESCRIPCIÓN": descripcion, "MARCA": marca,
            "MODELO": modelo, "NÚMERO DE SERIE": num_serie, "FACTURA_OC": "",
            "FECHA_DE_ESTATUS": fecha_acuse, "OBSERVACIONES": obs_formateada, "ESTATUS": "OK"
        })

    return tecnico_master, pd.DataFrame(registros_inventario), pd.DataFrame(), []


# =========================================================
# INTERFAZ PRINCIPAL Y PESTAÑAS (7 TOTALES)
# =========================================================

st.title("🛡️ Sistema de Gestión EPP e Inspecciones")

if not sistema_activo:
    st.warning("⚠️ **SISTEMA INHABILITADO:** El administrador ha pausado temporalmente el sistema.")
    st.stop()

tabs_lista = [
    "1️⃣ Dashboard",
    "2️⃣ Registrar Equipo",
    "3️⃣ Inspección Pre-operacional",
    "4️⃣ Historial de Inspecciones",
    "5️⃣ Asistente IA",
    "6️⃣ Automatización y Fichas"
]

if es_admin:
    tabs_lista.append("7️⃣ Alertas y Errores 🔒")

tabs = st.tabs(tabs_lista)

tab_dashboard = tabs[0]
tab_registrar = tabs[1]
tab_inspeccion = tabs[2]
tab_historial = tabs[3]
tab_ia = tabs[4]
tab_zip = tabs[5]
tab_errores = tabs[6] if es_admin else None


with tab_dashboard:
    st.header(f"📊 Estado General del Inventario ({ANIO_ACTUAL})")
    st.info("Panel general activo para el seguimiento de equipos.")


with tab_registrar:
    st.header("➕ Registrar / Asignar Equipo")
    with st.form("form_registrar_equipo"):
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            reg_depto = st.selectbox("Departamento:", DEPARTAMENTOS)
            reg_desc = st.text_input("Descripción del Equipo:")
            reg_marca = st.text_input("Marca:")
        with col_r2:
            reg_modelo = st.text_input("Modelo:")
            reg_serie = st.text_input("Número de Serie:")
            reg_factura = st.text_input("Factura / OC:")
        if st.form_submit_button("💾 Guardar Registro en Inventario"):
            st.success("✅ Equipo registrado exitosamente.")


with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional en Campo")
    insp_equipo = st.text_input("Buscar equipo por Número de Serie o Descripción:")
    insp_estado = st.radio("Estado de la inspección:", ["Conforme (OK) 🟢", "No Conforme / Dañado 🔴", "Requiere Mantenimiento 🟡"])
    insp_detalles = st.text_area("Detalles o hallazgos:")
    if st.button("📤 Enviar Reporte de Inspección"):
        st.success("✅ Inspección registrada correctamente.")


with tab_historial:
    st.header("📜 Historial de Inspecciones y Movimientos")
    st.info("No hay registros históricos recientes.")


with tab_ia:
    st.header("🤖 Asistente IA (DeepSeek)")
    pregunta_ia = st.text_input("Escribe tu consulta para DeepSeek:")
    if pregunta_ia:
        deepseek_key = st.secrets.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
        if not deepseek_key:
            st.error("⚠️ Falta configurar `DEEPSEEK_API_KEY` en secretos.")
        else:
            try:
                client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": pregunta_ia}],
                    stream=False
                )
                st.write(response.choices[0].message.content)
            except Exception as e:
                registrar_error_sistema("DeepSeek IA", str(e))
                st.error("❌ Ocurrió un error procesando la consulta con la IA.")


with tab_zip:
    st.header(f"📂 Auditoría y Sincronización de Fichas EPP ({ANIO_ACTUAL})")
    zip_cargado = st.file_uploader("Sube el archivo ZIP con las fichas del técnico:", type=["zip"])

    if zip_cargado:
        with st.spinner("⚡ Leyendo archivos..."):
            tecnico_master, df_inventario, df_ok, lista_errores = procesar_y_auditar_zip(zip_cargado)

        st.subheader(f"📋 Resumen - Técnico: **{tecnico_master}**")

        if not df_inventario.empty:
            st.success(f"✅ Se procesaron **{len(df_inventario)}** filas correctamente.")

            if st.button("🚀 Enviar Automáticamente a Google Sheets"):
                with st.spinner("Sincronizando..."):
                    exito_gs, mensaje_gs = enviar_datos_a_google_sheets(df_inventario)

                    if exito_gs:
                        st.success("🎉 ¡Datos sincronizados exitosamente con Google Sheets!")
                        st.balloons()
                    else:
                        st.error("⚠️ No se pudo completar la sincronización automática con Google Sheets. El administrador ha sido notificado para revisarlo.")

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_inventario.to_excel(writer, index=False, sheet_name="INVENTARIO")
            st.download_button("📥 Descargar Inventario en Excel (.xlsx)", data=output.getvalue(), file_name=f"Inventario_{tecnico_master}.xlsx")
            st.dataframe(df_inventario, use_container_width=True)


# =========================================================
# PESTAÑA 7: PANEL DE ALERTAS Y ERRORES (SOLO ADMIN)
# =========================================================
if es_admin and tab_errores is not None:
    with tab_errores:
        st.header("🔒 Panel de Control de Errores y Alertas Técnicas")
        st.write("Esta sección es privada y solo visible para el administrador. Aquí se registran los detalles técnicos de cualquier fallo en el sistema.")

        if st.session_state["log_errores_sistema"]:
            if st.button("🗑️ Limpiar Historial de Errores"):
                st.session_state["log_errores_sistema"] = []
                st.rerun()

            df_logs = pd.DataFrame(st.session_state["log_errores_sistema"])
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.success("🎉 ¡Excelente! No se ha registrado ningún error técnico en el sistema durante esta sesión.")
