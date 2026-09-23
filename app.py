import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date

# Configuración inicial
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones EPP", 
    page_icon="🛡️", 
    layout="wide"
)

# LISTA EXACTA DE TUS DEPARTAMENTOS / SECCIONES
DEPARTAMENTOS = [
    "PERSONAL 103", 
    "PERSONAL 105", 
    "PERSONAL 118", 
    "REVISIÓN", 
    "BAJAS"
]

# ---------------------------------------------------------
# CARGA Y LIMPIEZA DE DATOS DESDE GOOGLE SHEETS
# ---------------------------------------------------------
def cargar_hoja_csv(pestaña):
    try:
        url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = url_base.split("/d/")[1].split("/")[0]
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={pestaña}"
        
        df = pd.read_csv(url_csv)
        
        if not df.empty:
            # Normalizar nombres de columnas (minúsculas y sin espacios extra)
            df.columns = [str(col).strip().lower() for col in df.columns]
            # Eliminar columnas fantasma / unnamed
            df = df.loc[:, ~df.columns.str.startswith('unnamed')]
            
        return df.dropna(how="all")
    except Exception as e:
        return pd.DataFrame()

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.title("🛡️ Gestión de Inventario e Inspecciones de EPP")

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
    st.header("📊 Estado General por Departamento")
    df_inv = cargar_hoja_csv("INVENTARIO")
    
    dep_filtro = st.selectbox("Filtrar Dashboard por Departamento:", ["TODOS"] + DEPARTAMENTOS)
    
    if not df_inv.empty:
        if dep_filtro != "TODOS" and "departamento" in df_inv.columns:
            df_view = df_inv[df_inv["departamento"].astype(str).str.upper() == dep_filtro.upper()]
        else:
            df_view = df_inv
            
        total_equipos = len(df_view)
        conformes = len(df_view[df_view["estado"].astype(str).str.lower() == "ok"]) if "estado" in df_view.columns else 0
        no_conformes = len(df_view[df_view["estado"].astype(str).str.lower() != "ok"]) if "estado" in df_view.columns else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Equipos", total_equipos)
        c2.metric("Conformes ✅", conformes)
        c3.metric("No Conformes / Detalle ❌", no_conformes)
        
        st.divider()
        st.dataframe(df_view, use_container_width=True)
    else:
        st.info("La tabla de Inventario está vacía o cargando datos.")

# ---------------------------------------------------------
# 2. REGISTRAR EQUIPO
# ---------------------------------------------------------
with tab_registrar:
    st.header("➕ Registrar Nuevo Equipo")
    
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            codigo = st.text_input("Código / N° de Serie (ej. 24CUA900009)").strip().upper()
            departamento = st.selectbox("Departamento / Área Asignada", DEPARTAMENTOS)
            modelo = st.text_input("Modelo (ej. Atlas Lock Al Belt)").strip()
        with col2:
            marca = st.text_input("Marca (ej. Rock Empire, Petzl)").strip()
            fecha_fab = st.date_input("Fecha de Fabricación / Ingreso")
            estado_ini = st.selectbox("Estado Inicial", ["ok", "no conforme"])
            
        obs = st.text_area("Observaciones Iniciales", value="nuevo")
        btn_guardar = st.form_submit_button("💾 Registrar Equipo")
        
        if btn_guardar:
            if codigo and marca:
                st.success(f"✅ Equipo **{codigo}** registrado para **{departamento}**.")
                st.info("💡 Recuerda que puedes agregarlo directamente en Google Sheets o sincronizarlo en Excel.")
            else:
                st.warning("⚠️ Completa al menos el Código y la Marca.")

# ---------------------------------------------------------
# 3. INSPECCIÓN PRE-OPERACIONAL
# ---------------------------------------------------------
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional en Campo")
    df_inv = cargar_hoja_csv("INVENTARIO")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.warning("⚠️ No hay equipos registrados en el inventario.")
    else:
        dep_insp = st.selectbox("Selecciona Departamento / Área:", DEPARTAMENTOS, key="dep_insp")
        
        # Filtrar equipos por el departamento seleccionado
        if "departamento" in df_inv.columns:
            df_dep = df_inv[df_inv["departamento"].astype(str).str.upper() == dep_insp.upper()]
        else:
            df_dep = df_inv
            
        codigos_disponibles = df_dep["codigo"].dropna().astype(str).unique().tolist()
        
        if not codigos_disponibles:
            st.info(f"No hay equipos registrados bajo el área **{dep_insp}**.")
        else:
            codigo_sel = st.selectbox("Selecciona el Código del Equipo:", codigos_disponibles)
            
            st.subheader("Puntos de Verificación Normativa")
            c1 = st.checkbox("Cintas / Cuerdas: Sin cortes, desgaste, quemaduras ni hilos sueltos.")
            c2 = st.checkbox("Costuras de Seguridad: Continuas e íntegras.")
            c3 = st.checkbox("Partes Metálicas / Hebillas: Sin deformaciones, fisuras ni corrosión.")
            
            obs_insp = st.text_area("Observaciones / Hallazgos de la Inspección")
            
            if st.button("📝 Guardar Inspección"):
                resultado = "ok" if (c1 and c2 and c3) else "no conforme"
                fecha_hoy = date.today().strftime("%Y-%m-%d")
                
                if resultado == "ok":
                    st.success(f"✅ Inspección registrada para **{codigo_sel}** ({dep_insp}): **OK**")
                else:
                    st.error(f"❌ Inspección para **{codigo_sel}** ({dep_insp}): **NO CONFORME**")

# ---------------------------------------------------------
# 4. HISTORIAL DE INSPECCIONES
# ---------------------------------------------------------
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp = cargar_hoja_csv("INSPECCIONES")
    
    if not df_insp.empty:
        dep_hist = st.selectbox("Filtrar por Departamento:", ["TODOS"] + DEPARTAMENTOS, key="dep_hist")
        if dep_hist != "TODOS" and "departamento" in df_insp.columns:
            df_insp_view = df_insp[df_insp["departamento"].astype(str).str.upper() == dep_hist.upper()]
        else:
            df_insp_view = df_insp
            
        st.dataframe(df_insp_view, use_container_width=True)
    else:
        st.info("Aún no existen registros en la pestaña de Inspecciones.")

# ---------------------------------------------------------
# 5. ASISTENTE IA
# ---------------------------------------------------------
with tab_ia:
    st.header("🤖 Asistente Técnico de Seguridad e Inspección")
    st.caption("Consulta criterios de rechazo de equipos, normas NOM-017-STPS, OSHA, etc.")
    
    pregunta = st.text_input("Escribe tu consulta técnica:")
    
    if st.button("🔍 Consultar IA"):
        if pregunta:
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ Falta la clave 'GEMINI_API_KEY' en los Secrets de Streamlit.")
                else:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    with st.spinner("Analizando criterio técnico..."):
                        prompt = f"Eres un Ingeniero especialista en Seguridad Industrial y EPP de altura. Responde técnicamente: {pregunta}"
                        response = model.generate_content(prompt)
                        st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {e}")
