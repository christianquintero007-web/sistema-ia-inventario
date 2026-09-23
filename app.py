import streamlit as st
import pandas as pd
import google.generativeai as genai
import unicodedata
import requests
import zipfile
import io
import re
import pypdf
import gspread
from google.oauth2.service_account import Credentials
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

# Año dinámico activo
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
    "USA 118": ["118", "USA", "PERSONAL 118"],
    "REVISIÓN": ["REVISION", "REVISIÓN"],
    "BAJAS": ["BAJA", "BAJAS"]
}

# CORREOS PREDETERMINADOS DEL SISTEMA
CORREO_NOTIFICACION_PRINCIPAL = "almacen@windsunmx.com"
CORREO_COMPANERA_OPERACIONES = "auxiliaroperaciones@windsunmx.com"

# ---------------------------------------------------------
# ALERTAS VÍA POWER AUTOMATE
# ---------------------------------------------------------
def enviar_alerta_power_automate(tecnico, equipo, estatus, destinatario=CORREO_NOTIFICACION_PRINCIPAL, detalles_adicionales=""):
    webhook_url = st.secrets.get("POWER_AUTOMATE_URL")
    if not webhook_url:
        st.error("⚠️ No se encontró la variable 'POWER_AUTOMATE_URL' en los Secrets de Streamlit.")
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
        st.error("⚠️ No se encontró la variable 'POWER_AUTOMATE_URL' en los Secrets de Streamlit.")
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
# ESCRITURA Y GESTIÓN DINÁMICA DE HOJAS ANUALES EN GOOGLE SHEETS
# ---------------------------------------------------------
def obtener_cliente_gspread():
    try:
        if "gspread" in st.secrets:
            creds_dict = dict(st.secrets["gspread"])
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
        elif "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            creds_dict = dict(st.secrets["connections"]["gsheets"])
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def obtener_o_crear_hoja_anual(sh, nombre_base="INVENTARIO"):
    pestaña_target = f"{nombre_base}_{ANIO_ACTUAL}"
    
    try:
        return sh.worksheet(pestaña_target)
    except Exception:
        try:
            return sh.worksheet(nombre_base)
        except Exception:
            nueva_ws = sh.add_worksheet(title=pestaña_target, rows=1000, cols=10)
            encabezados = [
                "DEPARTAMENTO", "DESCRIPCIÓN", "MARCA", "MODELO", 
                "NÚMERO DE SERIE", "FECHA DE ESTATUS", "TÉCNICO / RESPONSABLE", "OBSERVACIONES", "ESTATUS"
            ]
            nueva_ws.append_row(encabezados)
            return nueva_ws

def sincronizar_o_actualizar_tecnico_sheets(df_nuevos, nombre_pestaña="INVENTARIO"):
    client = obtener_cliente_gspread()
    if not client:
        return False

    try:
        url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = url_base.split("/d/")[1].split("/")[0]
        sh = client.open_by_key(sheet_id)
        
        worksheet = obtener_o_crear_hoja_anual(sh, nombre_pestaña)
        valores = df_nuevos.astype(str).values.tolist()
        worksheet.append_rows(valores)
        return True
    except Exception as e:
        st.error(f"Error al escribir en Google Sheets: {e}")
        return False

# ---------------------------------------------------------
# LÓGICA DE AUDITORÍA Y EXTRACTION DE ACUSE EPI
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

