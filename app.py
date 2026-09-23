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
    "USA 118": ["118", "USA", "PERSONAL 118"],
    "REVISIÓN": ["REVISION", "REVISIÓN"],
    "BAJAS": ["BAJA", "BAJAS"]
}

CORREO_NOTIFICACION_PRINCIPAL = "almacen@windsunmx.com"
CORREO_COMPANERA_OPERACIONES = "auxiliaroperaciones@windsunmx.com"

# ---------------------------------------------------------
# FILTRO DE ELEMENTOS SERIABLES Y EXCEPCIÓN DE GUANTES 1000V / CLASE 0
# ---------------------------------------------------------
def es_item_valido_o_excepcion(linea_texto):
    texto_upper = linea_texto.upper()

    if any(k in texto_upper for k in ["WINDSUN", "ENTREGA EPI", "LOCALIDAD", "PUESTO", "FO-09", "FIRMA", "RECIBE"]):
        return False, False

    patron_guantes_dielectricos = r'GUANTE.*(1000|CLASE\s*0|1000V)'
    if re.search(patron_guantes_dielectricos, texto_upper):
        return True, True

    tiene_serie = bool(re.search(r'[A-Z0-9]{5,20}', texto_upper))
    return tiene_serie, False

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

    if any(k in puesto for k in ["MANTENIMIENTO", "TECNICO DE MANTENIMIENTO", "TÉCNICO DE MANTENIMIENTO"]) and any(k in info_contexto for k in ["SAN ROMAN", "SAN ROMÁN", "AUSTIN", "TEXAS", "USA"]):
        return "USA 118"

    if any(k in puesto for k in ["SOLDADOR", "BASTIDOR", "TECNICO BASTIDOR", "TÉCNICO BASTIDOR"]) or "BASTIDOR" in texto_upper:
        return "BASTIDOR 103"

    if any(k in puesto for k in ["PALAS", "TECNICO PALAS", "TÉCNICO PALAS", "LIDER PALAS", "LÍDER PALAS"]) or "PALAS" in texto_upper:
        return "PALAS 105"

    if any(k in puesto for k in ["MANTENIMIENTO", "TECNICO MANTENIMIENTO", "TÉCNICO MANTENIMIENTO"]) or any(k in info_contexto for k in ["JUCHITAN", "JUCHITÁN", "VESTAS", "BII HIOXO", "BIIHIOXO"]):
        return "MANTENIMIENTO 111"

    return "REVISIÓN"

# ---------------------------------------------------------
# ALERTAS VÍA POWER AUTOMATE
# ---------------------------------------------------------
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
# EXTRACCIÓN Y LÓGICA DE AUDITORÍA DE FICHAS
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

    departamento_auto = determinar_departamento_automatico(master_acuse_texto)

    match_tecnico_master = re.search(r'(?:NOMBRE|RECIBE|PERSONAL ASIGNADO|PERSONAL):\s*([^\n]+)', master_acuse_texto, re.IGNORECASE)
    tecnico_master = match_tecnico_master.group(1).strip().upper() if match_tecnico_master else "TÉCNICO NO DETECTADO"

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
                    num_serie = "SIN SERIE (DIELÉCTRICO)"
                    modelo = "CLASE 0 / 1000V"
                    marca = partes[-2] if len(partes) >= 3 else "DESCONOCIDO"
                else:
                    num_serie = partes[1] if len(partes) > 1 else partes[0]
                    modelo = partes[-2] if len(partes) >= 3 else "N/A"
                    marca = "PETZL" if "PETZL" in linea_str.upper() else "OTRA"
                
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
                    "DESCRIPCIÓN": partes[0] if len(partes) > 0 else "EQUIPO EPP",
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
        modelo_ficha = match_modelo.group(1).strip() if modelo_ficha else "DESCONOCIDO"
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
                    "detalle": f"El N/S '{serie_ficha}' no figura en el Acuse EPI."
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
                    "detalle": f"Serie '{serie_ficha}' no coincide con la ficha maestra."
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
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Sistema de Gestión EPP e Inspecciones")

