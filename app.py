import sqlite3
import os
import random
import io
import pandas as pd
import mercadopago
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session, send_file, jsonify

app = Flask(__name__)
app.secret_key = 'SISTEMA_V10_PRO_FINAL_2026'

# --- CONFIGURACIÓN MERCADO PAGO ---
# Prioriza la variable de entorno de Render
MP_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "APP_USR-5698071543918489-041916-eb07a14c4a0b922a085b5e338cc595fe-3346852284")
sdk = mercadopago.SDK(MP_TOKEN)

# --- MOTOR DE DATOS ---
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'sistema_v9.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, params=(), fetch=False):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch:
            res = cursor.fetchall()
            conn.close()
            return res
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error DB: {e}")
        return []

def init_db():
    query_db('CREATE TABLE IF NOT EXISTS usuarios (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, jefe TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, precio REAL, stock REAL, unidad TEXT, dueño TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, detalle TEXT, vendedor TEXT, dueño TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS config (dueño TEXT PRIMARY KEY, empresa TEXT, whatsapp TEXT, estado TEXT, vencimiento TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT, responsable TEXT, dueño TEXT)')
    query_db("INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?)", ('2026', 'Admin Maestro', 'Administrador', 'SISTEMA'))
    query_db("INSERT OR IGNORE INTO config VALUES (?,?,?,?,?)", ('2026', 'CENTRAL POS', '52', 'ACTIVO', '2030-01-01'))

def actualizar_tablas():
    try:
        query_db("ALTER TABLE productos ADD COLUMN stock REAL")
        query_db("ALTER TABLE productos ADD COLUMN unidad TEXT DEFAULT 'PZ'")
    except: pass
    try:
        query_db("ALTER TABLE pagos ADD COLUMN responsable TEXT")
        query_db("ALTER TABLE pagos ADD COLUMN fecha TEXT")
        query_db("ALTER TABLE pagos ADD COLUMN dueño TEXT")
    except: pass

# --- SEGURIDAD Y BLOQUEO AUTOMÁTICO ---
@app.before_request
def verificar_estatus():
    rutas_libres = ['/', '/auth', '/webhook_mp', '/generar_pago', '/health']
    if request.path in rutas_libres or 'static' in request.path:
        return
    
    if 'clv' in session and session['rango'] != 'Administrador':
        conf = query_db("SELECT estado, vencimiento FROM config WHERE dueño=?", (session['dueño'],), True)
        if conf:
            vencimiento = datetime.strptime(conf[0]['vencimiento'], '%Y-%m-%d')
            if datetime.now() > vencimiento or conf[0]['estado'] == 'SUSPENDIDO':
                return f'''
                <style>
                    body {{ background: #0b0f1a; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; }}
                    .card {{ background: rgba(30, 41, 59, 0.7); padding: 30px; border-radius: 20px; text-align: center; border: 1px solid #f43f5e; }}
                </style>
                <div class="card">
                    <h2 style="color:#f43f5e">SERVICIO SUSPENDIDO</h2>
                    <p>La suscripción de <b>{session['dueño']}</b> ha vencido.</p>
                    <a href="/generar_pago" style="display:block; background:#009ee3; color:white; padding:15px; text-decoration:none; border-radius:10px; font-weight:bold; margin-top:10px">💳 RENOVAR CON MERCADO PAGO</a>
                    <a href="/" style="display:block; color:#94a3b8; margin-top:15px; text-decoration:none;">Cerrar Sesión</a>
                </div>'''

# --- MERCADO PAGO: WEBHOOK Y PAGOS ---
@app.route('/health')
def health(): return "OK", 200

@app.route('/webhook_mp', methods=['POST'])
def webhook_mp():
    if request.args.get('type') == 'payment':
        payment_id = request.args.get('data.id')
        payment_info = sdk.payment().get(payment_id)
        if payment_info["response"]["status"] == "approved":
            dueño_id = payment_info["response"]["external_reference"]
            nueva_fecha = (datetime.now() + timedelta(days=31)).strftime('%Y-%m-%d')
            query_db("UPDATE config SET estado='ACTIVO', vencimiento=? WHERE dueño=?", (nueva_fecha, dueño_id))
    return jsonify({"status": "ok"}), 200

@app.route('/generar_pago')
def generar_pago():
    if 'clv' not in session: return redirect('/')
    preference_data = {
        "items": [{"title": "Mensualidad Sistema POS", "quantity": 1, "unit_price": 450.00, "currency_id": "MXN"}],
        "external_reference": session['dueño'],
        "notification_url": f"https://{request.host}/webhook_mp",
        "back_urls": {"success": f"https://{request.host}/hub"}
    }
    res = sdk.preference().create(preference_data)
    return redirect(res["response"]["init_point"])

