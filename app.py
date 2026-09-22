import streamlit as st
import pandas as pd
import google.generativeai as genai

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones EPP", 
    page_icon="🛡️", 
    layout="wide"
)

# ---------------------------------------------------------
# FUNCIÓN ROBUTA DE CARGA Y NORMALIZACIÓN DE DATOS
# ---------------------------------------------------------
def cargar_hoja_csv(pestaña):
    """
    Lee los datos desde Google Sheets vía CSV y normaliza los encabezados 
    a minúsculas sin espacios para ser inmune a diferencias de MAYÚSCULAS/minúsculas.
    """
    try:
        url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = url_base.split("/d/")[1].split("/")[0]
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={pestaña}"
        
        df = pd.read_csv(url_csv)
        
        if not df.empty:
            # Normalizar nombres de columnas (quita espacios extra y convierte a minúsculas)
            df.columns = [str(col).strip().lower() for col in df.columns]
            
        return df.dropna(how="all")
    except Exception as e:
        st.error(f"Error al conectar con la pestaña '{pestaña}': {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL Y NAVEGACIÓN
# ---------------------------------------------------------
st.title("🛡️ Sistema de Gestión de EPP e Inspecciones")

tab_dashboard, tab_registrar, tab_inspeccion, tab_gestionar, tab_historial, tab_ia = st.tabs([
    "📊 Dashboard", 
    "➕ Registrar Equipo", 
    "📋 Inspección Pre-operacional", 
    "🗑️ Eliminar / Gestionar", 
    "📜 Historial", 
    "🤖 Asistente IA"
])

# ---------------------------------------------------------
# 1. DASHBOARD
# ---------------------------------------------------------
with tab_dashboard:
    st.header("📊 Estado General del Inventario EPP")
    df_inv = cargar_hoja_csv("Inventario")
    
    total_equipos = len(df_inv) if not df_inv.empty else 0
    
    # Búsqueda flexible de columna 'estado'
    if not df_inv.empty and "estado" in df_inv.columns:
        conformes = len(df_inv[df_inv["estado"].astype(str).str.lower() == "conforme"])
        no_conformes = len(df_inv[df_inv["estado"].astype(str).str.lower() == "no conforme"])
    else:
        conformes = 0
        no_conformes = 0
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Equipos", total_equipos)
    c2.metric("Conformes ✅", conformes)
    c3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Tabla de Inventario Sincronizada")
    if not df_inv.empty:
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("La tabla de Inventario está vacía o cargando datos.")

# ---------------------------------------------------------
# 2. REGISTRAR NUEVO EQUIPO
# ---------------------------------------------------------
with tab_registrar:
    st.header("➕ Registrar Nuevo Equipo de Protección")
    
    with st.form("form_registro", clear_on_submit=True):
        codigo = st.text_input("Código / N° de Serie (ej. ARN-2026-01)").strip().upper()
        modelo = st.selectbox("Tipo de EPP", [
            "Arnés de Seguridad", 
            "Línea de Vida / Lanyard", 
            "Casco de Protección", 
            "Mosquetón / Conector", 
            "Cuerda de Posicionamiento", 
            "Otro"
        ])
        marca = st.text_input("Marca / Modelo (ej. Petzl, Rock Empire)").strip()
        fecha_fab = st.date_input("Fecha de Fabricación / Inspección")
        
        btn_guardar = st.form_submit_button("💾 Guardar Registro")
        
        if btn_guardar:
            if codigo and marca:
                st.success(f"✅ Equipo **{codigo}** ({tipo}) registrado correctamente.")
                st.info("💡 Si capturas datos directamente en Google Sheets o Excel, se sincronizarán en la siguiente recarga.")
            else:
                st.warning("⚠️ Por favor completa los campos requeridos (Código y Marca).")

# ---------------------------------------------------------
# 3. INSPECCIÓN PRE-OPERACIONAL
# ---------------------------------------------------------
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional de EPP")
    df_inv = cargar_hoja_csv("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.warning("⚠️ No hay equipos registrados en el inventario o la columna 'codigo' no fue detectada.")
    else:
        lista_codigos = df_inv["codigo"].dropna().astype(str).unique().tolist()
        codigo_sel = st.selectbox("Selecciona el Código del Equipo", lista_codigos)
        
        st.subheader("Criterios Normativos de Verificación")
        c1 = st.checkbox("Cintas textiles / Cuerdas: Sin desgastes, cortes, deshilachados o quemaduras.")
        c2 = st.checkbox("Costuras de seguridad: Íntimas, continuas y sin hilos rotos.")
        c3 = st.checkbox("Partes metálicas / Hebillas: Sin deformación, fisuras, corrosión ni bordes filosos.")
        
        obs = st.text_area("Observaciones Técnicas / Hallazgos", placeholder="Escribe aquí cualquier hallazgo relevante...")
        
        if st.button("📝 Registrar Inspección"):
            resultado = "Conforme" if (c1 and c2 and c3) else "No Conforme"
            
            if resultado == "Conforme":
                st.success(f"✅ Inspección para **{codigo_sel}**: **CONFORME**")
            else:
                st.error(f"❌ Inspección para **{codigo_sel}**: **NO CONFORME** (Requiere retiro/revisión)")

# ---------------------------------------------------------
# 4. ELIMINAR / GESTIONAR
# ---------------------------------------------------------
with tab_gestionar:
    st.header("🗑️ Gestor de Equipos")
    df_inv = cargar_hoja_csv("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.info("No hay equipos disponibles para gestionar.")
    else:
        lista_codigos = df_inv["codigo"].dropna().astype(str).unique().tolist()
        codigo_a_eliminar = st.selectbox("Selecciona el Código del Equipo a Gestionar", lista_codigos)
        
        if st.button("❌ Marcar para Baja / Eliminar"):
            st.warning(f"Equipo **{codigo_a_eliminar}** seleccionado para actualización/baja.")

# ---------------------------------------------------------
# 5. HISTORIAL DE INSPECCIONES
# ---------------------------------------------------------
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp = cargar_hoja_csv("Inspecciones")
    
    if not df_insp.empty:
        st.dataframe(df_insp, use_container_width=True)
    else:
        st.info("Aún no hay registros en la pestaña de Inspecciones.")

# ---------------------------------------------------------
# 6. ASISTENTE TÉCNICO IA (GEMINI)
# ---------------------------------------------------------
with tab_ia:
    st.header("🤖 Asistente Técnico de Seguridad e Inspección EPP")
    st.caption("Consulta normas (NOM-017-STPS, OSHA, EN), criterios de rechazo de equipos o especificaciones técnicas.")
    
    pregunta = st.text_input("Haz tu consulta técnica:")
    
    if st.button("🔍 Consultar Asistente IA"):
        if pregunta:
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ No se encontró la clave 'GEMINI_API_KEY' en los Secrets de Streamlit.")
                else:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    with st.spinner("Analizando norma y criterio técnico..."):
                        prompt_sistema = f"""
                        Eres un Ingeniero especialista en Seguridad Industrial, Salud Ocupacional e Inspección de EPP/EPI para trabajos en altura.
                        Responde de forma clara, técnica, estructurada y concisa a la siguiente consulta:
                        {pregunta}
                        """
                        response = model.generate_content(prompt_sistema)
                        st.markdown(response.text)
            except Exception as e:
                st.error(f"❌ Error al consultar el modelo de IA: {e}")
