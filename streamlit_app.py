import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MPS CFO Suite V6.0", page_icon="💼", layout="wide")

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
    .offer-title { color: #1e40af; font-weight: 800; font-size: 1.1rem; text-transform: uppercase; margin-bottom: 10px;}
    .offer-price { font-size: 2.2rem; font-weight: 800; color: #0f172a; margin: 5px 0; }
    
    .badge-excess { background-color: #fee2e2; color: #991b1b; font-size: 0.8rem; padding: 4px 8px; border-radius: 10px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- BACKEND (SQLITE CON DATOS PRECARGADOS) ---
def init_db():
    # Cambiamos nombre a v6 para asegurar una DB limpia y nueva
    conn = sqlite3.connect('mps_cfo_v6_loaded.db') 
    c = conn.cursor()
    
    # Crear Tablas
    c.execute('''CREATE TABLE IF NOT EXISTS equipos
                 (id INTEGER PRIMARY KEY, marca TEXT, modelo TEXT, tipo TEXT, 
                  velocidad INTEGER, costo_adq REAL, residual REAL, vida_util INTEGER, mantenimiento REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS consumibles
                 (id INTEGER PRIMARY KEY, equipo_id INTEGER, tipo TEXT, costo REAL, rendimiento INTEGER,
                  FOREIGN KEY(equipo_id) REFERENCES equipos(id))''')
    
    # --- CARGA AUTOMÁTICA DE DATOS (SI ESTÁ VACÍA) ---
    c.execute("SELECT count(*) FROM equipos")
    if c.fetchone()[0] == 0:
        # 1. Brother MFC-L6915DW
        c.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                  ("Brother", "MFC-L6915DW", 885.00, 50.00, 36, 20.00))
        id_1 = c.lastrowid
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_1, "Toner", 145.48, 25000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_1, "Drum", 97.19, 75000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_1, "Fuser", 185.00, 200000))

        # 2. Brother MFC-L6900DW
        c.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                  ("Brother", "MFC-L6900DW", 856.00, 50.00, 36, 20.00))
        id_2 = c.lastrowid
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_2, "Toner", 112.50, 20000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_2, "Drum", 86.89, 50000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_2, "Fuser", 185.00, 200000))

        # 3. Brother MFC-L9630CDN (Color)
        c.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                  ("Brother", "MFC-L9630CDN", 1275.00, 50.00, 36, 20.00))
        id_3 = c.lastrowid
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_3, "Toner (Set)", 492.00, 10000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_3, "Drum", 178.64, 100000))
        c.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (id_3, "Fuser", 185.00, 200000))
        
        print("✅ Datos de Brother precargados exitosamente.")

    conn.commit()
    return conn

conn = init_db()

# --- FUNCIONES FINANCIERAS ---
def calcular_vpn_manual(tasa, flujos):
    return sum(flujo / (1 + tasa) ** i for i, flujo in enumerate(flujos))

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
            if tipo == "Francesa":
                cuota = cuota_francesa; pago_capital = cuota - interes
            else: 
                pago_capital = amort_alemana; cuota = pago_capital + interes
            saldo_final = saldo - pago_capital
            if saldo_final < 0: saldo_final = 0
        
        tabla.append({"Mes": m, "Cuota Total": cuota, "Interés": interes, "Capital": pago_capital, "Saldo": saldo_final})
        saldo = saldo_final
    return pd.DataFrame(tabla)

def calcular_costos_operativos_detallado(equipo_id, volumen, incluir_papel, costo_papel):
    df_cons = pd.read_sql_query(f"SELECT * FROM consumibles WHERE equipo_id = {equipo_id}", conn)
    cpp_cons = 0
    for _, row in df_cons.iterrows():
        if row['rendimiento'] > 0:
            cpp_cons += row['costo'] / row['rendimiento']
    
    cpp_papel = costo_papel / 500 if incluir_papel else 0
    costo_var_unit = cpp_cons + cpp_papel
    equipo = pd.read_sql_query(f"SELECT * FROM equipos WHERE id = {equipo_id}", conn).iloc[0]
    
    return {
        "manto_mensual": equipo['mantenimiento'],
        "cpp_variable": costo_var_unit,
        "costo_var_total": costo_var_unit * volumen,
        "modelo": equipo['modelo'],
        "costo_adq": equipo['costo_adq']
    }