def procesar_y_auditar_zip(archivo_zip_subido, departamento_sel="PENDIENTE"):
    fichas_pdf = {}
    master_acuse_texto = ""
    master_filename = ""

    with zipfile.ZipFile(archivo_zip_subido, 'r') as z:
        archivos_pdf = [nombre for nombre in z.namelist() if nombre.lower().endswith('.pdf')]
        if not archivos_pdf:
            return None, pd.DataFrame(), pd.DataFrame(), []

        for nombre in archivos_pdf:
            with z.open(nombre) as f_pdf:
                stream = io.BytesIO(f_pdf.read())
                texto = extraer_datos_pdf_individual(stream)
                fichas_pdf[nombre] = texto
                
                if any(k in nombre.lower() for k in ["fo-09", "fo09", "entrega de epi", "entrega epi"]) or "ENTREGA EPI" in texto.upper():
                    master_acuse_texto = texto
                    master_filename = nombre

    # 1. Extraer Técnico del Acuse Maestro
    match_tecnico_master = re.search(r'(?:NOMBRE|RECIBE|PERSONAL ASIGNADO|PERSONAL):\s*([^\n]+)', master_acuse_texto, re.IGNORECASE)
    tecnico_master = match_tecnico_master.group(1).strip().upper() if match_tecnico_master else "TÉCNICO NO DETECTADO"

    # 2. Extraer Fecha del Acuse EPI (ubica la fecha del formato/firma en la parte inferior o encabezado)
    match_fechas = re.findall(r'\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b', master_acuse_texto)
    fecha_acuse = match_fechas[-1] if match_fechas else date.today().strftime("%Y-%m-%d")

    # 3. Construir items maestros y registros para la hoja de Inventario
    items_master = []
    registros_inventario = []
    lineas = master_acuse_texto.split('\n')

    for l in lineas:
        linea_str = l.strip()
        if re.search(r'[A-Z0-9]{5,20}', linea_str) and not any(k in linea_str.upper() for k in ["WINDSUN", "ENTREGA EPI", "LOCALIDAD", "PUESTO", "FO-09"]):
            partes = linea_str.split()
            if len(partes) >= 2:
                num_serie = partes[1] if len(partes) > 1 else partes[0]
                modelo = partes[-2] if len(partes) >= 3 else "N/A"
                marca = "PETZL" if "PETZL" in linea_str.upper() else "OTRA"
                
                items_master.append({
                    "raw_line": linea_str,
                    "serie": num_serie,
                    "modelo": modelo,
                    "marca": marca
                })

                # Regla de formato para OBSERVACIONES y FECHA DE ESTATUS
                es_nuevo = "NUEVO" in linea_str.upper()
                obs_formateada = f"(NUEVO) {tecnico_master}" if es_nuevo else tecnico_master

                registros_inventario.append({
                    "DEPARTAMENTO": departamento_sel,
                    "DESCRIPCIÓN": partes[0] if len(partes) > 0 else "EQUIPO EPP",
                    "MARCA": marca,
                    "MODELO": modelo,
                    "NÚMERO DE SERIE": num_serie,
                    "FECHA DE ESTATUS": fecha_acuse,
                    "TÉCNICO / RESPONSABLE": tecnico_master,
                    "OBSERVACIONES": obs_formateada,
                    "ESTATUS": "OK"
                })

    # 4. Auditar cada Ficha Individual
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
        modelo_ficha = match_modelo.group(1).strip() if match_modelo else "DESCONOCIDO"
        tecnico_ficha = match_tecnico.group(1).strip() if match_tecnico else "DESCONOCIDO"
        marca_ficha = match_marca.group(1).strip().upper() if match_marca else ("PETZL" if "PETZL" in texto_ficha.upper() or "PETZL" in nombre_archivo.upper() else "OTRA")

        if "PETZL" in marca_ficha:
            coincidencia_serie = any(item["serie"].upper() in texto_ficha.upper() or serie_ficha in item["serie"].upper() for item in items_master)
            coincidencia_modelo = any(item["modelo"].upper() in modelo_ficha.upper() or modelo_ficha.upper() in item["raw_line"].upper() for item in items_master)

            if not coincidencia_serie:
                lista_errores.append({
                    "archivo": nombre_archivo,
                    "tecnico": tecnico_master,
                    "marca": "PETZL",
                    "tipo_error": "Número de Serie No Coincide",
                    "detalle": f"El N/S '{serie_ficha}' no figura en el Acuse EPI del año {ANIO_ACTUAL}."
                })
            elif not coincidencia_modelo and modelo_ficha != "DESCONOCIDO":
                lista_errores.append({
                    "archivo": nombre_archivo,
                    "tecnico": tecnico_master,
                    "marca": "PETZL",
                    "tipo_error": "Modelo Incorrecto / Discordante",
                    "detalle": f"El modelo '{modelo_ficha}' no coincide con el registrado en el Acuse EPI."
                })
            else:
                reporte_correcto.append({
                    "archivo": nombre_archivo,
                    "marca": "PETZL",
                    "serie": serie_ficha,
                    "modelo": modelo_ficha,
                    "fecha_estatus": fecha_acuse,
                    "estatus": "CORRECTO ✅"
                })
        else:
            coincidencia_serie = any(item["serie"].upper() in texto_ficha.upper() or serie_ficha in item["serie"].upper() for item in items_master)
            coincidencia_tecnico = (tecnico_ficha.upper() in tecnico_master.upper()) or (tecnico_master.upper() in tecnico_ficha.upper()) or tecnico_ficha == "DESCONOCIDO"

            if not coincidencia_serie:
                lista_errores.append({
                    "archivo": nombre_archivo,
                    "tecnico": tecnico_master,
                    "marca": marca_ficha,
                    "tipo_error": "Número de Serie Mal Copiado",
                    "detalle": f"Serie '{serie_ficha}' no coincide con la ficha maestra del año {ANIO_ACTUAL}."
                })
            elif not coincidencia_tecnico:
                lista_errores.append({
                    "archivo": nombre_archivo,
                    "tecnico": tecnico_master,
                    "marca": marca_ficha,
                    "tipo_error": "Nombre de Técnico Incoherente",
                    "detalle": f"Técnico en ficha '{tecnico_ficha}' difiere del Acuse EPI '{tecnico_master}'."
                })
            else:
                reporte_correcto.append({
                    "archivo": nombre_archivo,
                    "marca": marca_ficha,
                    "serie": serie_ficha,
                    "tecnico": tecnico_master,
                    "fecha_estatus": fecha_acuse,
                    "estatus": "CORRECTO ✅"
                })

    return tecnico_master, pd.DataFrame(registros_inventario), pd.DataFrame(reporte_correcto), lista_errores

