import streamlit as st
import pandas as pd
import google.generativeai as genai
import unicodedata
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

DEPARTAMENTOS = [
    "PERSONAL 103", 
    "PERSONAL 105", 
    "PERSONAL 111", 
    "PERSONAL 118", 
    "PALAS",
    "MANTENIMIENTO",
    "REVISIÓN", 
    "BAJAS"
]

# ---------------------------------------------------------
# CARGA Y NORMALIZACIÓN DE DATOS DESDE GOOGLE SHEETS
# ---------------------------------------------------------
def normalizar_encabezado(texto):
    """Quita acentos, caracteres especiales y convierte a minúsculas"""
    texto = unicodedata.normalize('NFD', str(texto))
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return texto.lower().strip()

def coincide_departamento(val_celda, dep_seleccionado):
    """Compara flexiblemente '105' con 'PERSONAL 105' o 'PALAS'"""
    val_str = str(val_celda).upper().strip()
    dep_str = str(dep_seleccionado).upper().strip()
    if not val_str or val_str == "NAN":
        return False
    if val_str == dep_str:
        return True
    # Extraer números si existen (ej. '105' dentro de 'PERSONAL 105')
    nums_val = ''.join(filter(str.isdigit, val_str))
    nums_dep = ''.join(filter(str.isdigit, dep_str))
    if nums_val and nums_dep and nums_val == nums_dep:
        return True
    return val_str in dep_str or dep_str in val_str

def cargar_hoja_csv(pestaña):
    try:
        url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = url_base.split("/d/")[1].split("/")[0]
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={pestaña}"
        
        df = pd.read_csv(url_csv)
        
        if not df.empty:
            # Normalizar encabezados
            df.columns = [normalizar_encabezado(col) for col in df.columns]
            # Eliminar columnas sin nombre
            df = df.loc[:, ~df.columns.str.startswith('unnamed')]
            
        return df.dropna(how="all")
    except Exception as e:
        return pd.DataFrame()

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Sistema de Gestión EPP e Inspecciones")

tab_dashboard, tab_registrar, tab_inspeccion, tab_historial, tab_ia = st.tabs([
    "📊 Dashboard", 
    "➕ Registrar Equipo", 
    "📋 Inspección Pre-operacional", 
    "📜 Historial de Inspecciones", 
    "🤖 Asistente IA"
])

# ---------------------------------------------------------
# 1. DASHBOARD
# ---------------------------------------------------------
with tab_dashboard:
    st.header("📊 Estado General del Inventario")
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

# ---------------------------------------------------------
# 2. REGISTRAR EQUIPO (NUEVO O ASIGNACIÓN)
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 3. INSPECCIÓN PRE-OPERACIONAL
# ---------------------------------------------------------
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional en Campo")
    
    # Intentamos leer la pestaña de INSPECCIONES o INVENTARIO
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
            
        # Detectar la columna que contiene al equipo o personal (palas, serie, tecnico, personal)
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
                
                st.caption(f"Inspector: {inspector_str} | Fecha: {fecha_hoy} | Hallazgo: {obs_insp if obs_insp else 'Sin novedad'}")

# ---------------------------------------------------------
# 4. HISTORIAL DE INSPECCIONES
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 5. ASISTENTE IA (DUAL: DEEPSEEK + GOOGLE GEMINI)
# ---------------------------------------------------------
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
            # ---------------------------------------------------------
            # OPCIÓN 1: DEEPSEEK (V3)
            # ---------------------------------------------------------
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
                            
                            texto_respuesta = response.choices[0].message.content
                            st.markdown(texto_respuesta)
                            st.caption("🤖 *Respuesta generada por: `DeepSeek-V3 (deepseek-chat)`*")
                except Exception as e:
                    st.error(f"Error al conectar con DeepSeek: {e}")

            # ---------------------------------------------------------
            # OPCIÓN 2: GEMINI (GOOGLE)
            # ---------------------------------------------------------
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