# --- SESSION STATE ---
if 'proyecto' not in st.session_state: st.session_state['proyecto'] = []
if 'financiamiento' not in st.session_state: st.session_state['financiamiento'] = {}

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.header("Configuración")
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
st.title("💼 MPS CFO Suite V6.0 (Pre-Loaded)")
st.markdown("Ahora con **Datos Brother Precargados**. ¡Listo para usar!")

tabs = st.tabs(["🛠️ 1. Inventario", "🏗️ 2. Armador", "💰 3. Financiamiento", "📊 4. Oferta Comercial", "📈 5. Proyección", "📦 6. Stock"])

# TAB 1
with tabs[0]:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Alta de Equipos")
        with st.form("alta_eq"):
            marca = st.text_input("Marca", "Brother")
            modelo = st.text_input("Modelo")
            costo = st.number_input("Costo Compra ($)", 0.0)
            residual = st.number_input("Valor Residual ($)", 50.0)
            manto = st.number_input("Mantenimiento Mensual ($)", 20.0)
            if st.form_submit_button("Guardar Equipo"):
                cursor = conn.cursor()
                cursor.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                               (marca, modelo, costo, residual, 36, manto))
                conn.commit()
                st.success(f"{modelo} Guardado")
                st.rerun()
    with c2:
        st.subheader("Consumibles (Editables)")
        equipos = pd.read_sql("SELECT * FROM equipos", conn)
        if not equipos.empty:
            eq_id = st.selectbox("Seleccionar Equipo", equipos['id'].tolist(), format_func=lambda x: equipos[equipos['id']==x]['modelo'].values[0])
            with st.expander("➕ Agregar Consumible Manual"):
                with st.form("add_cons"):
                    cc1, cc2, cc3 = st.columns(3)
                    tipo = cc1.text_input("Tipo (Ej: Kit Manto)")
                    costo_c = cc2.number_input("Costo Unit. ($)", 0.0)
                    rend = cc3.number_input("Rendimiento (Págs)", 10000)
                    if st.form_submit_button("Agregar"):
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (eq_id, tipo, costo_c, rend))
                        conn.commit()
                        st.rerun()
            
            cons_df = pd.read_sql(f"SELECT tipo, costo, rendimiento FROM consumibles WHERE equipo_id={eq_id}", conn)
            edited_df = st.data_editor(cons_df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Guardar Cambios Inventario"):
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM consumibles WHERE equipo_id={eq_id}")
                for i, row in edited_df.iterrows():
                    if row['tipo']:
                        cursor.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", 
                                       (eq_id, row['tipo'], row['costo'], row['rendimiento']))
                conn.commit()
                st.success("Inventario actualizado.")
                st.rerun()

# TAB 2
with tabs[1]:
    st.subheader("🛒 Configuración del Proyecto")
    equipos_disp = pd.read_sql("SELECT * FROM equipos", conn)
    if not equipos_disp.empty:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
            with c1: sede = st.text_input("Sede / Dpto")
            with c2: id_eq = st.selectbox("Modelo", equipos_disp['id'].tolist(), format_func=lambda x: equipos_disp[equipos_disp['id']==x]['modelo'].values[0], key="sel_eq_arm")
            with c3: cant = st.number_input("Cant.", 1, 100, 1)
            with c4: vol = st.number_input("Vol. Unit.", 100, 200000, 3000)
            with c5: 
                st.write("") 
                st.write("") 
                add_btn = st.button("➕ Agregar", use_container_width=True)
        if add_btn and sede:
            detalles = calcular_costos_operativos_detallado(id_eq, vol, incluir_papel, costo_papel)
            st.session_state['proyecto'].append({
                "Sede": sede, "Modelo": detalles['modelo'], "Cantidad": cant,
                "Vol. Total": vol * cant,
                "OPEX Fijo": detalles['manto_mensual'] * cant, 
                "OPEX Var": detalles['costo_var_total'] * cant,
                "CPP Unit": detalles['cpp_variable'], "Manto Unit": detalles['manto_mensual'],
                "Inversión": detalles['costo_adq'] * cant, "Equipo ID": id_eq
            })
            st.rerun()
        if len(st.session_state['proyecto']) > 0:
            df_proy = pd.DataFrame(st.session_state['proyecto'])
            st.dataframe(df_proy, use_container_width=True)
            tot_inv = df_proy['Inversión'].sum()
            st.markdown(f"#### Inversión Total Requerida (CAPEX): :blue[${tot_inv:,.2f}]")
            if st.button("Deshacer última línea"): st.session_state['proyecto'].pop(); st.rerun()
    else: st.warning("Error en DB.")