tab_dashboard, tab_registrar, tab_inspeccion, tab_historial, tab_ia, tab_zip = st.tabs([
    "📊 Dashboard", 
    "➕ Registrar Equipo", 
    "📋 Inspección Pre-operacional", 
    "📜 Historial de Inspecciones", 
    "🤖 Asistente IA",
    "📂 Automatización y Fichas"
])

with tab_dashboard:
    st.header(f"📊 Estado General del Inventario ({ANIO_ACTUAL})")

with tab_registrar:
    st.header("➕ Registrar / Asignar Equipo")

with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional en Campo")

with tab_historial:
    st.header("📜 Historial de Inspecciones")

with tab_ia:
    st.header("🤖 Asistente Técnico en Seguridad Industrial y EPP")

# 6. PESTAÑA DE AUDITORÍA Y DESCARGA DIRECTA
with tab_zip:
    st.header(f"📂 Auditoría y Exportación de Fichas EPP ({ANIO_ACTUAL})")
    st.caption("Sube el archivo ZIP del técnico. El sistema auditará las fichas, clasificará el departamento, filtrará los elementos seriables (con excepción de guantes dieléctricos 1000V/Clase 0) y te generará un archivo Excel listo para descargar.")
    
    col_c1, col_c2 = st.columns([1.5, 1.5])
    with col_c1:
        correo_notificacion_mi_usuario = st.text_input("Tu correo (notificaciones de error):", value=CORREO_NOTIFICACION_PRINCIPAL).strip()
    with col_c2:
        correo_companera = st.text_input("Correo de tu compañera:", value=CORREO_COMPANERA_OPERACIONES).strip()

    zip_cargado = st.file_uploader(
        "Sube el archivo ZIP con las fichas del técnico:", 
        type=["zip"],
        key="uploader_zip_descarga"
    )

    if zip_cargado:
        with st.spinner("⚡ Leyendo PDF, detectando departamento y generando archivo..."):
            tecnico_master, df_inventario, df_ok, lista_errores = procesar_y_auditar_zip(zip_cargado)
            
            st.subheader(f"📋 Resumen de Auditoría - Técnico: **{tecnico_master}**")
            
            if lista_errores:
                st.error(f"⚠️ Se detectaron **{len(lista_errores)}** error(es) de captura en las fichas subidas:")
                df_err = pd.DataFrame(lista_errores)
                st.dataframe(df_err, use_container_width=True)
                
                texto_resumen_mail = ""
                for err in lista_errores:
                    texto_resumen_mail += f"• Archivo: {err['archivo']} | Marca: {err['marca']} | Error: {err['tipo_error']} -> {err['detalle']}\n"
                
                if correo_notificacion_mi_usuario:
                    envio_ok = enviar_alerta_errores_usuario(
                        tecnico=tecnico_master,
                        resumen_errores=texto_resumen_mail,
                        correo_notificacion=correo_notificacion_mi_usuario
                    )
                    if envio_ok:
                        st.warning(f"📧 Se envió un informe de corrección a tu correo (**{correo_notificacion_mi_usuario}**).")
            else:
                st.success(f"🎉 ¡Fichas auditadas exitosamente! No se detectaron errores de captura.")
                
            if not df_inventario.empty:
                st.success(f"✅ Se procesaron **{len(df_inventario)}** filas correctamente para **{tecnico_master}**.")
                
                # CREAR ARCHIVO EXCEL EN MEMORIA PARA DESCARGA
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_inventario.to_excel(writer, index=False, sheet_name='INVENTARIO')
                excel_data = output.getvalue()

                # BOTÓN DE DESCARGA DIRECTA
                st.download_button(
                    label="📥 Descargar Inventario Formateado para Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"Inventario_{tecnico_master.replace(' ', '_')}_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.subheader("📦 Registros Seriables Extraídos (Vista Previa)")
                st.dataframe(df_inventario, use_container_width=True)
            else:
                st.warning("⚠️ No se encontraron elementos seriables válidos en el archivo.")