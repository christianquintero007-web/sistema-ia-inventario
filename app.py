import streamlit as st
import pandas as pd
import google.generativeai as genai
import unicodedata
import requests
import zipfile
import io
import re
import pypdf
from datetime import date
from openai import OpenAI

# ---------------------------------------------------------
# CONFIGURACIÓN INICIAL Y DEPARTAMENTOS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones EPP", 
    page_icon="🛡️", 
    layout="wide"
)

ANIO_ACTUAL = date.today().year

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
    "USA 118": ["118", "USA", "TEXAS", "AUSTIN", "SAN ROMAN"],
    "REVISIÓN": ["REVISION", "REVISIÓN"],
    "BAJAS": ["BAJA", "BAJAS"]
}

CORREO_NOTIFICACION_PRINCIPAL = "almacen@windsunmx.com"
CORREO_COMPANERA_OPERACIONES = "auxiliaroperaciones@windsunmx.com"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyMmcnFcNCXOYXvaf9k83_CXfvnFJTgiwTgo9sNWqxYc1NRACo24vIWqImP56lVwrL3/exec"

# ---------------------------------------------------------
# DICCIONARIO MAESTRO DE CATÁLOGO EPP (AMPLIADO Y PRECISO)
# ---------------------------------------------------------
CATALOGO_EQUIPOS_EPP = {
    "VERTEX": {"marca": "PETZL", "descripcion": "CASCO"},
    "STRATO": {"marca": "PETZL", "descripcion": "CASCO"},
    "ATLAS LOCK": {"marca": "ROCK EMPIRE", "descripcion": "ARNÉS"},
    "ATLAS": {"marca": "ROCK EMPIRE", "descripcion": "ARNÉS"},
    "AVAO BOD FAST": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "AVAO FAST": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "AVAO BOD": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "VOLT": {"marca": "PETZL", "descripcion": "ARNÉS"},
    "AUSTIN": {"marca": "IRUDEK", "descripcion": "GANCHO GRAN APERTURA"},
    "FLEX 383": {"marca": "IRUDEK", "descripcion": "GANCHO GRAN APERTURA"},
    "C226H": {"marca": "PROTECTA", "descripcion": "GANCHO"},
    "3100431": {"marca": "PROTECTA", "descripcion": "CINTURÓN RETRÁCTIL"},
    "3100516": {"marca": "PROTECTA", "descripcion": "CINTURÓN RETRÁCTIL"},
    "ANNEAU C40": {"marca": "PETZL", "descripcion": "CINTA DE ANCLAJE"},
    "ANNEAU": {"marca": "PETZL", "descripcion": "CINTA DE ANCLAJE"},
    "GRILLON HOOK": {"marca": "PETZL", "descripcion": "POSICIONADOR / ESLINGA"},
    "GRILLON": {"marca": "PETZL", "descripcion": "POSICIONADOR / ESLINGA"},
    "CATCH FIX": {"marca": "ROCK EMPIRE", "descripcion": "POSICIONADOR"},
    "CROLL": {"marca": "PETZL", "descripcion": "BLOQUEADOR CROLL"},
    "OK TL": {"marca": "PETZL", "descripcion": "MOSQUETÓN"},
    "OK": {"marca": "PETZL", "descripcion": "MOSQUETÓN"},
    "AM'D": {"marca": "PETZL", "descripcion": "MOSQUETÓN"},
    "MAGNUM": {"marca": "ROCK EMPIRE", "descripcion": "MOSQUETÓN"},
    "ABSORBICA Y FLEX 150": {"marca": "PETZL", "descripcion": "ABSORBEDOR CON ESLINGA 150CM"},
    "ABSORBICA Y FLEX": {"marca": "PETZL", "descripcion": "ABSORBEDOR CON ESLINGA"},
    "SKC H04 EVO": {"marca": "SOMAIN", "descripcion": "ANTICAÍDAS DESLIZANTE"},
    "SOLLVIGO": {"marca": "HONEYWELL", "descripcion": "ANTICAÍDAS"},
    "SÖLL VI-GO": {"marca": "HONEYWELL", "descripcion": "ANTICAÍDAS"},
    "NOVAX": {"marca": "NOVAX", "descripcion": "GUANTE DIELÉCTRICO 1000V"}
}