# ---------------------------------------------------------
# CARGA Y NORMALIZACIÓN DESDE GOOGLE SHEETS
# ---------------------------------------------------------
def normalizar_encabezado(texto):
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

def coincide_departamento(val_celda, dep_seleccionado):
    val_str = str(val_celda).upper().strip()
    dep_str = str(dep_seleccionado).upper().strip()
    
    if not val_str or val_str == "NAN":
        return False
        
    if val_str == dep_str:
        return True

    if dep_seleccionado in MAPA_DEPARTAMENTOS:
        palabras_clave = MAPA_DEPARTAMENTOS[dep_seleccionado]
        for kw in palabras_clave:
            if kw in val_str:
                return True

    nums_val = ''.join(filter(str.isdigit, val_str))
    nums_dep = ''.join(filter(str.isdigit, dep_str))
    if nums_val and nums_dep and nums_val == nums_dep:
        return True

    return val_str in dep_str or dep_str in val_str

def cargar_hoja_csv(pestaña_base):
    try:
        url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = url_base.split("/d/")[1].split("/")[0]
        
        pestaña_target = f"{pestaña_base}_{ANIO_ACTUAL}"
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={pestaña_target}"
        
        try:
            df = pd.read_csv(url_csv)
        except Exception:
            url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={pestaña_base}"
            df = pd.read_csv(url_csv)
        
        if not df.empty:
            df.columns = [normalizar_encabezado(col) for col in df.columns]
            df = df.loc[:, ~df.columns.str.startswith('unnamed')]
            
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Sistema de Gestión EPP e Inspecciones")

