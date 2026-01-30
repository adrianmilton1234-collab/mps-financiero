import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MPS Engine V2.0", page_icon="🖨️", layout="wide")

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #ffffff; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A; color: white; }
    .metric-card { background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #1E3A8A; }
    h1, h2, h3 { color: #0F172A; }
    </style>
""", unsafe_allow_html=True)

# --- CAPA DE DATOS (BACKEND SQLITE) ---
def init_db():
    conn = sqlite3.connect('mps_data.db')
    c = conn.cursor()
    # Tabla Equipos
    c.execute('''CREATE TABLE IF NOT EXISTS equipos
                 (id INTEGER PRIMARY KEY, marca TEXT, modelo TEXT, tipo TEXT, 
                  velocidad INTEGER, costo_adq REAL, residual REAL, vida_util INTEGER, mantenimiento REAL)''')
    # Tabla Consumibles
    c.execute('''CREATE TABLE IF NOT EXISTS consumibles
                 (id INTEGER PRIMARY KEY, equipo_id INTEGER, tipo TEXT, costo REAL, rendimiento INTEGER,
                  FOREIGN KEY(equipo_id) REFERENCES equipos(id))''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNCIONES DE CÁLCULO (LÓGICA DE NEGOCIO) ---

def calcular_cpp(equipo_id, incluir_papel, costo_papel):
    """Calcula el Costo Por Página (CPP) sumando consumibles + papel"""
    df_cons = pd.read_sql_query(f"SELECT * FROM consumibles WHERE equipo_id = {equipo_id}", conn)
    
    cpp_total = 0
    detalles = []
    
    # 1. Sumar consumibles (Toner, Drum, Fuser, etc.)
    for _, row in df_cons.iterrows():
        if row['rendimiento'] > 0:
            costo_unit = row['costo'] / row['rendimiento']
            cpp_total += costo_unit
            detalles.append(f"{row['tipo']}: ${costo_unit:.4f}")
    
    # 2. Sumar Papel
    costo_hoja_papel = 0
    if incluir_papel:
        costo_hoja_papel = costo_papel / 500
        cpp_total += costo_hoja_papel
        detalles.append(f"Papel: ${costo_hoja_papel:.4f}")
        
    return cpp_total, detalles

def calcular_amortizacion_francesa(monto, tasa_anual, meses):
    """Calcula cuota mensual fija (Método Francés)"""
    if tasa_anual == 0: return monto / meses
    tasa_mensual = (tasa_anual / 100) / 12
    cuota = monto * (tasa_mensual * (1 + tasa_mensual)**meses) / ((1 + tasa_mensual)**meses - 1)
    return cuota

# --- INTERFAZ DE USUARIO (FRONTEND) ---

st.title("🖨️ MPS QUOTE ENGINE V2.0")
st.markdown("**Sistema Integral de Gestión de Servicios de Impresión**")

# Sidebar: Variables Globales
with st.sidebar:
    st.header("⚙️ Configuración Global")
    margen_meta = st.slider("Margen Meta (%)", 10, 60, 30) / 100
    st.divider()
    incluir_papel = st.checkbox("Incluir Papel", value=True)
    costo_papel = st.number_input("Costo Resma ($)", value=2.80, step=0.10)
    st.info("Base de datos: Conectada (SQLite)")

# TABS PRINCIPALES
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 1. Simulación & Precios", 
    "🛠️ 2. Inventario Equipos", 
    "💰 3. Financiamiento", 
    "📈 4. Proyección Financiera"
])

# ==============================================================================
# TAB 2: INVENTARIO (Lo ponemos primero en código para poblar datos, pero es la Tab 2 visual)
# ==============================================================================
with tab2:
    col_inv1, col_inv2 = st.columns([1, 2])
    
    with col_inv1:
        st.subheader("Nuevo Equipo")
        with st.form("form_equipo"):
            marca = st.text_input("Marca")
            modelo = st.text_input("Modelo")
            tipo = st.selectbox("Tipo", ["Monocromo", "Color"])
            velocidad = st.number_input("Velocidad (PPM)", 0)
            costo_adq = st.number_input("Costo Adquisición ($)", 0.0)
            residual = st.number_input("Valor Residual ($)", 0.0)
            vida_util = st.number_input("Vida Útil (Meses)", 36)
            manto = st.number_input("Costo Mantenimiento Mensual ($)", 0.0)
            
            submitted = st.form_submit_button("Guardar Equipo")
            if submitted and modelo:
                c = conn.cursor()
                c.execute("INSERT INTO equipos (marca, modelo, tipo, velocidad, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?,?,?)",
                          (marca, modelo, tipo, velocidad, costo_adq, residual, vida_util, manto))
                conn.commit()
                st.success("Equipo guardado.")
                st.rerun()

    with col_inv2:
        st.subheader("Gestión de Consumibles")
        equipos_df = pd.read_sql_query("SELECT * FROM equipos", conn)
        
        if not equipos_df.empty:
            equipo_sel_id = st.selectbox("Seleccionar Equipo para editar consumibles", 
                                         equipos_df['id'].tolist(), 
                                         format_func=lambda x: equipos_df[equipos_df['id'] == x]['modelo'].values[0])
            
            # Formulario Consumibles
            with st.form("form_consumible"):
                c1, c2, c3 = st.columns(3)
                tipo_cons = c1.selectbox("Tipo", ["Toner", "Drum", "Fuser", "Belt", "Waste Box", "Kit Manto"])
                costo_cons = c2.number_input("Costo ($)", 0.0)
                rend_cons = c3.number_input("Rendimiento (Págs)", 0)
                add_cons = st.form_submit_button("Agregar Consumible")
                
                if add_cons:
                    c = conn.cursor()
                    c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)",
                              (equipo_sel_id, tipo_cons, costo_cons, rend_cons))
                    conn.commit()
                    st.success("Consumible agregado.")
                    st.rerun()
            
            # Ver consumibles actuales
            cons_df = pd.read_sql_query(f"SELECT * FROM consumibles WHERE equipo_id = {equipo_sel_id}", conn)
            st.dataframe(cons_df, hide_index=True)
        else:
            st.warning("Registra un equipo primero.")

# ==============================================================================
# TAB 1: SIMULACIÓN DE PRECIOS
# ==============================================================================
with tab1:
    equipos_df = pd.read_sql_query("SELECT * FROM equipos", conn)
    
    if equipos_df.empty:
        st.warning("⚠️ No hay equipos registrados. Ve a la pestaña 2 e ingresa el inventario.")
    else:
        # Selección del Equipo
        col_sel, col_vol = st.columns(2)
        with col_sel:
            id_equipo_sim = st.selectbox("Selecciona Equipo a Cotizar", 
                                         equipos_df['id'].tolist(), 
                                         format_func=lambda x: equipos_df[equipos_df['id'] == x]['modelo'].values[0])
        
        # Recuperar datos del equipo
        equipo_data = equipos_df[equipos_df['id'] == id_equipo_sim].iloc[0]
        
        with col_vol:
            volumen_mensual = st.number_input("Volumen Mensual Estimado", value=5000, step=1000)

        # CÁLCULOS
        cpp_operativo, detalles_cpp = calcular_cpp(id_equipo_sim, incluir_papel, costo_papel)
        
        # Amortización Lineal Simple para Costo Operativo Interno
        depreciacion_mensual = (equipo_data['costo_adq'] - equipo_data['residual']) / equipo_data['vida_util']
        costo_fijo_mes = depreciacion_mensual + equipo_data['mantenimiento']
        
        # Costo Total Proyecto
        costo_variable_total = cpp_operativo * volumen_mensual
        costo_total_mensual = costo_fijo_mes + costo_variable_total
        
        # Precio Sugerido (Base Margen)
        precio_venta_mensual = costo_total_mensual / (1 - margen_meta) # Fórmula correcta de margen sobre venta
        precio_por_click = precio_venta_mensual / volumen_mensual

        # --- VISUALIZACIÓN ---
        st.markdown("### 🎯 Análisis de Costos y Precios")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Costo Operativo Unitario", f"${cpp_operativo:.4f}")
        m2.metric("Costo Total Mensual", f"${costo_total_mensual:,.2f}")
        m3.metric("Precio Sugerido (All-In)", f"${precio_por_click:.4f}")
        m4.metric("Facturación Mensual", f"${precio_venta_mensual:,.2f}", delta=f"{margen_meta*100:.0f}% Margen")

        # Guardar en Session State para usar en otras Tabs
        st.session_state['simulacion'] = {
            'equipo': equipo_data['modelo'],
            'costo_adq': equipo_data['costo_adq'],
            'ingreso_mensual': precio_venta_mensual,
            'costo_operativo_mensual': costo_variable_total + equipo_data['mantenimiento'], # Sin amortización (eso va en financiero)
            'volumen': volumen_mensual
        }

        # Desglose Visual
        st.divider()
        c_chart, c_prop = st.columns(2)
        
        with c_chart:
            # Grafico Breakdown
            labels = ['Depreciación', 'Mantenimiento', 'Consumibles + Papel', 'Utilidad Neta']
            values = [depreciacion_mensual, equipo_data['mantenimiento'], costo_variable_total, (precio_venta_mensual - costo_total_mensual)]
            fig = px.pie(names=labels, values=values, title="Estructura del Precio Mensual", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
            
        with c_prop:
            st.subheader("📋 Propuestas Comerciales")
            st.info(f"**Plan A (Variable Puro):** ${precio_por_click:.4f} por página.")
            st.success(f"**Plan B (Híbrido):** Renta ${costo_fijo_mes*1.3:,.2f} + Click ${(cpp_operativo*1.3):.4f}")
            st.warning(f"**Plan C (Tarifa Plana):** ${precio_venta_mensual:,.2f} mensuales (Hasta {volumen_mensual} págs).")

# ==============================================================================
# TAB 3: ESCENARIOS DE FINANCIAMIENTO
# ==============================================================================
with tab3:
    if 'simulacion' not in st.session_state:
        st.warning("Primero realiza una simulación en la Pestaña 1.")
    else:
        sim = st.session_state['simulacion']
        st.subheader(f"Financiamiento para: {sim['equipo']}")
        st.write(f"Inversión Requerida: **${sim['costo_adq']:,.2f}**")
        
        col_fin1, col_fin2 = st.columns(2)
        
        with col_fin1:
            escenario = st.radio("Método de Adquisición", ["Contado (Fondos Propios)", "Préstamo Bancario", "Crédito Mayorista"])
        
        with col_fin2:
            tasa = 0.0
            plazo = 12
            if escenario != "Contado (Fondos Propios)":
                tasa = st.number_input("Tasa Interés Anual (%)", 0.0, 50.0, 12.0)
                plazo = st.slider("Plazo (Meses)", 12, 60, 36)
        
        # Calcular Cuota
        cuota_financiera = 0
        total_intereses = 0
        
        if escenario == "Contado (Fondos Propios)":
            st.session_state['flujo_financiero'] = {'cuota': 0, 'inicial': sim['costo_adq']}
        else:
            cuota_financiera = calcular_amortizacion_francesa(sim['costo_adq'], tasa, plazo)
            total_pagado = cuota_financiera * plazo
            total_intereses = total_pagado - sim['costo_adq']
            
            st.markdown(f"""
            <div class="metric-card">
                <h3>Resultados Financieros</h3>
                <p>Cuota Mensual: <b>${cuota_financiera:,.2f}</b></p>
                <p>Total Intereses: <span style='color:red'>${total_intereses:,.2f}</span></p>
            </div>
            """, unsafe_allow_html=True)
            
            st.session_state['flujo_financiero'] = {'cuota': cuota_financiera, 'inicial': 0, 'plazo': plazo}

# ==============================================================================
# TAB 4: PROYECCIÓN FINANCIERA (CASH FLOW)
# ==============================================================================
with tab4:
    if 'flujo_financiero' not in st.session_state:
        st.warning("Configura el financiamiento en la Pestaña 3.")
    else:
        sim = st.session_state['simulacion']
        fin = st.session_state['flujo_financiero']
        
        meses_proyeccion = st.slider("Meses a Proyectar", 12, 60, 36)
        
        # Construir Flujo de Caja
        flujo = []
        acumulado = 0
        saldo_caja = -fin['inicial'] # Si es contado, empieza negativo
        
        for m in range(1, meses_proyeccion + 1):
            ingreso = sim['ingreso_mensual']
            egreso_op = sim['costo_operativo_mensual']
            
            # Egreso Financiero (Cuota) solo si está dentro del plazo del crédito
            egreso_fin = fin['cuota'] if (fin.get('plazo', 0) >= m) else 0
            
            neto_mes = ingreso - egreso_op - egreso_fin
            saldo_caja += neto_mes
            
            flujo.append({
                "Mes": m,
                "Ingresos": ingreso,
                "Costos Operativos": egreso_op,
                "Pago Financiero": egreso_fin,
                "Utilidad Neta": neto_mes,
                "Flujo Acumulado": saldo_caja
            })
            
        df_flujo = pd.DataFrame(flujo)
        
        # Métricas Resumen
        col_res1, col_res2, col_res3 = st.columns(3)
        total_utilidad = df_flujo['Utilidad Neta'].sum()
        roi = (total_utilidad / sim['costo_adq']) * 100
        
        col_res1.metric("Utilidad Total Proyectada", f"${total_utilidad:,.2f}")
        col_res2.metric("ROI del Proyecto", f"{roi:.1f}%")
        col_res3.metric("Punto de Recuperación", f"Mes {df_flujo[df_flujo['Flujo Acumulado'] > 0].index.min() + 1 if (df_flujo['Flujo Acumulado'] > 0).any() else 'N/A'}")

        # Gráficos
        tab_g1, tab_g2 = st.tabs(["📉 Flujo Mensual", "🚀 Flujo Acumulado"])
        
        with tab_g1:
            fig_bar = px.bar(df_flujo, x="Mes", y=["Ingresos", "Costos Operativos", "Pago Financiero"], 
                             title="Ingresos vs Egresos Mensuales", barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with tab_g2:
            fig_area = px.area(df_flujo, x="Mes", y="Flujo Acumulado", title="Crecimiento de la Caja (Cash Flow)")
            # Línea de 0
            fig_area.add_hline(y=0, line_dash="dot", line_color="red", annotation_text="Break Even")
            st.plotly_chart(fig_area, use_container_width=True)
            
        # Exportar
        csv = df_flujo.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Proyección a Excel (CSV)", data=csv, file_name="proyeccion_mps.csv", mime="text/csv")