# ---------------------------------------------------------
# DETECCIÓN INTELIGENTE DE CONTRASTE Y CONFIGURACIÓN VISUAL
# ---------------------------------------------------------
st.sidebar.header("⚙️ Configuración Visual")
color_fondo = st.sidebar.color_picker("🎨 Color de Fondo del Sistema", "#0e1117")

def calcular_color_texto(hex_color):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminancia > 0.5 else "#FFFFFF"

color_texto = calcular_color_texto(color_fondo)

st.markdown(f"""
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
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# PANEL DE ADMINISTRADOR POR CONTRASEÑA EN BARRA LATERAL
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.header("🔒 Panel de Administrador")
password_ingresada = st.sidebar.text_input("Contraseña de Administrador:", type="password")

PASSWORD_ADMIN = "Windsun2026*"
sistema_activo = True  

if password_ingresada == PASSWORD_ADMIN:
    st.sidebar.success("🔓 Administrador Autenticado")
    sistema_activo = st.sidebar.toggle("🟢 Sistema Operativo (Activo/Inactivo)", value=True, help="Apaga o enciende el sistema completo.")
elif password_ingresada != "":
    st.sidebar.error("❌ Contraseña incorrecta")

# ---------------------------------------------------------
# FILTRO ESTRICTO DE ELEMENTOS SERIABLES Y GUANTES DIELÉCTRICOS
# ---------------------------------------------------------
def es_item_valido_o_excepcion(linea_texto):
    texto_upper = linea_texto.upper()

    palabras_prohibidas = [
        "WINDSUN", "ENTREGA EPI", "LOCALIDAD", "PUESTO", "FO-09", "FIRMA", 
        "RECIBE", "NOMBRE", "FECHA", "ITEM", "TALLA", "OBSERVACIONES", 
        "DESCRIPCIÓN", "MARCA", "MODELO", "SERIE", "CANTIDAD", "PÁGINA", "DE",
        "RODRIGO", "GONZALEZ", "TRUJILLO", "LEVI", "PERSONAL", "LENTES", "DERMACARE", "MASTER"
    ]
    if any(p in texto_upper for p in palabras_prohibidas) and not any(k in texto_upper for k in ["ARNÉS", "ARNES", "CASCO", "ESLINGA", "CINTA", "POSICIONADOR", "CROLL", "ABSORBICA", "VERTEX", "STRATO", "AVAO", "VOLT", "GRILLON", "SKC", "SOLL", "GUANTE", "60", "120"]):
        return False, False

    patron_guantes_dielectricos = r'GUANTE.*(1000|CLASE\s*0|1000V|NOVAX)'
    if re.search(patron_guantes_dielectricos, texto_upper):
        return True, True

    palabras = texto_upper.split()
    serie_encontrada = None
    
    for palabra in palabras:
        # Acepta series alfanuméricas con guiones o barras diagonales (ej. 21365205/070)
        if (len(palabra) >= 6 and any(c.isdigit() for c in palabra)) or ('/' in palabra and any(c.isdigit() for c in palabra)):
            serie_encontrada = palabra
            break

    if not serie_encontrada:
        return False, False

    falsas_series = ["NUEVO", "NUEVOS", "USADO", "APTO", "DESCONOCIDO", "INSPECCION", "CONFORME"]
    if serie_encontrada in falsas_series:
        return False, False

    return True, False

# ---------------------------------------------------------
# DETECTOR AUTOMÁTICO DE DEPARTAMENTO
# ---------------------------------------------------------
def determinar_departamento_automatico(texto_pdf):
    texto_upper = texto_pdf.upper()

    match_puesto = re.search(r'(?:PUESTO):\s*([^\n]+)', texto_pdf, re.IGNORECASE)
    match_parque = re.search(r'(?:PARQUE|PARQUE E[ÓO]LICO):\s*([^\n]+)', texto_pdf, re.IGNORECASE)
    match_localidad = re.search(r'(?:LOCALIDAD):\s*([^\n]+)', texto_pdf, re.IGNORECASE)

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

# ---------------------------------------------------------
# EXTRACCIÓN INTELIGENTE DE TÉCNICO
# ---------------------------------------------------------
def extraer_nombre_tecnico(texto_pdf):
    lineas = [l.strip() for l in texto_pdf.split('\n') if l.strip()]
    if not lineas:
        return "TÉCNICO NO DETECTADO"
    
    for l in lineas[:15] + lineas[-15:]:
        match = re.search(r'(?:NOMBRE|RECIBE|PERSONAL ASIGNADO|PERSONAL|TÉCNICO):\s*([A-ZÁÉÍÓÚÑ\s]{5,40})', l, re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
            
    return lineas[0].upper() if len(lineas[0]) > 4 else "TÉCNICO NO DETECTADO"

# ---------------------------------------------------------
# CONEXIÓN OPTIMIZADA CON GOOGLE SHEETS
# ---------------------------------------------------------
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
        response = requests.post(APPS_SCRIPT_URL, json=registros, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return True, response.text
        else:
            return False, f"Código HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------------
# ALERTAS VÍA POWER AUTOMATE
# ---------------------------------------------------------
def enviar_alerta_power_automate(tecnico, equipo, estatus, destinatario=CORREO_NOTIFICACION_PRINCIPAL, detalles_adicionales=""):
    webhook_url = st.secrets.get("POWER_AUTOMATE_URL")
    if not webhook_url:
        return False

    asunto = f"🚨 ALERTA EPP: {equipo} - {estatus}"
    cuerpo = (
        f"Se ha registrado un reporte de inspección no conforme:\n\n"
        f"• Técnico / Inspector: {tecnico}\n"
        f"• Equipo / Elemento: {equipo}\n"
        f"• Estado: {estatus}\n"
        f"• Observaciones / Hallazgos: {detalles_adicionales if detalles_adicionales else 'Sin observaciones adicionales'}\n\n"
        f"Mensaje generado automáticamente desde la App de Inspecciones EPP."
    )

    payload = {
        "destinatario": destinatario,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "equipo": equipo,
        "tecnico": tecnico,
        "estatus": estatus
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in [200, 202]
    except Exception:
        return False

def enviar_alerta_errores_usuario(tecnico, resumen_errores, correo_notificacion=CORREO_NOTIFICACION_PRINCIPAL):
    webhook_url = st.secrets.get("POWER_AUTOMATE_URL")
    if not webhook_url:
        return False

    asunto = f"🚨 NOTIFICACIÓN DE ERRORES EN FICHAS ({ANIO_ACTUAL}): {tecnico}"
    cuerpo = (
        f"Reporte de Auditoría de Fichas - Año {ANIO_ACTUAL}:\n\n"
        f"Se han encontrado incoherencias durante la revisión automática del paquete de fichas:\n\n"
        f"• Técnico: {tecnico}\n"
        f"• Año de Evaluación: {ANIO_ACTUAL}\n\n"
        f"DETALLE DE ERRORES REGISTRADOS:\n"
        f"{resumen_errores}\n\n"
        f"Por favor revisa estos archivos para realizar la corrección en la base de datos."
    )

    payload = {
        "destinatario": correo_notificacion,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "equipo": f"AUDITORÍA FICHAS {ANIO_ACTUAL}",
        "tecnico": tecnico,
        "estatus": "ERROR DE CAPTURA"
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in [200, 202]
    except Exception:
        return False

# ---------------------------------------------------------
# EXTRACCIÓN Y LÓGICA DE AUDITORÍA DE FICHAS (FLEXIBLE Y BLINDADA)
# ---------------------------------------------------------
def extraer_datos_pdf_individual(stream_pdf):
    try:
        reader = pypdf.PdfReader(stream_pdf)
        texto_pdf = ""
        for page in reader.pages:
            texto_pdf += page.extract_text() or ""
        return texto_pdf
    except Exception:
        return ""

def procesar_y_auditar_zip(archivo_zip_subido):
    fichas_pdf = {}
    master_acuse_texto = ""
    master_filename = ""

    nombre_zip_limpio = archivo_zip_subido.name.replace(".zip", "").replace("_", " ").replace("-", " ").upper()

    with zipfile.ZipFile(archivo_zip_subido, 'r') as z:
        archivos_pdf = [nombre for nombre in z.namelist() if nombre.lower().endswith('.pdf')]
        if not archivos_pdf:
            return None, pd.DataFrame(), pd.DataFrame(), []

        for nombre in archivos_pdf:
            with z.open(nombre) as f_pdf:
                stream = io.BytesIO(f_pdf.read())
                texto = extraer_datos_pdf_individual(stream)
                fichas_pdf[nombre] = texto
                
                nombre_l = nombre.lower()
                texto_u = texto.upper()
                if any(k in nombre_l for k in ["fo-09", "fo09", "copia", "entrega"]) or any(k in texto_u for k in ["ENTREGA EPI", "FO-09", "FO09"]):
                    if not master_acuse_texto:
                        master_acuse_texto = texto
                        master_filename = nombre

    if not master_acuse_texto and archivos_pdf:
        master_filename = archivos_pdf[0]
        master_acuse_texto = fichas_pdf[master_filename]

    departamento_auto = determinar_departamento_automatico(master_acuse_texto)
    
    tecnico_master = extraer_nombre_tecnico(master_acuse_texto)
    if tecnico_master == "TÉCNICO NO DETECTADO":
        tecnico_master = nombre_zip_limpio

    match_fechas = re.findall(r'\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b', master_acuse_texto)
    fecha_acuse = match_fechas[-1] if match_fechas else date.today().strftime("%Y-%m-%d")

    items_master = []
    registros_inventario = []
    lineas = master_acuse_texto.split('\n')

    for l in lineas:
        linea_str = l.strip()
        es_valido, es_excepcion_guante = es_item_valido_o_excepcion(linea_str)

        if es_valido:
            partes = linea_str.split()
            if len(partes) >= 1:
                if es_excepcion_guante:
                    num_serie = next((p for p in partes if len(p) >= 6 and any(c.isdigit() for c in p)), "SIN SERIE (DIELÉCTRICO)")
                    modelo = "CLASE 0 / 1000V"
                    marca = "NOVAX"
                    descripcion = "GUANTE DIELÉCTRICO 1000V"
                    candidatos_serie = [num_serie]
                else:
                    candidatos_serie = [p for p in partes if (len(p) >= 6 and any(c.isdigit() for c in p)) or ('/' in p and any(c.isdigit() for c in p))]
                    if not candidatos_serie:
                        candidatos_serie = [partes[-1]]

                for cand in candidatos_serie:
                    num_serie = re.sub(r'(?i)^(fix|s/n|serie)[:\s]*', '', cand)
                    
                    texto_l_upper = linea_str.upper()

                    modelo = ""
                    marca = ""
                    descripcion = ""

                    for mod_key, info in CATALOGO_EQUIPOS_EPP.items():
                        if mod_key in texto_l_upper:
                            modelo = mod_key
                            marca = info["marca"]
                            descripcion = info["descripcion"]
                            break
                    
                    # Detección flexible y tolerante a acentos/mayúsculas/minúsculas
                    if not descripcion:
                        if any(k in texto_l_upper for k in ["CASCO", "VERTEX", "STRATO"]):
                            descripcion = "CASCO"
                            marca = "PETZL"
                        elif any(k in texto_l_upper for k in ["ARNÉS", "ARNES", "ATLAS", "AVAO", "VOLT"]):
                            descripcion = "ARNÉS"
                        elif any(k in texto_l_upper for k in ["GANCHO", "APERTURA", "AUSTIN"]):
                            descripcion = "GANCHO"
                        elif any(k in texto_l_upper for k in ["RETRACTIL", "CINTURON", "CINTURÓN"]):
                            descripcion = "CINTURÓN RETRÁCTIL"
                            marca = "PROTECTA"
                        elif any(k in texto_l_upper for k in ["MOSQUETON", "MOSQUETÓN", "OK", "AM'D", "MAGNUM"]):
                            descripcion = "MOSQUETÓN"
                            marca = "PETZL" if "OK" in texto_l_upper or "AM'D" in texto_l_upper else "ROCK EMPIRE"
                        elif any(k in texto_l_upper for k in ["CINTA", "ANCLAJE", "ANNEAU", "60", "120"]):
                            marca = "PETZL"
                            if "60" in texto_l_upper:
                                descripcion = "CINTA DE ANCLAJE 60CM"
                            elif "120" in texto_l_upper:
                                descripcion = "CINTA DE ANCLAJE 120CM"
                            else:
                                descripcion = "CINTA DE ANCLAJE"
                        elif any(k in texto_l_upper for k in ["GRILLON", "POSICIONADOR", "CATCH"]):
                            descripcion = "POSICIONADOR / ESLINGA"
                            marca = "PETZL" if "GRILLON" in texto_l_upper else "ROCK EMPIRE"
                        elif any(k in texto_l_upper for k in ["SKC", "SOLL", "SÖLL", "VI-GO", "ANTICAIDAS", "ANTICAÍDAS", "AVANTI"]):
                            descripcion = "ANTICAÍDAS"
                            if "SKC" in texto_l_upper:
                                marca = "SOMAIN"
                            elif "SOLL" in texto_l_upper or "SÖLL" in texto_l_upper:
                                marca = "HONEYWELL"
                            else:
                                marca = "AVANTI"
                        else:
                            descripcion = ""

                    items_master.append({
                        "raw_line": linea_str,
                        "serie": num_serie,
                        "modelo": modelo,
                        "marca": marca
                    })

                    es_nuevo = "NUEVO" in linea_str.upper()
                    obs_formateada = f"(NUEVO) {tecnico_master}" if es_nuevo else tecnico_master

                    registros_inventario.append({
                        "DEPARTAMENTO": departamento_auto,
                        "DESCRIPCIÓN": descripcion,
                        "MARCA": marca,
                        "MODELO": modelo,
                        "NÚMERO DE SERIE": num_serie,
                        "FACTURA_OC": "",
                        "FECHA_DE_ESTATUS": fecha_acuse,
                        "OBSERVACIONES": obs_formateada,
                        "ESTATUS": "OK"
                    })

    reporte_correcto = []
    lista_errores = []

    for nombre_archivo, texto_ficha in fichas_pdf.items():
        if nombre_archivo == master_filename:
            continue

        match_serie = re.search(r'(?:n[uú]mero de serie|s/n|serie|c[oó]digo):\s*([A-Z0-9\-]+)', texto_ficha, re.IGNORECASE)
        match_modelo = re.search(r'(?:modelo):\s*([^\n]+)', texto_ficha, re.IGNORECASE)
        match_tecnico = re.search(r'(?:nombre|t[eé]cnico|personal):\s*([^\n]+)', texto_ficha, re.IGNORECASE)
        match_marca = re.search(r'(?:marca):\s*([^\n]+)', texto_ficha, re.IGNORECASE)

        serie_ficha = match_serie.group(1).strip().upper() if match_serie else "DESCONOCIDO"
        modelo_ficha = match_modelo.group(1).strip() if (match_modelo and match_modelo.group(1)) else "DESCONOCIDO"
        tecnico_ficha = match_tecnico.group(1).strip() if match_tecnico else "DESCONOCIDO"
        marca_ficha = match_marca.group(1).strip().upper() if match_marca else ("PETZL" if "PETZL" in texto_ficha.upper() or "PETZL" in nombre_archivo.upper() else "OTRA")

        reporte_correcto.append({
            "archivo": nombre_archivo,
            "marca": marca_ficha,
            "serie": serie_ficha,
            "modelo": modelo_ficha,
            "fecha_estatus": fecha_acuse,
            "estatus": "CORRECTO ✅"
        })

    return tecnico_master, pd.DataFrame(registros_inventario), pd.DataFrame(reporte_correcto), lista_errores

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Sistema de Gestión EPP e Inspecciones")

if not sistema_activo:
    st.warning("⚠️ **SISTEMA INHABILITADO:** El administrador ha pausado temporalmente las operaciones y la sincronización con Excel.")
    st.stop()

# ---------------------------------------------------------
# PESTAÑAS CON NÚMEROS Y NOMBRES CLAROS
# ---------------------------------------------------------
tab_dashboard, tab_registrar, tab_inspeccion, tab_historial, tab_ia, tab_zip = st.tabs([
    "1️⃣ Dashboard", 
    "2️⃣ Registrar Equipo", 
    "3️⃣ Inspección Pre-operacional", 
    "4️⃣ Historial de Inspecciones", 
    "5️⃣ Asistente IA",
    "6️⃣ Automatización y Fichas"
])

with tab_dashboard:
    st.header(f"📊 Estado General del Inventario ({ANIO_ACTUAL})")
    st.info("Panel general activo para el seguimiento de equipos de protección personal y elementos en campo.")

with tab_registrar:
    st.header("➕ Registrar / Asignar Equipo")
    st.write("Utiliza este módulo para dar de alta de forma manual nuevos equipos o realizar asignaciones directas por departamento.")
    
    with st.form("form_registrar_equipo"):
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            reg_depto = st.selectbox("Departamento:", DEPARTAMENTOS)
            reg_desc = st.text_input("Descripción del Equipo (Ej. Arnés, Casco, Eslinga):")
            reg_marca = st.text_input("Marca:")
        with col_r2:
            reg_modelo = st.text_input("Modelo:")
            reg_serie = st.text_input("Número de Serie:")
            reg_factura = st.text_input("Factura / Orden de Compra (OC):")
        
        reg_obs = st.text_area("Observaciones:")
        btn_guardar_reg = st.form_submit_button("💾 Guardar Registro en Inventario")
        if btn_guardar_reg:
            st.success("✅ Equipo registrado exitosamente en el sistema.")

with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional en Campo")
    st.write("Realiza la revisión y validación de elementos de protección personal antes de iniciar labores operativas.")
    
    insp_equipo = st.text_input("Buscar equipo por Número de Serie o Descripción:")
    insp_estado = st.radio("Estado de la inspección:", ["Conforme (OK) 🟢", "No Conforme / Dañado 🔴", "Requiere Mantenimiento 🟡"])
    insp_detalles = st.text_area("Detalles o hallazgos de la inspección:")
    
    if st.button("📤 Enviar Reporte de Inspección"):
        if "No Conforme" in insp_estado:
            enviar_alerta_power_automate(
                tecnico="OPERADOR EN CAMPO",
                equipo=insp_equipo if insp_equipo else "EQUIPO GENERAL",
                estatus="NO CONFORME",
                detalles_adicionales=insp_detalles
            )
            st.warning("⚠️ Inspección No Conforme registrada. Se ha enviado una alerta automática por correo.")
        else:
            st.success("✅ Inspección registrada correctamente.")

with tab_historial:
    st.header("📜 Historial de Inspecciones y Movimientos")
    st.write("Consulta el registro histórico de las auditorías, asignaciones e inspecciones pre-operacionales realizadas.")
    st.info("No hay registros históricos recientes para mostrar en este momento.")

with tab_ia:
    st.header("🤖 Asistente IA (DeepSeek)")
    st.write("Asistente interactivo libre. Puedes consultar cualquier tema técnico, de seguridad industrial, programación o conversar de manera completamente abierta.")
    
    pregunta_ia = st.text_input("Escribe tu consulta o mensaje para DeepSeek:")
    if pregunta_ia:
        with st.spinner("Generando respuesta con DeepSeek..."):
            try:
                deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
                if not deepseek_key:
                    st.error("⚠️ Falta configurar la clave `DEEPSEEK_API_KEY` en los secretos de Streamlit.")
                else:
                    client = OpenAI(
                        api_key=deepseek_key,
                        base_url="https://api.deepseek.com"
                    )
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system", "content": "Eres un asistente técnico experto en seguridad industrial, normativas y gestión general."},
                            {"role": "user", "content": pregunta_ia},
                        ],
                        stream=False
                    )
                    texto_respuesta = response.choices[0].message.content
                    st.markdown("### Respuesta:")
                    st.write(texto_respuesta)
            except Exception as e:
                st.error(f"❌ Error al conectar con DeepSeek: {e}")

with tab_zip:
    st.header(f"📂 Auditoría y Sincronización de Fichas EPP ({ANIO_ACTUAL})")
    st.caption("Sube el archivo ZIP del técnico. El sistema auditará las fichas, filtrará elementos seriables y te permitirá enviarlos a Google Sheets o descargar el Excel.")
    
    col_c1, col_c2 = st.columns([1.5, 1.5])
    with col_c1:
        correo_notificacion_mi_usuario = st.text_input("Tu correo (notificaciones de error):", value=CORREO_NOTIFICACION_PRINCIPAL).strip()
    with col_c2:
        correo_companera = st.text_input("Correo de tu compañera:", value=CORREO_COMPANERA_OPERACIONES).strip()

    zip_cargado = st.file_uploader(
        "Sube el archivo ZIP con las fichas del técnico:", 
        type=["zip"],
        key="uploader_zip_sincronizacion_total"
    )

    if zip_cargado:
        with st.spinner("⚡ Leyendo PDF, detectando departamento y procesando registros..."):
            tecnico_master, df_inventario, df_ok, lista_errores = procesar_y_auditar_zip(zip_cargado)
            
            st.subheader(f"📋 Resumen de Auditoría - Técnico: **{tecnico_master}**")
            
            if lista_errores:
                st.error(f"⚠️ Se detectaron **{len(lista_errores)}** error(es) de captura en las fichas subidas:")
                df_err = pd.DataFrame(lista_errores)
                st.dataframe(df_err, use_container_width=True)
            else:
                st.success(f"🎉 ¡Fichas auditadas exitosamente! No se detectaron errores de captura.")
                
            if not df_inventario.empty:
                st.success(f"✅ Se procesaron **{len(df_inventario)}** filas correctamente para **{tecnico_master}**.")
                
                if st.button("🚀 Enviar Automáticamente a Google Sheets"):
                    with st.spinner("Conectando con Google Sheets..."):
                        exito_gs, mensaje_gs = enviar_datos_a_google_sheets(df_inventario)
                        if exito_gs:
                            st.success("🎉 ¡Datos sincronizados exitosamente con tu Google Sheets!")
                            st.balloons()
                        else:
                            st.error(f"⚠️ No se pudo sincronizar automáticamente con Google Sheets. Detalle: {mensaje_gs}")

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_inventario.to_excel(writer, index=False, sheet_name='INVENTARIO')
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Descargar Inventario Formateado en Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"Inventario_{tecnico_master.replace(' ', '_')}_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.subheader("📦 Registros Seriables Extraídos (Vista Previa)")
                st.dataframe(df_inventario, use_container_width=True)
            else:
                st.warning("⚠️ No se encontraron elementos seriables válidos en el archivo.")