tab_dashboard, tab_registrar, tab_inspeccion, tab_historial, tab_ia, tab_zip = st.tabs([
    "📊 Dashboard", 
    "➕ Registrar Equipo", 
    "📋 Inspección Pre-operacional", 
    "📜 Historial de Inspecciones", 
    "🤖 Asistente IA",
    "📂 Auditar Fichas (.ZIP)"
])

# 1. DASHBOARD
with tab_dashboard:
    st.header(f"📊 Estado General del Inventario ({ANIO_ACTUAL})")
    df_inv = cargar_hoja_csv("INVENTARIO")
    dep_filtro = st.selectbox("Filtrar por Departamento / Área:", ["TODOS"] + DEPARTAMENTOS)
    
    if not df_inv.empty:
        col_dep = next((c for c in df_inv.columns if "dep" in c or "area" in c or "columna1" in c), None)
        if dep_filtro != "TODOS" and col_dep:
            df_view = df_inv[df_inv[col_dep].apply(lambda x: coincide_departamento(x, dep_filtro))]
        else:
            df_view = df_inv
            
        total_equipos = len(df_view)
        col_estatus = next((c for c in df_view.columns if "estatus" in c or "estado" in c), None)
        
        if col_estatus:
            ok_count = len(df_view[df_view[col_estatus].astype(str).str.lower().str.contains("ok|conforme")])
            no_ok_count = total_equipos - ok_count
        else:
            ok_count = total_equipos
            no_ok_count = 0
            
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Equipos / Registros", total_equipos)
        c2.metric("Operativos / OK ✅", ok_count)
        c3.metric("En Revisión / Pendientes ❌", no_ok_count)
        
        st.divider()
        st.dataframe(df_view, use_container_width=True)
    else:
        st.info("La tabla de Inventario está vacía o cargando datos.")

# 2. REGISTRAR EQUIPO
with tab_registrar:
    st.header("➕ Registrar / Asignar Equipo")
    st.caption("Usa este formulario para dar de alta equipos nuevos o actualizar la asignación de un técnico.")
    
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            departamento = st.selectbox("DEPARTAMENTO", DEPARTAMENTOS)
            descripcion = st.text_input("DESCRIPCIÓN", placeholder="ej. Arnés de Cuerpos Entero / Casco").strip()
            marca = st.text_input("MARCA", placeholder="ej. Rock Empire, Petzl").strip()
            modelo = st.text_input("MODELO", placeholder="ej. Atlas Lock Al Belt").strip()
        with col2:
            num_serie = st.text_input("NÚMERO DE SERIE / CÓDIGO", placeholder="ej. 24CUA900009").strip().upper()
            factura_oc = st.text_input("FACTURA / OC", placeholder="ej. F-1234 / OC-5678").strip()
            fecha_estatus = st.date_input("FECHA DE ESTATUS / INGRESO")
            tecnico_resp = st.text_input("TÉCNICO / RESPONSABLE ASIGNADO", placeholder="ej. Juan Pérez").strip()
            
        motivo_registro = st.selectbox("TIPO DE REGISTRO / CONDICIÓN", [
            "Ingreso de equipo nuevo", 
            "Asignación a técnico", 
            "Reemplazo por desgaste", 
            "Otro"
        ])
        
        obs_adicionales = st.text_area("DETALLES / OBSERVACIONES ADICIONALES", placeholder="Escribe notas adicionales...")
        btn_guardar = st.form_submit_button("💾 Registrar Equipo")
        
        if btn_guardar:
            if num_serie or descripcion:
                obs_final = f"Téc: {tecnico_resp if tecnico_resp else 'N/A'} | {motivo_registro}"
                if obs_adicionales:
                    obs_final += f" | {obs_adicionales}"
                    
                st.success(f"✅ Registro completado para **{num_serie if num_serie else descripcion}**")
                st.markdown(f"**Observación generada:** `{obs_final}`")
            else:
                st.warning("⚠️ Completa al menos la DESCRIPCIÓN o NÚMERO DE SERIE.")

