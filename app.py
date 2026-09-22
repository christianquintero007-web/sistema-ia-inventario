import streamlit as st
import pandas as pd
import google.generativeai as genai

# Configuración de la página
st.set_page_config(page_title="Sistema de Inventario e Inspecciones", page_icon="📦", layout="wide")

# Inicialización segura de la base de datos en sesión
if "inventario" not in st.session_state or not isinstance(st.session_state.inventario, list):
    st.session_state.inventario = []

if "inspecciones" not in st.session_state or not isinstance(st.session_state.inspecciones, list):
    st.session_state.inspecciones = []

# Título Principal
st.title("📦 Sistema de Inventario e Inspecciones")

# Menú Lateral
menu = st.sidebar.selectbox(
    "Navegación", 
    ["Dashboard", "Registrar Equipo", "Inspección Pre-operacional", "Eliminar / Gestionar Equipo", "Historial", "Asistente IA"]
)

# 1. DASHBOARD
if menu == "Dashboard":
    st.header("📊 Estado General de Equipos")
    
    col1, col2, col3 = st.columns(3)
    total_equipos = len(st.session_state.inventario)
    
    conformes = sum(1 for e in st.session_state.inventario if e.get("estado") == "Conforme")
    no_conformes = sum(1 for e in st.session_state.inventario if e.get("estado") == "No Conforme")
        
    col1.metric("Total de Equipos", total_equipos)
    col2.metric("Conformes ✅", conformes)
    col3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Inventario Actual")
    if len(st.session_state.inventario) > 0:
        df = pd.DataFrame(st.session_state.inventario)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay equipos en la base de datos. Ve a 'Registrar Equipo' para agregar el primero.")

# 2. REGISTRAR EQUIPO
elif menu == "Registrar Equipo":
    st.header("➕ Registrar Nuevo Equipo / EPP")
    
    with st.form("form_registro", clear_on_submit=True):
        codigo = st.text_input("Código / N° de Serie del Equipo")
        tipo = st.selectbox("Tipo de Equipo", ["Arnés", "Línea de Vida / Lanyard", "Casco", "Mosquetón / Conector", "Cuerda", "Otro"])
        marca = st.text_input("Marca / Modelo")
        fecha_fab = st.date_input("Fecha de Fabricación")
        
        btn_guardar = st.form_submit_button("Guardar en Inventario")
        
        if btn_guardar:
            if codigo and marca:
                codigos_existentes = [eq["codigo"] for eq in st.session_state.inventario]
                if codigo in codigos_existentes:
                    st.error(f"El equipo con código {codigo} ya está registrado.")
                else:
                    st.session_state.inventario.append({
                        "codigo": codigo,
                        "tipo": tipo,
                        "marca": marca,
                        "fecha_fab": str(fecha_fab),
                        "estado": "Pendiente de Inspección",
                        "observaciones": "Sin inspeccionar"
                    })
                    st.success(f"Equipo {codigo} registrado correctamente.")
            else:
                st.warning("Por favor completa los campos de Código y Marca / Modelo.")

# 3. INSPECCIÓN PRE-OPERACIONAL
elif menu == "Inspección Pre-operacional":
    st.header("📋 Inspección Pre-operacional de EPP")
    
    if len(st.session_state.inventario) == 0:
        st.warning("Primero debes registrar al menos un equipo en el inventario.")
    else:
        lista_codigos = [eq["codigo"] for eq in st.session_state.inventario]
        codigo_sel = st.selectbox("Selecciona el Equipo a Inspeccionar", lista_codigos)
        
        st.subheader("Puntos de Verificación Técnica")
        c1 = st.checkbox("Cinta textil sin desgastes, cortes o quemaduras")
        c2 = st.checkbox("Costuras de seguridad integras y sin hilos sueltos")
        c3 = st.checkbox("Hebillas y partes metálicas sin deformación ni corrosión")
        
        obs = st.text_area("Observaciones técnicas")
        
        if st.button("Guardar Inspección"):
            resultado = "Conforme" if (c1 and c2 and c3) else "No Conforme"
            
            for eq in st.session_state.inventario:
                if eq["codigo"] == codigo_sel:
                    eq["estado"] = resultado
                    eq["observaciones"] = obs
            
            st.session_state.inspecciones.append({
                "Fecha": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "Codigo": codigo_sel,
                "Resultado": resultado,
                "Observaciones": obs
            })
            
            if resultado == "Conforme":
                st.success(f"Inspección guardada: CONFORME ✅")
            else:
                st.error(f"Inspección guardada: NO CONFORME ❌. Se requiere retiro de servicio.")

# 4. ELIMINAR / GESTIONAR EQUIPO
elif menu == "Eliminar / Gestionar Equipo":
    st.header("🗑️ Eliminar Equipo del Inventario")
    
    if len(st.session_state.inventario) == 0:
        st.info("No hay equipos para eliminar.")
    else:
        lista_codigos = [eq["codigo"] for eq in st.session_state.inventario]
        codigo_a_eliminar = st.selectbox("Selecciona el Código del Equipo a Eliminar", lista_codigos)
        
        st.warning(f"⚠️ ¿Estás seguro de que deseas eliminar el equipo **{codigo_a_eliminar}**?")
        
        if st.button("❌ Confirmar y Eliminar Equipo"):
            st.session_state.inventario = [eq for eq in st.session_state.inventario if eq["codigo"] != codigo_a_eliminar]
            st.success(f"El equipo {codigo_a_eliminar} ha sido eliminado correctamente del inventario.")

# 5. HISTORIAL
elif menu == "Historial":
    st.header("📜 Historial de Inspecciones")
    if len(st.session_state.inspecciones) > 0:
        df_insp = pd.DataFrame(st.session_state.inspecciones)
        st.dataframe(df_insp, use_container_width=True)
    else:
        st.info("Aún no se han realizado inspecciones.")

# 6. ASISTENTE IA
elif menu == "Asistente IA":
    st.header("🤖 Asistente Técnico de Inspección (IA)")
    
    pregunta = st.text_input("Consulta norma, criterio de rechazo o especificación técnica:")
    btn_consultar = st.button("Consultar IA")
    
    if btn_consultar:
        if pregunta:
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ No se encontró la etiqueta 'GEMINI_API_KEY' en Secrets de Streamlit.")
                else:
                    api_key = st.secrets["GEMINI_API_KEY"].strip()
                    genai.configure(api_key=api_key)
                    
                    # Lista de modelos compatibles
                    modelos = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro']
                    
                    exito = False
                    for nombre_modelo in modelos:
                        try:
                            model = genai.GenerativeModel(nombre_modelo)
                            response = model.generate_content(
                                f"Eres un inspector experto en Seguridad Industrial y EPP. Responde de forma clara y concisa: {pregunta}"
                            )
                            st.write(response.text)
                            exito = True
                            break
                        except Exception:
                            continue
                    
                    if not exito:
                        st.error("❌ No se encontró un modelo disponible. Revisa tu clave de API.")
            except Exception as e:
                st.error(f"❌ Error al consultar la IA: {e}")
        else:
            st.warning("Escribe una consulta primero.")


