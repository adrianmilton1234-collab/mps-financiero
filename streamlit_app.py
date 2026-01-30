import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN INICIAL (Solo un título global) ---
st.set_page_config(page_title="MPS Quote Engine V7.0", page_icon="🚀", layout="wide")

# TÍTULO PRINCIPAL FIJO
st.title("🚀 MPS QUOTE ENGINE | Generador de Contratos")
st.markdown("Simulador financiero integral para contratos MPS — costos, márgenes, financiamiento y proyecciones.")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    h1, h2, h3 { color: #0f172a; font-family: 'Segoe UI', sans-serif; }
    
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; background-color: white; padding: 10px 10px 0px 10px; 
        border-radius: 12px 12px 0px 0px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); 
    }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; border-radius: 8px 8px 0px 0px; border: none; 
        font-weight: 600; color: #64748b; background-color: transparent;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #1e40af; color: white; 
    }
    
    .offer-card {
        background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 20px;
        text-align: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        height: 100%; display: flex; flex-direction: column; justify-content: space-between;
    }
    .offer-title { color: #1e40af; font-weight: 800; font-size: 1.1rem; text-transform: uppercase; margin-bottom: 5px;}
    .offer-price { font-size: 2.2rem; font-weight: 800; color: #0f172a; margin: 5px 0; }
    .offer-desc { font-size: 0.85rem; color: #64748b; margin-bottom: 10px; }
    .offer-benefit { background-color: #eff6ff; color: #1e40af; padding: 8px; border-radius: 8px; font-size: 0.8rem; font-weight: 600; margin-top: 10px;}
    
    .badge-excess { background-color: #fee2e2; color: #991b1b; font-size: 0.8rem; padding: 4px 8px; border-radius: 10px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- BACKEND (SQLITE PRECARGADO) ---
def init_db():
    conn = sqlite3.connect('mps_cfo_v7.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS equipos
                 (id INTEGER PRIMARY KEY, marca TEXT, modelo TEXT, tipo TEXT, 
                  velocidad INTEGER, costo_adq REAL, residual REAL, vida_util INTEGER, mantenimiento REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS consumibles
                 (id INTEGER PRIMARY KEY, equipo_id INTEGER, tipo TEXT, costo REAL, rendimiento INTEGER,
                  FOREIGN KEY(equipo_id) REFERENCES equipos(id))''')
    
    # Pre-carga si está vacío
    c.execute("SELECT count(*) FROM equipos")
    if c.fetchone()[0] == 0:
        # 1. Brother L6915DW
        c.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)", ("Brother", "MFC-L6915DW", 885.00, 50.00, 36, 20.00))
        id_1 = c.lastrowid
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_1, "Toner", 145.48, 25000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_1, "Drum", 97.19, 75000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_1, "Fuser", 185.00, 200000))
        # 2. Brother L6900DW
        c.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)", ("Brother", "MFC-L6900DW", 856.00, 50.00, 36, 20.00))
        id_2 = c.lastrowid
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_2, "Toner", 112.50, 20000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_2, "Drum", 86.89, 50000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_2, "Fuser", 185.00, 200000))
        # 3. Brother Color
        c.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)", ("Brother", "MFC-L9630CDN", 1275.00, 50.00, 36, 20.00))
        id_3 = c.lastrowid
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_3, "Toner CMYK", 492.00, 10000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_3, "Drum", 178.64, 100000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_3, "Fuser", 185.00, 200000))
    conn.commit()
    return conn

conn = init_db()

# --- FUNCIONES DE CÁLCULO ---
def calcular_amortizacion(monto, tasa_anual, meses, tipo, gracia=0):
    tabla = []
    saldo = monto
    tasa_mensual = (tasa_anual / 100) / 12
    plazo_pago = meses - gracia
    
    cuota_francesa = 0
    if tipo == "Francesa" and tasa_mensual > 0 and plazo_pago > 0:
        cuota_francesa = saldo * (tasa_mensual * (1 + tasa_mensual)**plazo_pago) / ((1 + tasa_mensual)**plazo_pago - 1)
    elif tipo == "Francesa" and tasa_mensual == 0 and plazo_pago > 0:
        cuota_francesa = saldo / plazo_pago
    
    amort_alemana = saldo / plazo_pago if plazo_pago > 0 else 0

    for m in range(1, meses + 1):
        interes = saldo * tasa_mensual
        if m <= gracia:
            pago_capital = 0; cuota = interes; saldo_final = saldo
        else:
            if tipo == "Francesa": cuota = cuota_francesa; pago_capital = cuota - interes
            else: pago_capital = amort_alemana; cuota = pago_capital + interes
            saldo_final = saldo - pago_capital
            if saldo_final < 0: saldo_final = 0
        tabla.append({"Mes": m, "Cuota Total": cuota, "Interés": interes, "Capital": pago_capital, "Saldo": saldo_final})
        saldo = saldo_final
    return pd.DataFrame(tabla)

def get_detalles_equipo(equipo_id, volumen_unit, incluir_papel, costo_papel):
    """Calcula costos unitarios y totales para una línea"""
    df_cons = pd.read_sql_query(f"SELECT * FROM consumibles WHERE equipo_id = {equipo_id}", conn)
    cpp_cons = 0
    for _, row in df_cons.iterrows():
        if row['rendimiento'] > 0: cpp_cons += row['costo'] / row['rendimiento']
    
    cpp_papel = costo_papel / 500 if incluir_papel else 0
    cpp_total = cpp_cons + cpp_papel
    
    eq = pd.read_sql_query(f"SELECT * FROM equipos WHERE id = {equipo_id}", conn).iloc[0]
    
    return {
        "modelo": eq['modelo'], "costo_adq": eq['costo_adq'], "manto": eq['mantenimiento'],
        "cpp": cpp_total, "opex_var": cpp_total * volumen_unit
    }

# --- SESSION STATE ---
if 'proyecto' not in st.session_state: st.session_state['proyecto'] = []
if 'financiamiento' not in st.session_state: st.session_state['financiamiento'] = {}

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2885/2885456.png", width=70)
    st.markdown("### Configuración")
    margen_meta = st.slider("Margen Meta (%)", 10, 60, 30) / 100
    st.divider()
    incluir_papel = st.toggle("Incluir Papel", value=True)
    costo_papel = st.number_input("Costo Resma ($)", value=2.80) if incluir_papel else 0
    st.divider()
    if st.button("🗑️ Nuevo Proyecto", type="primary"):
        st.session_state['proyecto'] = []
        st.session_state['financiamiento'] = {}
        st.rerun()

# --- TABS ---
tabs = st.tabs(["🛠️ 1. Inventario", "🏗️ 2. Armador (Editable)", "💰 3. Financiamiento", "📊 4. Oferta Comercial", "📈 5. Proyección", "📦 6. Stock"])

# ================= TAB 1: INVENTARIO =================
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Alta de Equipos")
        with st.form("alta"):
            marca = st.text_input("Marca", "Brother")
            modelo = st.text_input("Modelo")
            costo = st.number_input("Costo ($)", 0.0)
            res = st.number_input("Residual ($)", 50.0)
            manto = st.number_input("Mantenimiento ($)", 20.0)
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)", (marca, modelo, costo, res, 36, manto))
                conn.commit(); st.rerun()
    with c2:
        st.subheader("Gestión de Consumibles")
        eqs = pd.read_sql("SELECT * FROM equipos", conn)
        if not eqs.empty:
            eq_id = st.selectbox("Equipo", eqs['id'].tolist(), format_func=lambda x: eqs[eqs['id']==x]['modelo'].values[0])
            # Data Editor para Consumibles
            cons_df = pd.read_sql(f"SELECT tipo, costo, rendimiento FROM consumibles WHERE equipo_id={eq_id}", conn)
            st.info("💡 Edita costos y rendimientos directamente aquí:")
            edited_cons = st.data_editor(cons_df, num_rows="dynamic", use_container_width=True, key="editor_inv")
            if st.button("💾 Guardar Cambios Inventario"):
                conn.execute(f"DELETE FROM consumibles WHERE equipo_id={eq_id}")
                for i, r in edited_cons.iterrows():
                    if r['tipo']: conn.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (eq_id, r['tipo'], r['costo'], r['rendimiento']))
                conn.commit(); st.success("Actualizado"); st.rerun()

# ================= TAB 2: ARMADOR (EDITABLE) =================
with tabs[1]:
    st.subheader("Configuración de Sedes y Equipos")
    eqs = pd.read_sql("SELECT * FROM equipos", conn)
    
    if not eqs.empty:
        # 1. INPUT PARA AGREGAR NUEVOS
        with st.expander("➕ Agregar Nueva Línea", expanded=True):
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
            with c1: sede = st.text_input("Sede / Dpto")
            with c2: id_eq = st.selectbox("Modelo", eqs['id'].tolist(), format_func=lambda x: eqs[eqs['id']==x]['modelo'].values[0])
            with c3: cant = st.number_input("Cant.", 1, 100, 1)
            with c4: vol = st.number_input("Vol. Unit.", 100, 200000, 3000)
            with c5: 
                st.write("")
                st.write("") 
                if st.button("Agregar"):
                    det = get_detalles_equipo(id_eq, vol, incluir_papel, costo_papel)
                    st.session_state['proyecto'].append({
                        "Sede": sede, "Modelo": det['modelo'], "Cantidad": cant, "Vol. Unit": vol,
                        "Vol. Total": vol*cant, "Inversión": det['costo_adq']*cant,
                        "OPEX Fijo": det['manto']*cant, "OPEX Var": det['opex_var']*cant, "Eq_ID": id_eq
                    })
                    st.rerun()

        # 2. TABLA EDITABLE (EL CAMBIO PRINCIPAL)
        if len(st.session_state['proyecto']) > 0:
            st.divider()
            st.info("✏️ Puedes editar 'Cantidad' y 'Vol. Unit' directamente en la tabla. El sistema recalculará todo.")
            
            df_proy = pd.DataFrame(st.session_state['proyecto'])
            
            # Configurar editor para permitir editar solo ciertas columnas
            edited_proy = st.data_editor(
                df_proy,
                column_config={
                    "Sede": st.column_config.TextColumn("Sede"),
                    "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1),
                    "Vol. Unit": st.column_config.NumberColumn("Vol. Unit", min_value=0, step=100),
                    "Modelo": st.column_config.TextColumn("Modelo", disabled=True), # Modelo fijo para no romper lógica de costos
                    "Vol. Total": st.column_config.NumberColumn("Vol. Total", disabled=True),
                    "Inversión": st.column_config.NumberColumn("Inversión", disabled=True)
                },
                use_container_width=True,
                num_rows="dynamic",
                key="editor_proyecto"
            )

            # LÓGICA DE RE-CÁLCULO AL DETECTAR CAMBIOS
            if not df_proy.equals(edited_proy):
                # Si hubo cambios, recalculamos costos basados en las nuevas cantidades/volúmenes
                new_proy_list = []
                for idx, row in edited_proy.iterrows():
                    # Recalcular costos con la nueva cantidad y volumen
                    det = get_detalles_equipo(row['Eq_ID'], row['Vol. Unit'], incluir_papel, costo_papel)
                    new_row = row.to_dict()
                    new_row['Vol. Total'] = row['Vol. Unit'] * row['Cantidad']
                    new_row['Inversión'] = det['costo_adq'] * row['Cantidad']
                    new_row['OPEX Fijo'] = det['manto'] * row['Cantidad']
                    new_row['OPEX Var'] = det['opex_var'] * row['Cantidad']
                    new_proy_list.append(new_row)
                
                st.session_state['proyecto'] = new_proy_list
                st.rerun() # Refrescar para mostrar nuevos totales

            tot_inv = sum(p['Inversión'] for p in st.session_state['proyecto'])
            st.markdown(f"#### Inversión Total (CAPEX): :blue[${tot_inv:,.2f}]")
    else: st.warning("Carga inventario en Tab 1.")

# ================= TAB 3: FINANCIAMIENTO =================
with tabs[2]:
    st.subheader("Estrategia de Financiamiento")
    if len(st.session_state['proyecto']) == 0: st.info("Arma el proyecto primero.")
    else:
        monto_total = sum(p['Inversión'] for p in st.session_state['proyecto'])
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Monto a Financiar", f"${monto_total:,.2f}")
            tipo_fin = st.selectbox("Fuente", ["Propios", "Bancario", "Mayorista"])
            tasa=0.0; plazo=36; gracia=0; metodo="Francesa"
            
            if tipo_fin != "Propios":
                tasa = st.number_input("Tasa Anual (%)", 0.0, 100.0, 12.0)
                plazo = st.number_input("Plazo (Meses)", 1, 60, 36)
                if tipo_fin == "Mayorista": gracia = st.number_input("Gracia (Meses)", 0, 12, 0)
            
            if tipo_fin == "Propios": df_amort = pd.DataFrame(); interes_total = 0
            else:
                df_amort = calcular_amortizacion(monto_total, tasa, plazo, metodo, gracia)
                interes_total = df_amort['Interés'].sum()
            
            st.session_state['financiamiento'] = {"Tipo": tipo_fin, "Tabla": df_amort, "Inv": monto_total, "Int": interes_total, "Plazo": plazo}
        
        with c2:
            if not df_amort.empty:
                st.metric("Costo Financiero Total", f"${interes_total:,.2f}")
                st.plotly_chart(px.bar(df_amort, x="Mes", y=["Capital", "Interés"], title="Flujo de Pagos"), use_container_width=True)

# ================= TAB 4: OFERTA COMERCIAL (MEJORADA) =================
with tabs[3]:
    st.subheader("Análisis de Costos y Oferta")
    if len(st.session_state['proyecto']) > 0:
        df = pd.DataFrame(st.session_state['proyecto'])
        vol_total = df['Vol. Total'].sum()
        opex_total = df['OPEX Fijo'].sum() + df['OPEX Var'].sum()
        
        fin = st.session_state.get('financiamiento', {})
        if not fin: st.error("Configura Tab 3."); st.stop()
        
        # Costo Fin Mensual
        costo_fin_mes = fin['Inv']/36 if fin['Tipo']=="Propios" else (fin['Tabla']['Cuota Total'].mean() if not fin['Tabla'].empty else 0)
        
        costo_total_real = opex_total + costo_fin_mes
        fact_meta = costo_total_real / (1 - margen_meta)
        
        # Precios
        p_unico = fact_meta / vol_total if vol_total else 0
        renta = (df['OPEX Fijo'].sum() + costo_fin_mes) / (1 - margen_meta)
        click = (df['OPEX Var'].sum() / (1 - margen_meta)) / vol_total if vol_total else 0
        excedente = p_unico * 1.15
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<div class="offer-card">
            <div class="offer-title">A. PLAN VARIABLE</div>
            <div class="offer-desc">All-In por página impresa.</div>
            <div class="offer-price">${p_unico:.4f}</div>
            <div class="offer-benefit">✅ Ideal para: Clientes con volumen variable o incierto. Sin fijos altos.</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="offer-card">
            <div class="offer-title">B. PLAN HÍBRIDO</div>
            <div class="offer-desc">Renta Fija + Click Variable.</div>
            <div class="offer-price">${renta:,.2f}</div>
            <div style="text-align:center; font-weight:bold; color:#1e40af;">+ Click: ${click:.4f}</div>
            <div class="offer-benefit">✅ Ideal para: Asegurar tu costo de equipo y cobrar insumos aparte.</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="offer-card">
            <div class="offer-title">C. TARIFA PLANA</div>
            <div class="offer-desc">Factura fija mensual (Bolsa).</div>
            <div class="offer-price">${fact_meta:,.2f}</div>
            <div class="badge-excess">⚠️ Excedente: ${excedente:.4f}</div>
            <div class="offer-benefit">✅ Ideal para: Presupuestos fijos corporativos y licitaciones.</div>
            </div>""", unsafe_allow_html=True)

# ================= TAB 5: PROYECCIÓN (CASH FLOW & VPN) =================
with tabs[4]:
    st.subheader("Proyección Financiera")
    if len(st.session_state['proyecto']) > 0:
        meses = st.slider("Horizonte (Meses)", 12, 60, 36)
        inv_inicial = fin.get('Inv', 0)
        
        flujo = []
        saldo = -inv_inicial if fin['Tipo']=="Propios" else 0 # Si es banco, entra el dinero y sale al proveedor, efecto neto 0 en caja inicial pero hay deuda
        
        # Ajuste: Si es propios, la salida es Mes 0. Si es banco, no hay salida inicial de caja propia, pero hay cuota.
        
        for m in range(1, meses + 1):
            ingreso = fact_meta
            egreso_op = opex_total
            egreso_fin = fin['Tabla'].loc[fin['Tabla']['Mes']==m, 'Cuota Total'].values[0] if (not fin['Tabla'].empty and m <= len(fin['Tabla'])) else 0
            
            neto_mensual = ingreso - egreso_op - egreso_fin
            if m==1 and fin['Tipo']=="Propios": neto_mensual -= inv_inicial
            
            saldo += neto_mensual
            flujo.append({"Mes": m, "Neto": neto_mensual, "Acumulado": saldo})
        
        df_f = pd.DataFrame(flujo)
        
        # 1. GRÁFICO CASH FLOW MENSUAL
        st.markdown("#### 📊 Flujo de Caja Mensual (Ingresos - Egresos)")
        fig_cf = px.bar(df_f, x="Mes", y="Neto", title="Cash Flow Neto Mensual", color="Neto", 
                        color_continuous_scale=["red", "green"])
        st.plotly_chart(fig_cf, use_container_width=True)
        
        # 2. VPN (10%)
        tasa_desc = 0.10 / 12
        vpn = sum(x['Neto'] / ((1 + tasa_desc) ** i) for i, x in enumerate(flujo, 1))
        
        c1, c2 = st.columns(2)
        c1.info(f"💰 **VPN (10%) = ${vpn:,.2f}**\n\nRepresenta el valor actual de tus ganancias futuras descontando una tasa del 10% anual. Si es positivo, el proyecto crea valor.")
        
        # 3. GRÁFICO ACUMULADO
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_f['Mes'], y=df_f['Acumulado'], fill='tozeroy', mode='lines', name='Acumulado'))
        fig2.add_hline(y=0, line_dash="dot", line_color="red")
        st.plotly_chart(fig2, use_container_width=True)

# ================= TAB 6: STOCK POR AGENCIA =================
with tabs[5]:
    st.subheader("📦 Planificación de Compras (Stock)")
    st.markdown("Cálculo de insumos necesarios para cubrir **6 meses** de operación por Sede.")
    
    if len(st.session_state['proyecto']) > 0:
        df_p = pd.DataFrame(st.session_state['proyecto'])
        stock_list = []
        
        for idx, row in df_p.iterrows():
            # Buscar consumibles del equipo
            cons = pd.read_sql(f"SELECT tipo, rendimiento FROM consumibles WHERE equipo_id={row['Eq_ID']}", conn)
            
            for _, r in cons.iterrows():
                if r['rendimiento'] > 0:
                    consumo_mensual = row['Vol. Total'] / r['rendimiento']
                    duracion_meses = 1 / consumo_mensual if consumo_mensual > 0 else 999
                    # Estrategia: Stock para 6 meses
                    a_comprar = np.ceil(consumo_mensual * 6)
                    
                    stock_list.append({
                        "Sede": row['Sede'],
                        "Equipo": row['Modelo'],
                        "Insumo": r['tipo'],
                        "Consumo Mes": f"{consumo_mensual:.2f} un.",
                        "Duración Est.": f"{duracion_meses:.1f} meses",
                        "Stock (6 Meses)": f"{a_comprar:.0f} un."
                    })
        
        st.dataframe(pd.DataFrame(stock_list), use_container_width=True)
        st.success("💡 Esta tabla te dice exactamente qué enviar a cada agencia para no tener desabastecimiento en medio año.")