# 3. INSPECCIÓN PRE-OPERACIONAL
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional en Campo")
    df_insp_data = cargar_hoja_csv("INSPECCIONES")
    if df_insp_data.empty:
        df_insp_data = cargar_hoja_csv("INVENTARIO")
        
    if df_insp_data.empty:
        st.warning("⚠️ No se encontraron datos registrados en Google Sheets.")
    else:
        dep_insp = st.selectbox("Selecciona Departamento / Área:", DEPARTAMENTOS, key="dep_insp")
        col_dep = next((c for c in df_insp_data.columns if "dep" in c or "area" in c or "columna1" in c), None)
        
        if col_dep:
            df_dep = df_insp_data[df_insp_data[col_dep].apply(lambda x: coincide_departamento(x, dep_insp))]
        else:
            df_dep = df_insp_data
            
        col_identificador = next((c for c in df_dep.columns if any(k in c for k in ["serie", "codigo", "palas", "personal", "tecnico", "descripcion"])), df_dep.columns[0] if not df_dep.empty else None)
        
        if df_dep.empty or not col_identificador:
            st.info(f"No hay registros cargados bajo el área **{dep_insp}**.")
        else:
            elementos_disponibles = df_dep[col_identificador].dropna().astype(str).unique().tolist()
            
            col_a, col_b = st.columns(2)
            with col_a:
                item_sel = st.selectbox("Selecciona Equipo / Personal a Verificar:", elementos_disponibles)
            with col_b:
                inspector = st.text_input("TÉCNICO / INSPECTOR QUE VERIFICA", placeholder="ej. Ing. Carlos R.").strip()
            
            st.subheader("Criterios Normativos de Inspección")
            c1 = st.checkbox("Cintas / Cuerdas: Sin cortes, desgaste, quemaduras ni hilos sueltos.")
            c2 = st.checkbox("Costuras de Seguridad: Continuas e íntegras.")
            c3 = st.checkbox("Partes Metálicas / Hebillas: Sin deformaciones, fisuras ni corrosión.")
            
            obs_insp = st.text_area("Observaciones / Hallazgos de la Inspección")
            
            if st.button("📝 Guardar Inspección"):
                resultado = "ok" if (c1 and c2 and c3) else "no conforme"
                fecha_hoy = date.today().strftime("%Y-%m-%d")
                inspector_str = inspector if inspector else "No especificado"
                
                if resultado == "ok":
                    st.success(f"✅ Inspección registrada para **{item_sel}** ({dep_insp}): **OK**")
                else:
                    st.error(f"❌ Inspección para **{item_sel}** ({dep_insp}): **NO CONFORME**")
                    enviar_alerta_power_automate(
                        tecnico=inspector_str,
                        equipo=f"{item_sel} ({dep_insp})",
                        estatus="NO CONFORME",
                        destinatario=CORREO_NOTIFICACION_PRINCIPAL,
                        detalles_adicionales=obs_insp
                    )
                
                st.caption(f"Inspector: {inspector_str} | Fecha: {fecha_hoy} | Hallazgo: {obs_insp if obs_insp else 'Sin novedad'}")

# 4. HISTORIAL DE INSPECCIONES
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp = cargar_hoja_csv("INSPECCIONES")
    
    if not df_insp.empty:
        dep_hist = st.selectbox("Filtrar por Departamento:", ["TODOS"] + DEPARTAMENTOS, key="dep_hist")
        col_dep_h = next((c for c in df_insp.columns if "dep" in c or "area" in c or "columna1" in c), None)
        
        if dep_hist != "TODOS" and col_dep_h:
            df_insp_view = df_insp[df_insp[col_dep_h].apply(lambda x: coincide_departamento(x, dep_hist))]
        else:
            df_insp_view = df_insp
            
        st.dataframe(df_insp_view, use_container_width=True)
    else:
        st.info("Aún no existen registros en la pestaña de Inspecciones.")