# TAB 3
with tabs[2]:
    st.subheader("💰 Estrategia de Financiamiento")
    if len(st.session_state['proyecto']) == 0: st.info("Arma el proyecto primero.")
    else:
        df_proy = pd.DataFrame(st.session_state['proyecto'])
        monto_total = df_proy['Inversión'].sum()
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Monto a Financiar", f"${monto_total:,.2f}")
            tipo_fin = st.selectbox("Fuente de Fondos", ["Propios (Contado)", "Bancario", "Crédito Mayorista"])
            tasa = 0.0; plazo = 12; gracia = 0; metodo = "Lineal"
            if tipo_fin == "Bancario":
                tasa = st.number_input("Tasa Interés Anual (%)", 0.0, 100.0, 12.0)
                plazo = st.number_input("Plazo (Meses)", 1, 60, 36)
                metodo = st.selectbox("Amortización", ["Francesa", "Alemana"])
            elif tipo_fin == "Crédito Mayorista":
                tasa = st.number_input("Interés Anual (%)", 0.0, 100.0, 5.0)
                plazo = st.number_input("Plazo Pago (Meses)", 1, 36, 12)
                gracia = st.number_input("Meses de Gracia", 0, 12, 0)
                metodo = "Alemana"
            
            if tipo_fin == "Propios (Contado)":
                df_amort = pd.DataFrame(); cuota_promedio = 0; interes_total = 0
            else:
                df_amort = calcular_amortizacion(monto_total, tasa, plazo, metodo, gracia)
                cuota_promedio = df_amort['Cuota Total'].mean()
                interes_total = df_amort['Interés'].sum()
            
            st.session_state['financiamiento'] = {"Tipo": tipo_fin, "Tabla": df_amort, "Inversión": monto_total if tipo_fin == "Propios (Contado)" else 0, "Interés Total": interes_total, "Plazo": plazo}
        with c2:
            if tipo_fin != "Propios (Contado)":
                m1, m2 = st.columns(2)
                m1.metric("Cuota Promedio", f"${cuota_promedio:,.2f}")
                m2.metric("Costo Fin. Total", f"${interes_total:,.2f}")
                st.plotly_chart(px.bar(df_amort, x="Mes", y=["Capital", "Interés"], title="Flujo de Pagos"), use_container_width=True)

