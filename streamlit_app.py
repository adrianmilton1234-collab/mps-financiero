import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MPS Enterprise V3.2", page_icon="🏢", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #ffffff; border-radius: 4px; border: 1px solid #e0e0e0;
    }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A; color: white; border: none; }
    .metric-card { 
        background-color: white; padding: 20px; border-radius: 10px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #1E3A8A; 
        text-align: center;
    }
    .offer-card {
        background-color: #f0fdf4; border: 2px solid #10B981; padding: 15px; border-radius: 10px;
        text-align: center; margin-bottom: 10px; height: 100%;
    }
    .offer-title { color: #047857; font-weight: bold; font-size: 18px; margin-bottom: 10px; text-decoration: underline;}
    .offer-price { font-size: 26px; font-weight: bold; color: #1E3A8A; margin: 10px 0; }
    .offer-detail { font-size: 14px; color: #475569; margin-top: 5px; }
    .excess-price { font-size: 14px; color: #dc2626; font-weight: bold; background-color: #fee2e2; padding: 5px; border-radius: 5px; margin-top: 10px;}
    </style>
""", unsafe_allow_html=True)

# --- BACKEND (SQLITE) ---
def init_db():
    conn = sqlite3.connect('mps_enterprise.db')
    c = conn.cursor()
    # Usamos IF NOT EXISTS para no borrar datos si el archivo ya existe (en local)
    c.execute('''CREATE TABLE IF NOT EXISTS equipos
                 (id INTEGER PRIMARY KEY, marca TEXT, modelo TEXT, tipo TEXT, 
                  velocidad INTEGER, costo_adq REAL, residual REAL, vida_util INTEGER, mantenimiento REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS consumibles
                 (id INTEGER PRIMARY KEY, equipo_id INTEGER, tipo TEXT, costo REAL, rendimiento INTEGER,
                  FOREIGN KEY(equipo_id) REFERENCES equipos(id))''')
    conn.commit()
    return conn

conn = init_db()

# --- LÓGICA FINANCIERA ---
def calcular_costos_equipo(equipo_id, volumen, incluir_papel, costo_papel):
    # 1. Costo Consumibles (Variable)
    df_cons = pd.read_sql_query(f"SELECT * FROM consumibles WHERE equipo_id = {equipo_id}", conn)
    cpp_cons = 0
    for _, row in df_cons.iterrows():
        if row['rendimiento'] > 0:
            cpp_cons += row['costo'] / row['rendimiento']
    
    if incluir_papel:
        cpp_cons += costo_papel / 500

    costo_variable_unitario = cpp_cons
    costo_variable_total = cpp_cons * volumen

    # 2. Costo Fijo (Amortización + Mantenimiento)
    equipo = pd.read_sql_query(f"SELECT * FROM equipos WHERE id = {equipo_id}", conn).iloc[0]
    amortizacion = (equipo['costo_adq'] - equipo['residual']) / equipo['vida_util']
    costo_fijo_total = amortizacion + equipo['mantenimiento']

    return costo_fijo_total, costo_variable_total, equipo['modelo'], equipo['costo_adq']

# --- SESSION STATE ---
if 'proyecto' not in st.session_state:
    st.session_state['proyecto'] = []

# --- INTERFAZ ---
st.title("🏢 MPS ENTERPRISE V3.2 | Deal Architect")
st.markdown("Generador de Contratos Corporativos con **Cálculo de Excedentes**.")

with st.sidebar:
    st.header("Configuración Global")
    margen_meta = st.slider("Margen Meta (%)", 10, 60, 30) / 100
    incluir_papel = st.checkbox("Incluir Papel", value=True)
    costo_papel = st.number_input("Costo Resma ($)", value=2.80)
    
    st.divider()
    st.info("💡 Nota: Si estás en la Nube, los datos se reinician al actualizar código. En PC local se mantienen.")
    if st.button("🗑️ Limpiar Proyecto Actual"):
        st.session_state['proyecto'] = []
        st.rerun()

# TABS
tab1, tab2, tab3, tab4 = st.tabs([
    "🛠️ 1. Inventario", 
    "🏗️ 2. Armador Proyecto", 
    "📊 3. OFERTA COMERCIAL", 
    "📈 4. Proyección"
])

# ==============================================================================
# TAB 1: INVENTARIO
# ==============================================================================
with tab1:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Alta de Equipos")
        with st.form("nuevo_equipo"):
            marca = st.text_input("Marca", "Brother")
            modelo = st.text_input("Modelo")
            costo = st.number_input("Costo Equipo ($)", 0.0)
            residual = st.number_input("Valor Residual ($)", 50.0)
            manto = st.number_input("Mantenimiento Mensual ($)", 20.0)
            if st.form_submit_button("Guardar Equipo"):
                cursor = conn.cursor()
                cursor.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                               (marca, modelo, costo, residual, 36, manto))
                conn.commit()
                st.success(f"Equipo {modelo} guardado.")
                st.rerun()
    
    with c2:
        st.subheader("Asignar Consumibles")
        equipos = pd.read_sql("SELECT * FROM equipos", conn)
        if not equipos.empty:
            eq_id = st.selectbox("Seleccionar Equipo", equipos['id'].tolist(), format_func=lambda x: equipos[equipos['id']==x]['modelo'].values[0])
            with st.form("nuevo_cons"):
                col_a, col_b, col_c = st.columns(3)
                tipo = col_a.selectbox("Tipo", ["Toner", "Drum", "Fuser", "Kit"])
                costo_c = col_b.number_input("Costo ($)", 0.0)
                rend = col_c.number_input("Rendimiento", 10000)
                if st.form_submit_button("Guardar Consumible"):
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (eq_id, tipo, costo_c, rend))
                    conn.commit()
                    st.success("Consumible agregado.")
            
            # Mostrar consumibles actuales
            cons_actuales = pd.read_sql(f"SELECT tipo, costo, rendimiento FROM consumibles WHERE equipo_id={eq_id}", conn)
            if not cons_actuales.empty:
                st.dataframe(cons_actuales, use_container_width=True)
        else:
            st.warning("Registra al menos un equipo a la izquierda.")

# ==============================================================================
# TAB 2: ARMADOR
# ==============================================================================
with tab2:
    st.subheader("🛒 Construcción del Contrato")
    equipos_disponibles = pd.read_sql("SELECT * FROM equipos", conn)
    
    if equipos_disponibles.empty:
        st.warning("Ve a la Pestaña 1 y carga tus impresoras primero.")
    else:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
            with c1: sede = st.text_input("Sede / Área", placeholder="Ej: Contabilidad")
            with c2: id_eq_sel = st.selectbox("Modelo", equipos_disponibles['id'].tolist(), format_func=lambda x: equipos_disponibles[equipos_disponibles['id']==x]['modelo'].values[0])
            with c3: cantidad = st.number_input("Cant.", 1, 100, 1)
            with c4: vol_unit = st.number_input("Vol. Unitario", 100, 100000, 2000)
            with c5: 
                st.write("")
                st.write("")
                btn = st.button("➕ Agregar")

        if btn and sede:
            fijo_u, var_u_tot, mod_nom, cost_adq = calcular_costos_equipo(id_eq_sel, vol_unit, incluir_papel, costo_papel)
            
            # Totales Línea
            costo_fijo_tot = fijo_u * cantidad
            costo_var_tot = var_u_tot * cantidad
            costo_total = costo_fijo_tot + costo_var_tot
            
            item = {
                "Sede": sede, "Modelo": mod_nom, "Cantidad": cantidad,
                "Vol. Total": vol_unit * cantidad,
                "Costo Fijo Raw": costo_fijo_tot, "Costo Var Raw": costo_var_tot,
                "Inversión": cost_adq * cantidad
            }
            st.session_state['proyecto'].append(item)
            st.success(f"Agregado: {sede}")

        if len(st.session_state['proyecto']) > 0:
            df = pd.DataFrame(st.session_state['proyecto'])
            st.divider()
            st.dataframe(df[["Sede", "Modelo", "Cantidad", "Vol. Total"]].style.format({"Vol. Total": "{:,.0f}"}), use_container_width=True)
            if st.button("Deshacer última línea"):
                st.session_state['proyecto'].pop()
                st.rerun()

# ==============================================================================
# TAB 3: OFERTA COMERCIAL (CON EXCEDENTES)
# ==============================================================================
with tab3:
    if len(st.session_state['proyecto']) == 0:
        st.info("Arma el proyecto primero.")
    else:
        df = pd.DataFrame(st.session_state['proyecto'])
        
        # Totales
        vol_total = df['Vol. Total'].sum()
        costo_fijo_tot = df['Costo Fijo Raw'].sum()
        costo_var_tot = df['Costo Var Raw'].sum()
        costo_total_proyecto = costo_fijo_tot + costo_var_tot
        
        # Margen Venta
        facturacion_target = costo_total_proyecto / (1 - margen_meta)
        
        # --- CÁLCULO DE ESTRATEGIAS ---
        
        # A. PRECIO ÚNICO
        precio_unico = facturacion_target / vol_total if vol_total > 0 else 0
        
        # B. HÍBRIDO
        renta_sug = costo_fijo_tot / (1 - margen_meta)
        click_sug = (costo_var_tot / (1 - margen_meta)) / vol_total if vol_total > 0 else 0
        
        # C. TARIFA PLANA (CON EXCEDENTE)
        mensualidad = facturacion_target
        # Precio Excedente = Precio Único (A) + 10% Penalidad
        precio_excedente = precio_unico * 1.10
        
        # --- VISUALIZACIÓN ---
        st.markdown(f"### 🏆 ESTRATEGIAS COMERCIALES (Margen {margen_meta*100:.0f}%)")
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("""<div class="offer-card"><div class="offer-title">OPCIÓN A<br>PRECIO ÚNICO</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="offer-price">${precio_unico:.4f}</div>""", unsafe_allow_html=True)
            st.markdown("""<div class="offer-detail">Pago 100% Variable por hoja.<br>Todo incluido.</div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown("""<div class="offer-card"><div class="offer-title">OPCIÓN B<br>HÍBRIDO</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="offer-price">${renta_sug:,.2f}</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="offer-detail">+ Click: <b>${click_sug:.4f}</b><br>Renta asegura equipos.</div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c3:
            st.markdown("""<div class="offer-card"><div class="offer-title">OPCIÓN C<br>TARIFA PLANA</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="offer-price">${mensualidad:,.2f}</div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="offer-detail">Bolsa de {vol_total:,.0f} páginas.<br>Factura fija mensual.</div>""", unsafe_allow_html=True)
            # AQUÍ ESTÁ EL EXCEDENTE
            st.markdown(f"""<div class="excess-price">⚠️ Excedente: ${precio_excedente:.4f} / pág</div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.metric("Utilidad Mensual Proyectada", f"${(facturacion_target - costo_total_proyecto):,.2f}", delta="Ganancia Neta")

# ==============================================================================
# TAB 4: PROYECCIÓN
# ==============================================================================
with tab4:
    if len(st.session_state['proyecto']) > 0:
        meses = st.slider("Plazo", 12, 60, 36)
        inversion = df['Inversión'].sum()
        utilidad = facturacion_target - costo_total_proyecto
        
        # Cash Flow
        flujo = [utilidad] * meses
        flujo[0] -= inversion
        acumulado = np.cumsum(flujo)
        
        # Gráfico
        df_chart = pd.DataFrame({"Mes": range(1, meses+1), "Acumulado": acumulado})
        fig = px.area(df_chart, x="Mes", y="Acumulado", title="Cash Flow Acumulado (ROI)")
        fig.add_hline(y=0, line_dash="dot", line_color="red")
        
        c1, c2 = st.columns([1, 3])
        c1.metric("Inversión Total", f"${inversion:,.2f}")
        c1.metric("ROI Total", f"{(acumulado[-1]/inversion)*100:.1f}%")
        c2.plotly_chart(fig, use_container_width=True)
