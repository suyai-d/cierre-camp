import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import base64
from io import StringIO
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Cierre de Campaña - Analizador",
    page_icon="🚜",
    layout="wide"
)

# --- LOGOS SUPERIORES ---
col_logo_izq, col_espacio, col_logo_der = st.columns([1, 4, 1])
with col_logo_izq:
    st.image("CSC.png", width=170)
with col_logo_der:
    st.image("JD.png", width=200)

# --- CONFIGURACIÓN DE GITHUB API ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_OWNER = "suyai-d"
REPO_NAME = "reportes-seguridad-db"
BRANCH = "main"


# --- FUNCIONES DE CONTROL DE ACCESO Y LOGS ---
def verificar_usuario(legajo_ingresado):
    """Intenta leer desde GitHub de forma estricta para alertar errores."""
    url_api_usuarios = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/usuarios_permitidos.csv"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    legajo_limpio = legajo_ingresado.strip().upper()

    try:
        response = requests.get(url_api_usuarios, headers=headers, timeout=5)
        if response.status_code == 200:
            file_data = response.json()
            content = base64.b64decode(file_data['content']).decode('utf-8')
            df_usuarios = pd.read_csv(StringIO(content))

            # Limpieza exhaustiva de la columna de usuarios
            df_usuarios['usuarios'] = df_usuarios['usuarios'].astype(str).str.replace(r'\r|\n', '',
                                                                                      regex=True).str.strip().str.upper()
            return legajo_limpio in df_usuarios['usuarios'].values
        else:
            st.error(f"⚠️ Error de lectura en GitHub (Status: {response.status_code}). Revisar Token.")
            return False
    except Exception as e:
        st.error(f"💥 Error de conexión: {str(e)}")
        return False


def registrar_evento_github(usuario, accion, cliente="N/A"):
    """Intenta escribir en GitHub y muestra una alerta en la web si falla."""
    url_registro = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/registro_actividad.csv"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    nueva_fila = {
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": usuario.upper(),
        "accion": accion,
        "cliente": cliente if cliente else "No especificado"
    }

    try:
        res = requests.get(url_registro, headers=headers, timeout=5)
        if res.status_code == 200:
            file_data = res.json()
            sha = file_data['sha']
            content = base64.b64decode(file_data['content']).decode('utf-8')
            df_log = pd.read_csv(StringIO(content))

            # Unimos el nuevo evento
            df_log = pd.concat([df_log, pd.DataFrame([nueva_fila])], ignore_index=True)

            csv_actualizado = df_log.to_csv(index=False)
            content_encoded = base64.b64encode(csv_actualizado.encode('utf-8')).decode('utf-8')

            payload = {
                "message": f"Log: {usuario} - {accion}",
                "content": content_encoded,
                "branch": BRANCH,
                "sha": sha
            }

            requests.put(url_registro, json=payload, headers=headers, timeout=5)
        else:
            st.error(f"❌ No se pudo encontrar el archivo de registros en GitHub. Código: {res.status_code}")
    except Exception as e:
        st.error(f"💥 Error crítico al intentar escribir log: {str(e)}")

def obtener_organizaciones():
    """Trae la lista de organizaciones desde GitHub. Si falla, usa el archivo local."""
    url_api_orgs = f"https://api.github.com/repos/suyai-d/reportes-seguridad-db/contents/Orgs CONCI.csv"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        response = requests.get(url_api_orgs, headers=headers, timeout=3)
        if response.status_code == 200:
            file_data = response.json()
            import base64
            content = base64.b64decode(file_data['content']).decode('utf-8')
            df_orgs = pd.read_csv(StringIO(content))
            return sorted(df_orgs['Organización'].dropna().unique())
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        try:
            # Plan B por si estás en local con red corporativa bloqueada
            df_orgs = pd.read_csv("Orgs CONCI.csv")
            return sorted(df_orgs['Organización'].dropna().unique())
        except Exception:
            return ["No se pudo cargar la lista"]
    return ["No se pudo cargar la lista"]


# --- FLUJO DE AUTENTICACIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""

if not st.session_state.autenticado:
    st.markdown("""<style>.main .block-container { max-width: 450px; padding-top: 5rem; }</style>""",
                unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #367c2b;'>Acceso al Reporte de Cierre de Campaña</h2>",
                unsafe_allow_html=True)
    legajo = st.text_input("Ingresá tu legajo:", placeholder="X000000")

    if st.button("Ingresar al Tablero", use_container_width=True):
        if verificar_usuario(legajo):
            st.session_state.autenticado = True
            st.session_state.usuario = legajo.upper()
            registrar_evento_github(legajo, "Ingreso al Cierre de Cosecha")
            st.rerun()
        else:
            st.error("❌ Usuario no autorizado. Verificá tu legajo.")
    st.stop()  # Detiene la carga de la página aquí si no está autenticado