# --- RUTAS DE NAVEGACIÓN ---
@app.route('/')
def login():
    session.clear()
    return '''
    <style>
        body { background: #0b0f1a; color: white; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }
        .card { background: rgba(30, 41, 59, 0.7); padding: 25px; border-radius: 20px; width: 300px; border: 1px solid rgba(255,255,255,0.1); }
        input { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; box-sizing: border-box; }
        button { background: linear-gradient(to right, #00f2fe, #4facfe); color: #0b0f1a; border: none; padding: 15px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; }
    </style>
    <div class="card">
        <h2 style="text-align:center">Acceso V10</h2>
        <form action="/auth" method="POST">
            <input name="c" type="password" placeholder="Clave Operativa" required autofocus>
            <button>INGRESAR</button>
        </form>
    </div>'''

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db("SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if res:
        session['clv'], session['user'], session['rango'] = res[0]['clave'], res[0]['nombre'], res[0]['rango']
        session['dueño'] = res[0]['jefe'] if res[0]['rango'] == 'Trabajador' else res[0]['clave']
        return redirect('/hub')
    return redirect('/')

@app.route('/hub')
def hub():
    if 'clv' not in session: return redirect('/')
    conf = query_db("SELECT empresa FROM config WHERE dueño=?", (session['dueño'],), True)
    empresa = conf[0]['empresa'] if conf else "SISTEMA"
    
    html = f'''
    <style>
        body {{ background: #0b0f1a; color: white; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.7); padding: 25px; border-radius: 20px; width: 350px; border: 1px solid rgba(255,255,255,0.1); text-align: center; }}
        .btn-nav {{ text-decoration: none; color: white; display: block; padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); margin-top: 10px; font-weight: bold; }}
    </style>
    <div class="card">
        <small style="background:#00f2fe; color:black; padding:2px 8px; border-radius:5px; font-weight:bold;">{session['rango']}</small>
        <h2>{empresa}</h2>'''
    
    if session['rango'] in ['Trabajador', 'Dueño']:
        html += '<a href="/pos" class="btn-nav" style="background:#00f2fe; color:black;">🛒 VENTAS / CAJA</a>'
        html += '<a href="/proveedores" class="btn-nav">🚚 PAGO A PROVEEDORES</a>'
        html += '<a href="/inventario" class="btn-nav">📦 INVENTARIO</a>'
    
    if session['rango'] == 'Dueño':
        html += '<a href="/corte" class="btn-nav">📊 CORTE DE CAJA</a>'
        
    html += '<a href="/" class="btn-nav" style="color:#f43f5e; margin-top:20px;">Cerrar Sesión</a></div>'
    return html

@app.route('/pos')
def pos():
    prods = query_db("SELECT * FROM productos WHERE dueño=?", (session['dueño'],), True)
    carro = session.get('carro', [])
    total = sum(i['s'] for i in carro)
    
    l_bus = "".join([f'<div style="padding:10px; border-bottom:1px solid #333; cursor:pointer" onclick="document.getElementById(\'pid\').value=\'{p["id"]}\'; document.getElementById(\'q\').value=\'{p["nombre"]}\';">{p["nombre"]} - ${p["precio"]}</div>' for p in prods])
    
    return f'''
    <style>
        body {{ background: #0b0f1a; color: white; font-family: sans-serif; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.7); padding: 20px; border-radius: 20px; max-width: 400px; margin: auto; }}
        input {{ width: 100%; padding: 10px; margin: 5px 0; box-sizing: border-box; }}
        button {{ width: 100%; padding: 15px; background: #00f2fe; border: none; font-weight: bold; border-radius: 10px; }}
    </style>
    <div class="card">
        <h2>Caja</h2>
        <div id="lista-carro">
            {"".join([f"<p>{i['n']} - ${i['s']}</p>" for i in carro])}
        </div>
        <h3>Total: ${total}</h3>
        <form action="/pagar" method="POST">
            <input name="tel" placeholder="WhatsApp Cliente" required>
            <button>FINALIZAR VENTA</button>
        </form>
        <hr>
        <input id="q" placeholder="Buscar producto...">
        <div style="background:#1e293b; max-height:150px; overflow-y:auto;">{l_bus}</div>
        <form action="/add_carro" method="POST" style="margin-top:10px">
            <input type="hidden" name="id" id="pid">
            <input name="val" type="number" step="0.01" placeholder="Cantidad" required>
            <button style="background:#4facfe">+</button>
        </form>
        <a href="/hub" style="color:white; display:block; text-align:center; margin-top:15px;">Volver</a>
    </div>'''

@app.route('/add_carro', methods=['POST'])
def add_carro():
    p = query_db("SELECT * FROM productos WHERE id=?", (request.form['id'],), True)[0]
    val = float(request.form['val'])
    sub = val if p['unidad'] == 'Kg' else round(val * p['precio'], 2)
    carro = session.get('carro', [])
    carro.append({'id': p['id'], 'n': p['nombre'], 'c': val/p['precio'] if p['unidad']=='Kg' else val, 's': sub})
    session['carro'] = carro
    return redirect('/pos')

@app.route('/pagar', methods=['POST'])
def pagar():
    carro = session.get('carro', [])
    if not carro: return redirect('/pos')
    conf = query_db("SELECT empresa FROM config WHERE dueño=?", (session['dueño'],), True)
    empresa = conf[0]['empresa'] if conf else "NEGOCIO"
    total = sum(i['s'] for i in carro)
    
    ticket_prod = ""
    for i in carro:
        query_db("UPDATE productos SET stock = stock - ? WHERE id = ? AND stock IS NOT NULL", (i['c'], i['id']))
        query_db("INSERT INTO ventas (total, fecha, detalle, vendedor, dueño) VALUES (?,?,?,?,?)", 
                 (i['s'], datetime.now().strftime("%H:%M"), i['n'], session['user'], session['dueño']))
        ticket_prod += f"• {i['n']} ({i['c']}) ${i['s']}%0A"
    
    mensaje = f"🧾 *TICKET DE VENTA*%0A🏪 *{empresa.upper()}*%0A👤 Atendió: {session['user']}%0A{ticket_prod}💰 *TOTAL: ${total}*"
    session['carro'] = []
    return redirect(f"https://api.whatsapp.com/send?phone={request.form['tel']}&text={mensaje}")

@app.route('/corte')
def corte():
    v_l = query_db("SELECT * FROM ventas WHERE dueño=? ORDER BY id DESC", (session['dueño'],), True)
    p_l = query_db("SELECT * FROM pagos WHERE dueño=? ORDER BY id DESC", (session['dueño'],), True)
    t_v, t_p = sum(v['total'] for v in v_l), sum(p['monto'] for p in p_l)
    return f'''
    <body style="background:#0b0f1a; color:white; font-family:sans-serif; text-align:center; padding:20px;">
        <div style="background:rgba(30,41,59,0.7); padding:20px; border-radius:20px; display:inline-block;">
            <h2>Corte de Caja</h2>
            <h1 style="color:#00f2fe">${t_v - t_p}</h1>
            <a href="/exportar_excel" style="background:#1d6f42; color:white; padding:15px; display:block; border-radius:10px; text-decoration:none; font-weight:bold;">📑 DESCARGAR EXCEL</a>
            <a href="/hub" style="color:white; display:block; margin-top:20px;">Volver</a>
        </div>
    </body>'''

@app.route('/exportar_excel')
def exportar_excel():
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT id as 'TICKET', fecha as HORA, vendedor as 'RESPONSABLE', detalle as 'CONCEPTO', total as 'ENTRADA (+)', 0.0 as 'SALIDA (-)' FROM ventas WHERE dueño=?", conn, params=(session['dueño'],))
    df_p = pd.read_sql_query("SELECT id as 'TICKET', fecha as HORA, responsable as 'RESPONSABLE', concepto as 'CONCEPTO', 0.0 as 'ENTRADA (+)', monto as 'SALIDA (-)' FROM pagos WHERE dueño=?", conn, params=(session['dueño'],))
    df_final = pd.concat([df_v, df_p]).sort_values(by='HORA')
    
    query_db("DELETE FROM ventas WHERE dueño=?", (session['dueño'],))
    query_db("DELETE FROM pagos WHERE dueño=?", (session['dueño'],))
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Caja')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name="corte.xlsx")

@app.route('/inventario')
def inventario():
    prods = query_db("SELECT * FROM productos WHERE dueño = ?", (session['dueño'],), True)
    html = '<h2>Inventario</h2><form action="/agregar_producto" method="post"><input name="nombre" placeholder="Producto"><input name="precio" type="number" step="0.01" placeholder="Precio"><input name="stock" type="number" step="0.1" placeholder="Stock"><select name="unidad"><option value="PZ">PZ</option><option value="KG">KG</option></select><button>Guardar</button></form>'
    for p in prods:
        html += f'<p>{p["nombre"]} - ${p["precio"]} ({p["stock"]} {p["unidad"]}) <a href="/eliminar_producto/{p["id"]}">🗑️</a></p>'
    return html + '<a href="/hub">Volver</a>'

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    query_db("INSERT INTO productos (nombre, precio, stock, unidad, dueño) VALUES (?,?,?,?,?)", 
             (request.form['nombre'].upper(), request.form['precio'], request.form['stock'], request.form['unidad'], session['dueño']))
    return redirect('/inventario')

@app.route('/eliminar_producto/<int:id>')
def eliminar_producto(id):
    query_db("DELETE FROM productos WHERE id=? AND dueño=?", (id, session['dueño']))
    return redirect('/inventario')

@app.route('/proveedores')
def proveedores():
    pagos = query_db("SELECT * FROM pagos WHERE dueño = ?", (session['dueño'],), True)
    html = '<h2>Gastos</h2><form action="/registrar_pago" method="post"><input name="con" placeholder="Concepto"><input name="mon" type="number" step="0.01" placeholder="Monto"><button>Registrar</button></form>'
    for pg in pagos:
        html += f'<p>{pg["concepto"]} - ${pg["monto"]}</p>'
    return html + '<a href="/hub">Volver</a>'

@app.route('/registrar_pago', methods=['POST'])
def registrar_pago():
    query_db("INSERT INTO pagos (concepto, monto, responsable, dueño, fecha) VALUES (?,?,?,?,?)", 
             (request.form['con'].upper(), request.form['mon'], session['user'], session['dueño'], datetime.now().strftime("%H:%M")))
    return redirect('/proveedores')

if __name__ == '__main__':
    init_db()
    actualizar_tablas()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
        