# TAB 4
with tabs[3]:
    st.subheader("📊 Análisis de Costos y Oferta")
    if len(st.session_state['proyecto']) == 0: st.warning("Faltan datos.")
    else:
        df = pd.DataFrame(st.session_state['proyecto'])
        st.markdown("##### 🔎 Desglose de Costos por Modelo")
        resumen_modelos = df.groupby("Modelo").agg({"CPP Unit": "mean", "Manto Unit": "mean", "Cantidad": "sum", "Inversión": "sum"}).reset_index()
        st.dataframe(resumen_modelos.style.format({"CPP Unit": "${:.4f}", "Manto Unit": "${:,.2f}", "Inversión": "${:,.2f}"}), use_container_width=True)
        st.divider()
        vol_total = df['Vol. Total'].sum()
        opex_total = df['OPEX Fijo'].sum() + df['OPEX Var'].sum()
        fin_data = st.session_state.get('financiamiento', {})
        if not fin_data: st.error("Configura Pestaña 3."); st.stop()
        
        costo_fin_mes = df['Inversión'].sum() / 36 if fin_data['Tipo'] == "Propios (Contado)" else fin_data['Tabla']['Cuota Total'].mean()
        costo_total_real = opex_total + costo_fin_mes
        facturacion_meta = costo_total_real / (1 - margen_meta)
        
        precio_unico = facturacion_meta / vol_total if vol_total > 0 else 0
        renta_base = (df['OPEX Fijo'].sum() + costo_fin_mes) / (1 - margen_meta)
        click_var = (df['OPEX Var'].sum() / (1 - margen_meta)) / vol_total if vol_total > 0 else 0
        excedente = precio_unico * 1.15

        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"""<div class="offer-card"><div class="offer-title">A. PRECIO ÚNICO</div><div class="offer-price">${precio_unico:.4f}</div><div class="offer-desc">All-In por hoja</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown(f"""<div class="offer-card"><div class="offer-title">B. HÍBRIDO</div><div class="offer-price">${renta_base:,.2f}</div><div class="offer-desc">Renta Fija + Click ${click_var:.4f}</div></div>""", unsafe_allow_html=True)
        with c3: st.markdown(f"""<div class="offer-card"><div class="offer-title">C. TARIFA PLANA</div><div class="offer-price">${facturacion_meta:,.2f}</div><div class="badge-excess">Exc: ${excedente:.4f}</div></div>""", unsafe_allow_html=True)

# TAB 5
with tabs[4]:
    st.subheader("📈 Proyección Financiera")
    if len(st.session_state['proyecto']) > 0:
        meses_proy = st.slider("Tiempo (Meses)", 12, 60, 36)
        flujo_caja = []
        saldo_acum = 0
        inversion_inicial = fin_data.get('Inversión', 0)
        tabla_amort = fin_data.get('Tabla', pd.DataFrame())
        saldo_acum -= inversion_inicial
        
        for m in range(1, meses_proy + 1):
            ingreso = facturacion_meta
            egreso_opex = opex_total
            egreso_fin = tabla_amort.loc[tabla_amort['Mes'] == m, 'Cuota Total'].values[0] if (not tabla_amort.empty and m <= len(tabla_amort)) else 0
            flujo_neto = ingreso - egreso_opex - egreso_fin
            if m == 1: flujo_neto -= inversion_inicial
            saldo_acum += flujo_neto
            flujo_caja.append({"Mes": m, "Neto": flujo_neto, "Acumulado": saldo_acum})
        
        df_flujo = pd.DataFrame(flujo_caja)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_flujo['Mes'], y=df_flujo['Acumulado'].apply(lambda x: max(x, 0)), fill='tozeroy', mode='none', fillcolor='rgba(16, 185, 129, 0.2)', name='Ganancia'))
        fig2.add_trace(go.Scatter(x=df_flujo['Mes'], y=df_flujo['Acumulado'].apply(lambda x: min(x, 0)), fill='tozeroy', mode='none', fillcolor='rgba(239, 68, 68, 0.2)', name='Recuperación'))
        fig2.add_trace(go.Scatter(x=df_flujo['Mes'], y=df_flujo['Acumulado'], mode='lines', line=dict(color='#0f172a', width=3), name='Flujo'))
        st.plotly_chart(fig2, use_container_width=True)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("VPN (10%)", f"${calcular_vpn_manual(0.10/12, df_flujo['Neto']):,.2f}")
        recup = df_flujo[df_flujo['Acumulado'] >= 0]
        c2.metric("Mes Recuperación", recup.iloc[0]['Mes'] if not recup.empty else "N/A")
        c3.download_button("📥 Excel", data=df_flujo.to_csv(index=False).encode('utf-8'), file_name="proyeccion.csv", mime="text/csv")

# TAB 6
with tabs[5]:
    st.subheader("📦 Stock Mensual")
    if len(st.session_state['proyecto']) > 0:
        df = pd.DataFrame(st.session_state['proyecto'])
        vol_eq = df.groupby("Equipo ID")["Vol. Total"].sum()
        lista_c = []
        for eq_id, vol in vol_eq.items():
            nom = pd.read_sql(f"SELECT modelo FROM equipos WHERE id={eq_id}", conn).iloc[0]['modelo']
            cons = pd.read_sql(f"SELECT tipo, rendimiento FROM consumibles WHERE equipo_id={eq_id}", conn)
            for _, r in cons.iterrows():
                if r['rendimiento'] > 0:
                    lista_c.append({"Equipo": nom, "Item": r['tipo'], "Volumen": f"{vol:,.0f}", "Rendimiento": f"{r['rendimiento']:,.0f}", "Compra Mensual": f"{np.ceil(vol/r['rendimiento']):.0f}"})
        st.dataframe(pd.DataFrame(lista_c), use_container_width=True)