# 5. ASISTENTE IA (DUAL: DEEPSEEK + GOOGLE GEMINI)
with tab_ia:
    st.header("🤖 Asistente Técnico en Seguridad Industrial y EPP")
    st.caption("Consultor automático adaptado al Marco Jurídico Mexicano vigente (STPS), Normas Oficiales (NOMs), normatividad internacional (OSHA, ANSI, NFPA), soporte en Excel y consultas generales.")
    
    col_motor, col_dummy = st.columns([1.5, 1.5])
    with col_motor:
        motor_ia = st.radio(
            "Selecciona el motor de IA:",
            [
                "🚀 DeepSeek (DeepSeek-V3 - Rápido y Racional)", 
                "🌐 Gemini (Google)"
            ],
            index=0
        )
    
    pregunta = st.text_input("Escribe tu consulta:")
    
    if st.button("🔍 Consultar IA"):
        if pregunta:
            prompt_sistema = """
REGLA ESTRICTA DE IDIOMA:
- RESPONDE EXCLUSIVAMENTE EN ESPAÑOL DESDE LA PRIMERA PALABRA. 
- Queda estrictamente prohibido incluir introducciones, prefijos o saludos en inglés.

MARCO JURÍDICO Y NORMATIVO DINÁMICO:
1. Actúa como Ingeniero Especialista en Seguridad Industrial, Salud Ocupacional e Inspección de EPP/EPI en México.
2. Aplica automáticamente el Marco Jurídico Mexicano vigente en materia de Seguridad y Salud en el Trabajo (Ley Federal del Trabajo, Reglamento Federal de SST y las Normas Oficiales Mexicanas de la STPS en sus versiones más recientes y actualizadas a la fecha, incluyendo NOM-017-STPS, NOM-009-STPS, NOM-031-STPS, etc.).
3. Identifica e integra de forma autónoma la Norma Oficial Mexicana vigente que aplique a la consulta del usuario, sin necesidad de que el usuario especifique la norma, la clave o el año.
4. Complementa con estándares internacionales vigentes de referencia para trabajo en altura e inspección técnica (ANSI/ASSP, OSHA, NFPA, EN/CE) cuando aporte rigor técnico.
5. Para consultas de ámbito general (fórmulas o macros de Excel, redacción de reportes técnicos, gestión operativa), responde directamente con el mismo rigor, claridad y estructura en español.
"""
            if "DeepSeek" in motor_ia:
                try:
                    if "DEEPSEEK_API_KEY" not in st.secrets:
                        st.error("❌ Falta la clave 'DEEPSEEK_API_KEY' en los Secrets de Streamlit.")
                    else:
                        client_ds = OpenAI(
                            api_key=st.secrets["DEEPSEEK_API_KEY"].strip(),
                            base_url="https://api.deepseek.com"
                        )
                        with st.spinner("🚀 Generando respuesta técnica con DeepSeek..."):
                            response = client_ds.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": prompt_sistema},
                                    {"role": "user", "content": pregunta}
                                ],
                                temperature=0.3
                            )
                            st.markdown(response.choices[0].message.content)
                            st.caption("🤖 *Respuesta generada por: `DeepSeek-V3 (deepseek-chat)`*")
                except Exception as e:
                    st.error(f"Error al conectar con DeepSeek: {e}")
            else:
                try:
                    if "GEMINI_API_KEY" not in st.secrets:
                        st.error("❌ Falta la clave 'GEMINI_API_KEY' en los Secrets de Streamlit.")
                    else:
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
                        prompt_full = f"{prompt_sistema}\n\nConsulta del usuario: {pregunta}"
                        response = None
                        modelo_usado = None
                        with st.spinner("Generando respuesta con Google Gemini..."):
                            modelos_rapidos = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
                            for mod_name in modelos_rapidos:
                                try:
                                    model = genai.GenerativeModel(mod_name)
                                    response = model.generate_content(prompt_full)
                                    modelo_usado = mod_name
                                    break
                                except Exception:
                                    continue
                            if response and hasattr(response, 'text'):
                                st.markdown(response.text)
                                st.caption(f"🤖 *Respuesta generada por: `{modelo_usado}`*")
                            else:
                                st.error("❌ No se pudo conectar con Gemini.")
                except Exception as e:
                    st.error(f"Error al conectar con Gemini: {e}")