# --- INTERFAZ DEL TABLERO AUTORIZADO ---
st.markdown(
    """<style>.metric-container { background-color: #ffffff; padding: 15px; border-radius:10px; border:1px solid #e6e9ef; text-align:center; margin-bottom:20px; }</style>""",
    unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.header("Configuración del Informe")

# Razón Social
# 1. Cargamos las razones sociales desde la función híbrida
lista_clientes = obtener_organizaciones()

# 2. Reemplazamos el text_input por el selectbox con opción vacía inicial por prolijidad
razon_social = st.sidebar.selectbox(
    "Razón Social del Cliente",
    options=["Seleccionar Cliente..."] + lista_clientes
)

if razon_social and razon_social != "Seleccionar Cliente...":
    st.info(f"📋 **Cliente:** {razon_social}")

st.sidebar.markdown("---")

# --- SECCIÓN 1: PERFORMANCE ---
st.sidebar.subheader("📊 1. Performance de Maquinaria")
activar_performance = st.sidebar.checkbox("Incluir análisis de Performance", value=True)

df = None
maquinas_seleccionadas = []

if activar_performance:
    uploaded_file = st.sidebar.file_uploader(
        "Cargar datos del Operations Center (Performance)",
        type=["csv", "xlsx"],
        key="perf_file"
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            df.columns = df.columns.str.strip()

            # --- HOMOLOGACIÓN DE NUEVO FORMATO DE PERFORMANCE ---
            mapeo_performance = {
                'Factor de carga prom del motor Trabajo': 'Factor de carga prom del motor En funcionamiento (%)',
                'Combustible consumido Período': 'Combustible consumido Período', # Se mantiene igual
                'Emisiones de combustible Período': 'Emisiones de combustible Período (kg CO2e)',
                'Combustible consumido Ralentí': 'Combustible consumido Ralentí (l)',
                'Combustible consumido Trabajo': 'Combustible consumido Trabajo (l)',
                'Combustible consumido Transporte': 'Combustible consumido Transporte (l)',
                'Horas de trabajo del motor Período': 'Horas de trabajo del motor Período (h)',
                'Horas de trabajo del motor Vida útil': 'Horas de trabajo del motor Vida útil (h)',
                'Tiempo en soja': 'Tiempo en soja (h)',
                'Tiempo en maíz': 'Tiempo en maíz (h)',
                'Active Terrain Adjustment™ Activado': 'Active Terrain Adjustment™ Activado (%)',
                'ActiveYield™ Activado': 'ActiveYield™ Activado (%)',
                'Harvest Smart Activado': 'Harvest Smart Activado (%)',
                'Auto Maintain Activado': 'Auto Maintain Activado (%)',
                'AutoTrac™ Activo': 'AutoTrac™ Activo (%)',
                'AutoPath™ Activo': 'AutoPath™ Activo (%)',
                'John Deere Machine Sync Vehículo guía activo': 'John Deere Machine Sync Vehículo guía activo (%)',
                'Automatización de maniobras AutoTrac™ Activo': 'Automatización de maniobras AutoTrac™ Activo (%)',
                'Automatización de la velocidad de avance Activo': 'Automatización de la velocidad de avance Activo (%)',
                'Automatización de ajustes de cosecha Activo': 'Automatización de los ajustes de cosecha Activo (%)'
            }
            
            # Nota: El archivo exportado trae un espacio al final en 'Tiempo en soja ' y 'Tiempo en maíz ', 
            # limpiamos los espacios extras de las columnas antes del renombre definitivo.
            df.columns = df.columns.str.strip()
            df = df.rename(columns=mapeo_performance)

            if 'Máquina' in df.columns:
                df = df.dropna(subset=['Máquina'])
                opciones_maquinas = df['Máquina'].unique().tolist()

                maquinas_seleccionadas = st.sidebar.multiselect(
                    "Seleccionar Máquinas para el informe",
                    options=opciones_maquinas,
                    default=opciones_maquinas
                )
            else:
                st.sidebar.error("No se encontró la columna 'Máquina' en el archivo de performance.")
        except Exception as e:
            st.sidebar.error(f"Error al cargar archivo de performance: {e}")
    else:
        st.sidebar.info("Subí el archivo de Performance para comenzar.")

st.sidebar.markdown("---")

# --- SECCIÓN 2: CALIDAD DE REGISTRO ---
st.sidebar.subheader("📋 2. Calidad de Registro")
agregar_calidad = st.sidebar.checkbox("Agregar análisis de Calidad de Registro", value=False)

calidad_datos = {}
if agregar_calidad:
    st.sidebar.caption("Completar totales vs. datos correctos:")

    st.sidebar.markdown("**Asignación de Variedad**")
    v_totales = st.sidebar.number_input("Total de Mapas de Cosecha:", min_value=1, value=10, key="v_tot")
    # Protegemos el value para que no supere a v_totales
    v_correctos = st.sidebar.number_input("Mapas con Variedad Cargada:", min_value=0, max_value=v_totales,
                                          value=min(8, v_totales), key="v_corr")

    st.sidebar.markdown("**Mapas Cargados Correctamente**")
    m_totales = st.sidebar.number_input("Total de Mapas del Período:", min_value=1, value=12, key="m_tot")
    # Protegemos el value para que no supere a m_totales (evita el error que te apareció)
    m_correctos = st.sidebar.number_input("Mapas sin Errores/Superposiciones:", min_value=0, max_value=m_totales,
                                          value=min(11, m_totales), key="m_corr")

    st.sidebar.markdown("**Nombramiento de Campos**")
    c_totales = st.sidebar.number_input("Total de Campos Registrados:", min_value=1, value=15, key="c_tot")
    # Protegemos el value para que no supere a c_totales
    c_correctos = st.sidebar.number_input("Campos con Nombre Correcto (sin duplicados):", min_value=0,
                                          max_value=c_totales, value=min(12, c_totales), key="c_corr")

    st.sidebar.markdown("**Límites de Campos**")
    l_totales = st.sidebar.number_input("Total de Campos en Org:", min_value=1, value=15, key="l_tot")
    # Protegemos el value para que no supere a l_totales
    l_correctos = st.sidebar.number_input("Campos con Límites Correctos/Activos:", min_value=0, max_value=l_totales,
                                          value=min(9, l_totales), key="l_corr")

    calidad_datos = {
        'Asignación de Variedad': (v_correctos / v_totales) * 100,
        'Mapas sin Errores': (m_correctos / m_totales) * 100,
        'Nombramiento de Campos': (c_correctos / c_totales) * 100,
        'Límites Definitivos': (l_correctos / l_totales) * 100
    }

st.sidebar.markdown("---")

# --- SECCIÓN 3: DATOS AGRONÓMICOS ---
st.sidebar.subheader("🌾 3. Datos Agronómicos")
agregar_agronómico = st.sidebar.checkbox("Agregar análisis de datos agronómicos", value=False)

hectareas_filtro = 2.0
df_agro = None

if agregar_agronómico:
    uploaded_agro_file = st.sidebar.file_uploader(
        "Cargar datos de Cosecha (.xlsx/.csv)",
        type=["csv", "xlsx"],
        key="agro_file"
    )

    hectareas_filtro = st.sidebar.number_input(
        "Filtrar lotes con superficie menor a (ha):",
        min_value=0.0, max_value=100.0, value=2.0, step=0.5
    )

    if uploaded_agro_file is not None:
        try:
            if uploaded_agro_file.name.endswith('.csv'):
                df_agro = pd.read_csv(uploaded_agro_file)
            else:
                df_agro = pd.read_excel(uploaded_agro_file)

            df_agro.columns = df_agro.columns.str.strip()

            # --- HOMOLOGACIÓN INTELIGENTE DE COLUMNAS ---
            mapeo_columnas = {
                'Velocidad': 'Velocidad de trabajo',
                'Índice de combustible (área)': 'Consumo de combustible por unidad de superficie',
                'Rendimiento (seco)': 'Productividad_th'
            }
            df_agro = df_agro.rename(columns=mapeo_columnas)

            # Limpieza de filas de control
            df_agro = df_agro[(df_agro['Nombre de máquina'] != 'Unidad') & (df_agro['Nombre de máquina'] != '---')]
            df_agro = df_agro.dropna(subset=['Nombre de máquina'])

            # Forzamos conversión numérica de las columnas clave
            columnas_numericas = [
                'Superficie cosechada', 'Rendimiento en seco', 'Rendimiento seco total',
                'Velocidad de trabajo', 'Consumo de combustible por unidad de superficie',
                'Productividad_th', 'Productividad'
            ]
            for col in columnas_numericas:
                if col in df_agro.columns:
                    df_agro[col] = pd.to_numeric(df_agro[col], errors='coerce')

            # Parsear la columna de fecha para la serie histórica
            if 'Primera cosecha' in df_agro.columns:
                df_agro['Fecha_Formateada'] = pd.to_datetime(df_agro['Primera cosecha'], errors='coerce')

        except Exception as e:
            st.sidebar.error(f"Error al cargar el archivo agronómico: {e}")

# --- CUERPO DEL INFORME ---
# Portada de inicio full-width para la descarga en PDF
st.image("portada.jpg", use_container_width=True)

st.title("Cierre de Campaña")

if df is not None and len(df) > 0 and activar_performance:
    fecha_inicio_raw = df['Fecha de inicio'].dropna().iloc[0] if 'Fecha de inicio' in df.columns else "N/D"
    fecha_fin_raw = df['Fecha de terminación'].dropna().iloc[0] if 'Fecha de terminación' in df.columns else "N/D"
    fecha_inicio = str(fecha_inicio_raw).split()[0] if fecha_inicio_raw != "N/D" else "N/D"
    fecha_fin = str(fecha_fin_raw).split()[0] if fecha_fin_raw != "N/D" else "N/D"
else:
    fecha_inicio, fecha_fin = "N/D", "N/D"

col_header1, col_header2 = st.columns(2)
with col_header1:
    if razon_social:
        st.subheader(f"Cliente: {razon_social}")
    else:
        st.subheader("Cliente: _Razón Social no especificada_")
with col_header2:
    st.markdown(
        f"<p style='text-align: right; font-size: 1.2rem; font-weight: bold; color: #4caf50;'>📅 Período: {fecha_inicio} al {fecha_fin}</p>",
        unsafe_allow_html=True)

st.markdown("---")

# --- DISPLAY SECCIÓN 1: PERFORMANCE ---
if activar_performance:
    st.header("1. Performance de Maquinaria")

    if df is not None and maquinas_seleccionadas:
        df_filtrado = df[df['Máquina'].isin(maquinas_seleccionadas)]

        st.markdown("### Equipos en Análisis")
        cols = st.columns(min(len(df_filtrado), 4))
        for idx, (_, row) in enumerate(df_filtrado.iterrows()):
            with cols[idx % min(len(df_filtrado), 4)]:
                sn = row.get('Número de serie de la máquina', 'N/D')
                modelo = row.get('Modelo', 'N/D')
                st.info(f"**{row['Máquina']}**\n\n*Modelo:* {modelo}\n\n*S/N:* `{sn}`")

        st.markdown("---")
        st.markdown("### Análisis Individual por Equipo")

        for maquina in maquinas_seleccionadas:
            row_m = df_filtrado[df_filtrado['Máquina'] == maquina].iloc[0]
            modelo_maquina = str(row_m.get('Modelo', '')).upper().strip()

            with st.expander(f"🚜 Análisis Detallado - {maquina} ({modelo_maquina})", expanded=True):
                kpi_col1, kpi_col2, kpi_col3 = st.columns(3)

                with kpi_col1:
                    horas_periodo = row_m.get('Horas de trabajo del motor Período (h)', 0)
                    horas_vida = row_m.get('Horas de trabajo del motor Vida útil (h)', 0)
                    horas_periodo = 0.0 if pd.isna(horas_periodo) else horas_periodo
                    horas_vida = 0.0 if pd.isna(horas_vida) else horas_vida
                    st.metric(label="Horas de Motor (En Período)", value=f"{horas_periodo:,.1f} h",
                              delta=f"Total Vida Útil: {horas_vida:,.1f} h", delta_color="normal")

                with kpi_col2:
                    co2 = row_m.get('Emisiones de combustible Período (kg CO2e)', 0)
                    co2 = 0 if pd.isna(co2) else co2
                    st.metric(label="Emisiones de CO₂", value=f"{co2:,.0f} kg CO2e")

                with kpi_col3:
                    t_soja = row_m.get('Tiempo en soja (h)', 0)
                    t_maiz = row_m.get('Tiempo en maíz (h)', 0)
                    t_soja = 0 if pd.isna(t_soja) else t_soja
                    t_maiz = 0 if pd.isna(t_maiz) else t_maiz

                    st.markdown("**Distribución de Tiempo por Cultivo**")
                    if t_soja > 0 or t_maiz > 0:
                        fig_cultivo = go.Figure(go.Bar(
                            x=[t_soja, t_maiz], y=['Soja ', 'Maíz '], orientation='h',
                            marker_color=['#9ccc65', '#ffca28'], text=[f"{t_soja:,.1f} h", f"{t_maiz:,.1f} h"],
                            textposition='inside'
                        ))
                        fig_cultivo.update_layout(height=140, margin=dict(l=10, r=10, t=10, b=10),
                                                  xaxis=dict(showgrid=False, visible=False),
                                                  yaxis=dict(autorange="reversed"))
                        st.plotly_chart(fig_cultivo, use_container_width=True, key=f"cultivo_{maquina}")
                    else:
                        st.caption("No se registraron horas específicas de trilla.")

                st.markdown("#### Eficiencia y Estado del Motor")
                graf_comb, term_motor = st.columns([2, 1])

                with graf_comb:
                    st.markdown("**Distribución de Combustible Consumido (Litros / %)**")
                    c_trabajo = row_m.get('Combustible consumido Trabajo (l)', 0)
                    c_ralenti = row_m.get('Combustible consumido Ralentí (l)', 0)
                    c_transp = row_m.get('Combustible consumido Transporte (l)', 0)

                    c_trabajo = 0 if pd.isna(c_trabajo) else c_trabajo
                    c_ralenti = 0 if pd.isna(c_ralenti) else c_ralenti
                    c_transp = 0 if pd.isna(c_transp) else c_transp
                    c_total = c_trabajo + c_ralenti + c_transp

                    if c_total > 0:
                        p_trabajo = (c_trabajo / c_total) * 100
                        p_ralenti = (c_ralenti / c_total) * 100
                        p_transp = (c_transp / c_total) * 100

                        # Armamos los nombres con los datos integrados para la leyenda
                        label_trabajo = f"Trabajo: {c_trabajo:,.0f} L ({p_trabajo:.1f}%)" if c_trabajo > 0 else "Trabajo"
                        label_ralenti = f"Ralentí: {c_ralenti:,.0f} L ({p_ralenti:.1f}%)" if c_ralenti > 0 else "Ralentí"
                        label_transp = f"Transporte: {c_transp:,.0f} L ({p_transp:.1f}%)" if c_transp > 0 else "Transporte"

                        fig_comb = go.Figure()
                        fig_comb.add_trace(go.Bar(
                            name=label_trabajo, y=['Combustible'], x=[c_trabajo], orientation='h',
                            marker_color='#2ca02c'
                        ))
                        fig_comb.add_trace(go.Bar(
                            name=label_ralenti, y=['Combustible'], x=[c_ralenti], orientation='h',
                            marker_color='#ff7f0e'
                        ))
                        fig_comb.add_trace(go.Bar(
                            name=label_transp, y=['Combustible'], x=[c_transp], orientation='h', marker_color='#7f7f7f'
                        ))
                        fig_comb.update_layout(barmode='stack', height=180, margin=dict(l=10, r=10, t=10, b=10),
                                               legend=dict(orientation="h", y=1.3))
                        st.plotly_chart(fig_comb, use_container_width=True, key=f"comb_{maquina}")
                    else:
                        st.caption("Sin datos de combustible.")

                with term_motor:
                    st.markdown("**Factor de Carga Promedio del Motor**")
                    factor_carga = row_m.get('Factor de carga prom del motor En funcionamiento (%)', 0)
                    if not pd.isna(factor_carga) and factor_carga > 0:
                        if factor_carga <= 1.0: factor_carga *= 100

                        es_nueva_s7 = "S7 " in modelo_maquina
                        if es_nueva_s7:
                            color_term = "#28a745"
                            status_text = "✅ Carga Eficiente"
                            steps_config = [{'range': [0, 100], 'color': "#c8e6c9"}]
                        else:
                            if factor_carga >= 90:
                                color_term = "#dc3545"
                                status_text = "⚠️ CARGA CRÍTICA (>90%)"
                            elif factor_carga >= 85:
                                color_term = "#ffc107"
                                status_text = "⚠️ Carga Moderada (85-90%)"
                            else:
                                color_term = "#28a745"
                                status_text = "✅ Carga Normal (<85%)"
                            steps_config = [{'range': [0, 85], 'color': "#e0e0e0"},
                                            {'range': [85, 90], 'color': "#ffe082"},
                                            {'range': [90, 100], 'color': "#ffcdd2"}]

                        fig_gauge = go.Figure(go.Indicator(
                            mode="gauge+number", value=factor_carga, number={'suffix': "%"},
                            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': color_term}, 'steps': steps_config}
                        ))
                        fig_gauge.update_layout(height=150, margin=dict(l=20, r=20, t=10, b=10))
                        st.plotly_chart(fig_gauge, use_container_width=True, key=f"gauge_{maquina}")
                        st.markdown(
                            f"<p style='text-align: center; font-weight: bold; color: {color_term};'>{status_text}</p>",
                            unsafe_allow_html=True)
                    else:
                        st.caption("Sin datos de factor de carga.")

        st.markdown("---")
        st.header("2. Eficiencia de Operación y Tecnologías")
        st.markdown("### Comparativa de Tecnología de Guiado por Equipo")


        def normalizar_porcentaje(val):
            if pd.isna(val): return 0.0
            return val * 100 if val <= 1.0 else val


        datos_guiado = []
        datos_cosechadora = []

        for _, row in df_filtrado.iterrows():
            m_name = row['Máquina']
            at = normalizar_porcentaje(row.get('AutoTrac™ Activo (%)', 0))
            ap = normalizar_porcentaje(row.get('AutoPath™ Activo (%)', 0))
            am = normalizar_porcentaje(row.get('Automatización de maniobras AutoTrac™ Activo (%)', 0))
            ms = normalizar_porcentaje(row.get('John Deere Machine Sync Vehículo guía activo (%)', 0))

            datos_guiado.append({'Máquina': m_name, 'Tecnología': 'AutoTrac™', 'Porcentaje': at})
            datos_guiado.append({'Máquina': m_name, 'Tecnología': 'AutoPath™', 'Porcentaje': ap})
            datos_guiado.append({'Máquina': m_name, 'Tecnología': 'Automatización Maniobras (iTEC)', 'Porcentaje': am})
            datos_guiado.append({'Máquina': m_name, 'Tecnología': 'Machine Sync (Guía)', 'Porcentaje': ms})

            ata = normalizar_porcentaje(row.get('Active Terrain Adjustment™ Activado (%)', 0))
            ay = normalizar_porcentaje(row.get('ActiveYield™ Activado (%)', 0))
            hs = normalizar_porcentaje(row.get('Harvest Smart Activado (%)', 0))
            amaintain = normalizar_porcentaje(row.get('Auto Maintain Activado (%)', 0))
            ajustes_c = normalizar_porcentaje(row.get('Automatización de los ajustes de cosecha Activo (%)', 0))
            tech_ajustes = ajustes_c if ajustes_c > 0 else amaintain
            vel_avance = normalizar_porcentaje(row.get('Automatización de la velocidad de avance Activo (%)', 0))

            datos_cosechadora.append({'Máquina': m_name, 'Tecnología': 'Active Terrain Adjustment™', 'Porcentaje': ata})
            datos_cosechadora.append({'Máquina': m_name, 'Tecnología': 'ActiveYield™', 'Porcentaje': ay})
            datos_cosechadora.append({'Máquina': m_name, 'Tecnología': 'Harvest Smart', 'Porcentaje': hs})
            datos_cosechadora.append(
                {'Máquina': m_name, 'Tecnología': 'Ajustes de Cosecha / Auto Maintain', 'Porcentaje': tech_ajustes})
            datos_cosechadora.append(
                {'Máquina': m_name, 'Tecnología': 'Automatización Vel. Avance', 'Porcentaje': vel_avance})

        df_guiado_plot = pd.DataFrame(datos_guiado)
        df_cosechadora_plot = pd.DataFrame(datos_cosechadora)

        # --- Gráfico 1: Comparativa de Tecnología de Guiado ---
        fig_guiado = px.bar(df_guiado_plot, x='Máquina', y='Porcentaje', color='Tecnología', barmode='group',
                            text=df_guiado_plot['Porcentaje'].apply(lambda x: f"{x:.1f}%" if x > 0 else ""),
                            color_discrete_sequence=['#367c2b', '#ffde00', '#204d19', '#9ccc65'])

        # Línea de objetivo al 80%
        fig_guiado.add_hline(y=60, line_dash="dash", line_color="#d32f2f",
                             annotation_text="Objetivo: 60%", annotation_position="top left")

        fig_guiado.update_layout(yaxis=dict(range=[0, 115]), height=400,
                                 legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_guiado, use_container_width=True)

        st.markdown("---")
        st.markdown("### Comparativa de Tecnología de Cosecha por Equipo")

        # --- Gráfico 2: Comparativa de Tecnología de Cosecha ---
        fig_cosechadora = px.bar(df_cosechadora_plot, x='Máquina', y='Porcentaje', color='Tecnología', barmode='group',
                                 text=df_cosechadora_plot['Porcentaje'].apply(lambda x: f"{x:.1f}%" if x > 0 else ""),
                                 color_discrete_sequence=['#1b5e20', '#2e7d32', '#4caf50', '#81c784', '#a5d6a7'])

        # Línea de objetivo al 60%
        fig_cosechadora.add_hline(y=80, line_dash="dash", line_color="#d32f2f",
                                  annotation_text="Objetivo: 80%", annotation_position="top left")

        fig_cosechadora.update_layout(yaxis=dict(range=[0, 115]), height=400,
                                      legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig_cosechadora, use_container_width=True)

# --- DISPLAY SECCIÓN 2: CALIDAD DE REGISTRO ---
if agregar_calidad:
    st.markdown("---")
    st.header("3. Calidad de Registro y Limpieza de Datos")

    calidad_general = sum(calidad_datos.values()) / len(calidad_datos)
    if calidad_general >= 85:
        color_general = "#28a745"
    elif calidad_general >= 70:
        color_general = "#ffc107"
    else:
        color_general = "#dc3545"

    col_cal1, col_cal2 = st.columns([1, 2])
    with col_cal1:
        st.markdown("### Calidad Digital General")
        st.markdown(f"""
        <div style='background-color: #f8f9fa; border-left: 8px solid {color_general}; padding: 20px; border-radius: 5px; text-align: center;'>
            <p style='margin: 0; font-size: 1.1rem; font-weight: bold; color: #6c757d;'>Score General de la Organización</p>
            <h1 style='margin: 10px 0; color: {color_general}; font-size: 3.5rem;'>{calidad_general:.1f}%</h1>
            <p style='margin: 0; font-size: 0.9rem; font-style: italic; color: #495057;'>Establece el nivel de confianza de los reportes digitales del Operations Center.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_cal2:
        st.markdown("### Desglose de Cumplimiento")
        df_calidad = pd.DataFrame({'Indicador': list(calidad_datos.keys()), 'Porcentaje': list(calidad_datos.values())})
        fig_calidad = px.bar(df_calidad, x='Porcentaje', y='Indicador', orientation='h',
                             text=df_calidad['Porcentaje'].apply(lambda x: f"{x:.1f}%"),
                             labels={'Porcentaje': '% de Avance', 'Indicador': 'Área de Control'}, color='Porcentaje',
                             color_continuous_scale=['#ffcdd2', '#ffe082', '#a5d6a7', '#2e7d32'])
        fig_calidad.update_traces(textposition='inside', textfont_size=12, textfont_weight='bold')
        fig_calidad.update_layout(xaxis=dict(range=[0, 105]), height=220, coloraxis_showscale=False,
                                  margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_calidad, use_container_width=True)

# --- DISPLAY SECCIÓN 3: DATOS AGRONÓMICOS ---
if agregar_agronómico:
    st.markdown("---")
    num_seccion = "4" if agregar_calidad else "3"
    st.header(f"{num_seccion}. Análisis de Datos Agronómicos")

    if df_agro is not None and len(df_agro) > 0:
        df_base_filtrada = df_agro[df_agro['Superficie cosechada'] >= hectareas_filtro].copy()

        if len(df_base_filtrada) == 0:
            st.warning(f"No hay registros con una superficie mayor o igual a {hectareas_filtro} ha.")
        else:
            st.caption(
                f"ℹ️ Mostrando datos agrupados de lotes con superficies iguales o mayores a **{hectareas_filtro} ha**.")
            cultivos_disponibles = df_base_filtrada['Tipo de cultivo'].dropna().unique().tolist()

            for cultivo in cultivos_disponibles:
                df_c = df_base_filtrada[df_base_filtrada['Tipo de cultivo'] == cultivo].copy()
                st.markdown(f"## 🌾 Cultivo Analizado: {str(cultivo).upper()}")

                # --- KPIs GLOBALES DEL CULTIVO ---
                sup_total_c = df_c['Superficie cosechada'].sum()
                df_rinde_valido_c = df_c[df_c['Rendimiento en seco'] > 0]
                rinde_prom_c = df_rinde_valido_c['Rendimiento en seco'].mean() if len(df_rinde_valido_c) > 0 else 0

                if 'Rendimiento seco total' in df_c.columns:
                    ton_totales_c = df_c['Rendimiento seco total'].sum()
                else:
                    ton_totales_c = sup_total_c * rinde_prom_c

                kpi_g1, kpi_g2, kpi_g3 = st.columns(3)
                with kpi_g1:
                    st.metric(label="Superficie Total Cosechada", value=f"{sup_total_c:,.1f} ha")
                with kpi_g2:
                    st.metric(label="Rendimiento Promedio", value=f"{rinde_prom_c:.2f} t/ha")
                with kpi_g3:
                    st.metric(label="Producción Total", value=f"{ton_totales_c:,.1f} t")

                # --- 1. DATOS DE MAQUINARIA (SUPERFICIE Y VELOCIDAD) ---
                st.markdown("#### 🚜 Performance de Equipos en el Cultivo")
                col_m1, col_m2 = st.columns(2)

                with col_m1:
                    df_sup_maq = df_c.groupby('Nombre de máquina')['Superficie cosechada'].sum().reset_index()
                    fig_sup_maq = px.bar(
                        df_sup_maq, x='Nombre de máquina', y='Superficie cosechada',
                        text=df_sup_maq['Superficie cosechada'].apply(lambda x: f"{x:,.1f} ha"),
                        labels={'Superficie cosechada': 'Superficie (ha)', 'Nombre de máquina': 'Equipo'},
                        title="Superficie por Equipo", color_discrete_sequence=['#4caf50']
                    )
                    fig_sup_maq.update_traces(textposition='outside')
                    fig_sup_maq.update_layout(yaxis=dict(range=[0, df_sup_maq['Superficie cosechada'].max() * 1.3]),
                                              height=300, margin=dict(t=40, b=10, l=10, r=10))
                    st.plotly_chart(fig_sup_maq, use_container_width=True, key=f"sup_maq_{cultivo}")

                with col_m2:
                    df_vel_valida = df_c[df_c['Velocidad de trabajo'] > 0]
                    df_vel_maq = df_vel_valida.groupby('Nombre de máquina')['Velocidad de trabajo'].mean().reset_index()
                    vel_general = df_vel_valida['Velocidad de trabajo'].mean() if len(df_vel_valida) > 0 else 0

                    fig_vel = px.bar(
                        df_vel_maq, x='Nombre de máquina', y='Velocidad de trabajo',
                        text=df_vel_maq['Velocidad de trabajo'].apply(lambda x: f"{x:.1f} km/h"),
                        labels={'Velocidad de trabajo': 'Velocidad (km/h)', 'Nombre de máquina': 'Equipo'},
                        title="Velocidad Promedio de Cosecha", color_discrete_sequence=['#367c2b']
                    )
                    fig_vel.add_hline(y=vel_general, line_dash="dash", line_color="#d32f2f")
                    fig_vel.update_traces(textposition='outside')
                    fig_vel.update_layout(yaxis=dict(range=[0, max(
                        df_vel_maq['Velocidad de trabajo'].max() if len(df_vel_maq) > 0 else 5, vel_general) * 1.3]),
                                          height=300, margin=dict(t=40, b=10, l=10, r=10))
                    st.plotly_chart(fig_vel, use_container_width=True, key=f"vel_maq_{cultivo}")

                # --- NUEVO: EFICIENCIA (L/ha) VS PRODUCTIVIDAD (tn/h) ---
                st.markdown("#### 📊 Capacidad y Eficiencia de los Equipos")
                col_c1, col_c2 = st.columns(2)

                with col_c1:
                    # Eficiencia del archivo de Cosecha (L/ha)
                    campo_comb = 'Consumo de combustible por unidad de superficie'
                    if campo_comb in df_c.columns:
                        df_comb_valido = df_c[df_c[campo_comb] > 0]
                        df_litros_ha = df_comb_valido.groupby('Nombre de máquina')[campo_comb].mean().reset_index()

                        fig_lha = px.bar(
                            df_litros_ha, x='Nombre de máquina', y=campo_comb,
                            text=df_litros_ha[campo_comb].apply(lambda x: f"{x:.1f} L/ha"),
                            labels={campo_comb: 'Consumo (L/ha)', 'Nombre de máquina': 'Equipo'},
                            title="Eficiencia de Combustible", color_discrete_sequence=['#2e7d32']
                        )
                        fig_lha.update_traces(textposition='outside')
                        fig_lha.update_layout(yaxis=dict(
                            range=[0, (df_litros_ha[campo_comb].max() if len(df_litros_ha) > 0 else 10) * 1.3]),
                            height=300, margin=dict(t=40, b=10, l=10, r=10))
                        st.plotly_chart(fig_lha, use_container_width=True, key=f"lha_{cultivo}")
                    else:
                        st.warning("Columna de consumo L/ha no disponible.")

                with col_c2:
                    # REEMPLAZO: CANTIDAD DE TONELADAS POR HORA QUE PROCESÓ CADA MÁQUINA
                    col_prod = 'Productividad_th' if 'Productividad_th' in df_c.columns else 'Productividad'

                    if col_prod in df_c.columns:
                        df_prod_valida = df_c[df_c[col_prod] > 0]
                        df_prod_maq = df_prod_valida.groupby('Nombre de máquina')[col_prod].mean().reset_index()
                        prod_gral = df_prod_valida[col_prod].mean() if len(df_prod_valida) > 0 else 0

                        fig_th = px.bar(
                            df_prod_maq, x='Nombre de máquina', y=col_prod,
                            text=df_prod_maq[col_prod].apply(lambda x: f"{x:.1f} t/h"),
                            labels={col_prod: 'Productividad (t/h)', 'Nombre de máquina': 'Equipo'},
                            title="Productividad Horaria de Trilla", color_discrete_sequence=['#ffde00']
                        )
                        if prod_gral > 0:
                            fig_th.add_hline(y=prod_gral, line_dash="dash", line_color="#1b5e20")
                        fig_th.update_traces(textposition='outside')
                        fig_th.update_layout(yaxis=dict(range=[0, max(
                            df_prod_maq[col_prod].max() if len(df_prod_maq) > 0 else 10, prod_gral) * 1.3]), height=300,
                                             margin=dict(t=40, b=10, l=10, r=10))
                        st.plotly_chart(fig_th, use_container_width=True, key=f"th_{cultivo}")
                    else:
                        st.warning("Columna de Productividad (t/h) no encontrada en el archivo.")

                # --- 2. SERIE HISTÓRICA DE COSECHA ---
                st.markdown("#### 📈 Evolución y Ritmo de Cosecha")
                if 'Fecha_Formateada' in df_c.columns and df_c['Fecha_Formateada'].notna().any():
                    df_dia = df_c.groupby(df_c['Fecha_Formateada'].dt.date)['Superficie cosechada'].sum().reset_index()
                    df_dia.columns = ['Fecha_Dia', 'Superficie cosechada']
                    df_dia = df_dia.sort_values('Fecha_Dia')
                    df_dia['Acumulado'] = df_dia['Superficie cosechada'].cumsum()

                    fig_timeline = go.Figure()
                    fig_timeline.add_trace(go.Bar(
                        x=df_dia['Fecha_Dia'], y=df_dia['Superficie cosechada'],
                        name='Hectáreas Diarias', marker_color='#a5d6a7', yaxis='y1'
                    ))
                    fig_timeline.add_trace(go.Scatter(
                        x=df_dia['Fecha_Dia'], y=df_dia['Acumulado'],
                        name='Hectáreas Acumuladas', line=dict(color='#1b5e20', width=3), mode='lines+markers',
                        yaxis='y2'
                    ))
                    fig_timeline.update_layout(
                        height=350, legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center"),
                        xaxis=dict(type='category'),
                        yaxis=dict(title="Superficie Diaria (ha)", side="left", showgrid=True),
                        yaxis2=dict(title="Superficie Acumulada (ha)", side="right", overlaying="y", showgrid=False),
                        margin=dict(t=30, b=20)
                    )
                    st.plotly_chart(fig_timeline, use_container_width=True, key=f"timeline_{cultivo}")
                else:
                    st.info("Sin columna de fecha válida para la línea de tiempo.")

                # --- 3. UN SOLO GRÁFICO DE TORTA DE VARIEDADES ---
                st.markdown("#### 📊 Distribución de Superficie por Variedad / Híbrido")
                df_pie_var = df_c.groupby('Variedades')['Superficie cosechada'].sum().reset_index()

                fig_pie_v = px.pie(
                    df_pie_var, values='Superficie cosechada', names='Variedades',
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_pie_v.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie_v.update_layout(height=350, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_pie_v, use_container_width=True, key=f"pie_var_{cultivo}")

                # --- 4. BOXPLOT DE RENDIMIENTO POR VARIEDAD ---
                st.markdown("#### 📊 Rendimiento por Variedad (Análisis de Dispersión)")
                if len(df_rinde_valido_c) > 0:
                    fig_box = px.box(
                        df_rinde_valido_c, x='Variedades', y='Rendimiento en seco',
                        labels={'Rendimiento en seco': 'Rendimiento (t/ha)', 'Variedades': 'Variedad / Híbrido'},
                        color_discrete_sequence=['#4caf50']
                    )
                    fig_box.update_layout(height=380, boxmode='group', margin=dict(t=20, b=20))
                    st.plotly_chart(fig_box, use_container_width=True, key=f"box_{cultivo}")
                else:
                    st.info("Sin datos de rendimiento para el Boxplot.")

                st.markdown("---")  # Separador estético entre cultivos

# --- SECCIÓN FINALES Y ACCIONES DE EXPORTACIÓN ---

# Botón para simular la generación de PDF y disparar el log automático
if st.button("Generar Reporte PDF", use_container_width=True):
    # Aquí irá tu lógica para renderizar/descargar el PDF, pero el registro en GitHub ya se ejecuta de inmediato:
    cliente_informe = razon_social.strip() if razon_social else "No especificado"
    registrar_evento_github(st.session_state.usuario, "Exportó Reporte Cierre Cosecha a PDF", cliente=cliente_informe)
    st.success(f"🎉 ¡Reporte registrado con éxito para {cliente_informe}!")
