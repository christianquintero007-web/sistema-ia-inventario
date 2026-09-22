import streamlit as st
import pandas as pd
import google.generativeai as genai
import gspread

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones", 
    page_icon="📦", 
    layout="wide"
)

# Función para conectar y cargar datos de Google Sheets
def cargar_hoja(nombre_pestaña):
    try:
        url_sheet = st.secrets["connections"]["gsheets"]["spreadsheet"]
        gc = gspread.public_url(url_sheet) if hasattr(gspread, 'public_url') else gspread.open_by_url(url_sheet)
        worksheet = gc.worksheet(nombre_pestaña)
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    except Exception as e:
        # Intento secundario directo por URL
        try:
            url_sheet = st.secrets["connections"]["gsheets"]["spreadsheet"]
            gc = gspread.open_by_url(url_sheet)
            worksheet = gc.worksheet(nombre_pestaña)
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except Exception as err:
            st.error(f"Error al conectar con la pestaña '{nombre_pestaña}': {err}")
            return pd.DataFrame(), None

# Título Principal
st.title("📦 Sistema de Inventario e Inspecciones")

# Navegación por pestañas
tab_dashboard, tab_registrar, tab_inspeccion, tab_gestionar, tab_historial, tab_ia = st.tabs([
    "📊 Dashboard", 
    "➕ Registrar Equipo", 
    "📋 Inspección Pre-operacional", 
    "🗑️ Eliminar / Gestionar", 
    "📜 Historial", 
    "🤖 Asistente IA"
])

# 1. DASHBOARD
with tab_dashboard:
    st.header("📊 Estado General de Equipos")
    df_inv, _ = cargar_hoja("Inventario")
    
    total_equipos = len(df_inv) if not df_inv.empty else 0
    conformes = len(df_inv[df_inv["estado"] == "Conforme"]) if total_equipos > 0 and "estado" in df_inv.columns else 0
    no_conformes = len(df_inv[df_inv["estado"] == "No Conforme"]) if total_equipos > 0 and "estado" in df_inv.columns else 0
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Equipos", total_equipos)
    c2.metric("Conformes ✅", conformes)
    c3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Inventario Actual en Google Sheets")
    if not df_inv.empty:
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("No hay datos cargados en la pestaña 'Inventario' de Google Sheets.")

# 2. REGISTRAR EQUIPO
with tab_registrar:
    st.header("➕ Registrar Nuevo Equipo / EPP")
    
    with st.form("form_registro", clear_on_submit=True):
        codigo = st.text_input("Código / N° de Serie del Equipo")
        tipo = st.selectbox("Tipo de Equipo", ["Arnés", "Línea de Vida / Lanyard", "Casco", "Mosquetón / Conector", "Cuerda", "Otro"])
        marca = st.text_input("Marca / Modelo")
        fecha_fab = st.date_input("Fecha de Fabricación")
        
        btn_guardar = st.form_submit_button("Guardar en Google Sheets")
        
        if btn_guardar:
            if codigo and marca:
                df_inv, ws_inv = cargar_hoja("Inventario")
                if ws_inv is not None:
                    if df_inv.empty:
                        ws_inv.append_row(["codigo", "tipo", "marca", "fecha_fab", "estado", "observaciones"])
                    
                    ws_inv.append_row([str(codigo), tipo, marca, str(fecha_fab), "Pendiente de Inspección", "Sin inspeccionar"])
                    st.success(f"Equipo {codigo} registrado con éxito.")
                    st.rerun()
            else:
                st.warning("Completa los campos requeridos (Código y Marca/Modelo).")

# 3. INSPECCIÓN PRE-OPERACIONAL
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional de EPP")
    df_inv, ws_inv = cargar_hoja("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.warning("Primero debes registrar al menos un equipo en el inventario.")
    else:
        lista_codigos = df_inv["codigo"].astype(str).tolist()
        codigo_sel = st.selectbox("Selecciona el Equipo a Inspeccionar", lista_codigos)
        
        st.subheader("Puntos de Verificación Técnica")
        c1 = st.checkbox("Cinta textil sin desgastes, cortes o quemaduras")
        c2 = st.checkbox("Costuras de seguridad íntegras y sin hilos sueltos")
        c3 = st.checkbox("Hebillas y partes metálicas sin deformación ni corrosión")
        
        obs = st.text_area("Observaciones técnicas")
        
        if st.button("Guardar Inspección"):
            resultado = "Conforme" if (c1 and c2 and c3) else "No Conforme"
            
            df_insp, ws_insp = cargar_hoja("Inspecciones")
            if ws_insp is not None:
                if df_insp.empty:
                    ws_insp.append_row(["Fecha", "Codigo", "Resultado", "Observaciones"])
                
                fecha_now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                ws_insp.append_row([fecha_now, str(codigo_sel), resultado, obs])
                
                # Actualizar estado en Inventario
                cell = ws_inv.find(str(codigo_sel))
                if cell:
                    col_estado = df_inv.columns.get_loc("estado") + 1 if "estado" in df_inv.columns else 5
                    col_obs = df_inv.columns.get_loc("observaciones") + 1 if "observaciones" in df_inv.columns else 6
                    ws_inv.update_cell(cell.row, col_estado, resultado)
                    ws_inv.update_cell(cell.row, col_obs, obs)
                
                if resultado == "Conforme":
                    st.success("Inspección guardada: CONFORME ✅")
                else:
                    st.error("Inspección guardada: NO CONFORME ❌.")
                st.rerun()

# 4. ELIMINAR / GESTIONAR EQUIPO
with tab_gestionar:
    st.header("🗑️ Eliminar Equipo del Inventario")
    df_inv, ws_inv = cargar_hoja("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.info("No hay equipos para eliminar.")
    else:
        lista_codigos = df_inv["codigo"].astype(str).tolist()
        codigo_a_eliminar = st.selectbox("Selecciona el Código a Eliminar", lista_codigos)
        
        if st.button("❌ Confirmar y Eliminar Equipo"):
            cell = ws_inv.find(str(codigo_a_eliminar))
            if cell:
                ws_inv.delete_rows(cell.row)
                st.success(f"Equipo {codigo_a_eliminar} eliminado correctamente.")
                st.rerun()

# 5. HISTORIAL
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp, _ = cargar_hoja("Inspecciones")
    if not df_insp.empty:
        st.dataframe(df_insp, use_container_width=True)
    else:
        st.info("Aún no hay inspecciones registradas.")

# 6. ASISTENTE IA
with tab_ia:
    st.header("🤖 Asistente Técnico de Inspección (IA)")
    pregunta = st.text_input("Consulta norma, criterio de rechazo o especificación técnica:")
    
    if st.button("Consultar IA"):
        if pregunta:
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ Falta GEMINI_API_KEY en Secrets.")
                else:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(
                        f"Eres un inspector experto en Seguridad Industrial y EPP. Responde conciso: {pregunta}"
                    )
                    st.write(response.text)
            except Exception as e:
                st.error(f"❌ Error: {e}")