# 6. AUDITORÍA Y CONTROL DE CALIDAD EN FICHAS (.ZIP) CON FILTRO DE AÑO
with tab_zip:
    st.header(f"📂 Auditar y Corregir Fichas de Técnico (Año Activo: {ANIO_ACTUAL})")
    st.caption(f"Evalúa automáticamente las fichas del año **{ANIO_ACTUAL}**. Registra todo el acuse EPI en el inventario con el formato de observaciones y fecha correspondiente.")
    
    col_c1, col_c2, col_c3 = st.columns([1.5, 1.5, 1])
    with col_c1:
        correo_notificacion_mi_usuario = st.text_input("Tu correo (para recibir notificaciones de error):", value=CORREO_NOTIFICACION_PRINCIPAL).strip()
    with col_c2:
        correo_companera = st.text_input("Correo de tu compañera (colaboradora):", value=CORREO_COMPANERA_OPERACIONES).strip()
    with col_c3:
        dep_destino = st.selectbox("Departamento:", DEPARTAMENTOS)

    zip_cargado = st.file_uploader(
        f"Sube el archivo ZIP con las fichas del técnico ({ANIO_ACTUAL}):", 
        type=["zip"],
        key="uploader_zip_acuses"
    )

    if zip_cargado:
        if st.button("🚀 Auditar Fichas y Registrar Acuse EPI"):
            with st.spinner(f"Analizando fichas para el período {ANIO_ACTUAL}..."):
                tecnico_master, df_inventario, df_ok, lista_errores = procesar_y_auditar_zip(zip_cargado, departamento_sel=dep_destino)
                
                st.subheader(f"📋 Resumen de Auditoría ({ANIO_ACTUAL}) - Técnico: **{tecnico_master}**")
                
                if lista_errores:
                    st.error(f"⚠️ Se detectaron **{len(lista_errores)}** error(es) de captura en las fichas subidas:")
                    
                    df_err = pd.DataFrame(lista_errores)
                    st.dataframe(df_err, use_container_width=True)
                    
                    texto_resumen_mail = ""
                    for err in lista_errores:
                        texto_resumen_mail += f"• Archivo: {err['archivo']} | Marca: {err['marca']} | Error: {err['tipo_error']} -> {err['detalle']}\n"
                    
                    if correo_notificacion_mi_usuario:
                        with st.spinner("Enviando aviso de errores a tu correo..."):
                            envio_ok = enviar_alerta_errores_usuario(
                                tecnico=tecnico_master,
                                resumen_errores=texto_resumen_mail,
                                correo_notificacion=correo_notificacion_mi_usuario
                            )
                            if envio_ok:
                                st.warning(f"📧 Se envió una notificación de ajuste a tu correo (**{correo_notificacion_mi_usuario}**).")
                            else:
                                st.info("No se pudo enviar el correo automático (revisa la URL de Power Automate).")
                else:
                    st.success(f"🎉 ¡Fichas del año {ANIO_ACTUAL} auditadas exitosamente! No se encontraron errores humanos.")
                    
                    # Sincronización completa a la hoja INVENTARIO de Google Sheets
                    if not df_inventario.empty:
                        sincronizar_o_actualizar_tecnico_sheets(df_inventario, nombre_pestaña="INVENTARIO")
                        st.balloons()
                        st.success(f"✅ Se registró el Acuse EPI completo del técnico **{tecnico_master}** en Google Sheets con sus fechas de estatus y formato de observaciones.")

                if not df_inventario.empty:
                    st.subheader(f"📦 Registros Extraídos del Acuse EPI para Inventario ({ANIO_ACTUAL})")
                    st.dataframe(df_inventario, use_container_width=True)