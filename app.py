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
    
    # Parche de seguridad para columnas nuevas
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for tabla, col, tipo in [('productos','stock','REAL'), ('productos','unidad','TEXT DEFAULT "PZ"'), ('pagos','responsable','TEXT'), ('pagos','dueño','TEXT')]:
            try: cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
            except: pass
        conn.commit()

    query_db("INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?)", ('2026', 'Admin Maestro', 'Administrador', 'SISTEMA'))
    query_db("INSERT OR IGNORE INTO config VALUES (?,?,?,?,?)", ('2026', 'CENTRAL POS', '52', 'ACTIVO', '2030-01-01'))

# --- ESTILOS CSS (GLASSMORPHISM) ---
CSS = '''
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    :root { --accent: #00f2fe; --bg: #0b0f1a; --glass: rgba(30, 41, 59, 0.7); --border: rgba(255, 255, 255, 0.1); }
    body { background: #0b0f1a; color: white; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; min-height: 100vh; margin:0; }
    .card { background: var(--glass); backdrop-filter: blur(12px); border-radius: 20px; padding: 25px; width: 90%; max-width: 400px; border: 1px solid var(--border); margin-bottom: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; }
    h2 { background: linear-gradient(to right, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; margin-top:0; }
    input, select { background: rgba(0,0,0,0.3); border: 1px solid var(--border); color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; box-sizing: border-box; outline: none; }
    button { background: linear-gradient(to right, #00f2fe, #4facfe); color: #0b0f1a; border: none; padding: 15px; width: 100%; border-radius: 10px; font-weight: 800; cursor: pointer; transition: 0.3s; margin-top:10px; }
    button:hover { opacity: 0.8; transform: scale(0.98); }
    .btn-nav { text-decoration: none; color: #94a3b8; display: block; text-align: center; padding: 12px; border-radius: 10px; border: 1px solid var(--border); margin-top: 10px; font-size: 14px; font-weight: 600; }
    table { width: 100%; font-size: 13px; border-collapse: collapse; margin-top: 10px; }
    td { padding: 10px 5px; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: left; }
    .badge { background: var(--accent); color: black; padding: 3px 8px; border-radius: 5px; font-size: 10px; font-weight: 800; text-transform: uppercase; margin-bottom:10px; display:inline-block; }
</style>
'''

# --- SEGURIDAD Y BLOQUEO ---
@app.before_request
def verificar_estatus():
    rutas_libres = ['/', '/auth', '/webhook_mp', '/generar_pago', '/health']
    if request.path in rutas_libres or 'static' in request.path: return
    if 'clv' not in session: return redirect('/')
    if session['rango'] != 'Administrador':
        conf = query_db("SELECT estado, vencimiento FROM config WHERE dueño=?", (session['dueño'],), True)
        if conf:
            venc = datetime.strptime(conf[0]['vencimiento'], '%Y-%m-%d')
            if datetime.now() > venc or conf[0]['estado'] == 'SUSPENDIDO':
                return f'{CSS}<div class="card"><h2 style="color:#f43f5e">SERVICIO SUSPENDIDO</h2><p>Venció: {conf[0]["vencimiento"]}</p><a href="/generar_pago" class="btn-nav" style="background:#009ee3; color:white">💳 RENOVAR</a><a href="/" class="btn-nav">Cerrar Sesión</a></div>'

# --- RUTAS DE ACCESO ---
@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso V10</h2><form action="/auth" method="POST"><input name="c" type="password" placeholder="Clave Operativa" required autofocus><button>INGRESAR</button></form></div>'

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
    empresa = conf[0]['empresa'] if conf else "MI NEGOCIO"
    html = f'{CSS}<div class="card"><span class="badge">{session["rango"]}</span><h2>{empresa}</h2>'
    if session['rango'] in ['Trabajador', 'Dueño']:
        html += '<a href="/pos" class="btn-nav" style="background:var(--accent); color:black; font-weight:800">🛒 VENTAS / CAJA</a>'
        html += '<a href="/proveedores" class="btn-nav">🚚 PAGO A PROVEEDORES</a>'
        html += '<a href="/inventario" class="btn-nav">📦 INVENTARIO</a>'
    if session['rango'] == 'Dueño':
        html += '<hr style="opacity:0.1; margin:20px 0"><a href="/corte" class="btn-nav">📊 CORTE DE CAJA</a><a href="/gestion_personal" class="btn-nav">👥 GESTIÓN DE PERSONAL</a><a href="/ajustes" class="btn-nav">⚙️ CONFIGURACIÓN</a>'
    if session['rango'] == 'Administrador':
        html += '<a href="/gestion_dueños" class="btn-nav" style="background:#f59e0b; color:black">🏢 PANEL DE CONTROL</a>'
    html += '<a href="/" class="btn-nav" style="color:#f43f5e; margin-top:30px">Cerrar Sesión</a></div>'
    return html

# --- VENTAS (POS) ---
@app.route('/pos')
def pos():
    prods = query_db("SELECT * FROM productos WHERE dueño=?", (session['dueño'],), True)
    carro = session.get('carro', [])
    total = sum(i['s'] for i in carro)
    l_bus = "".join([f'<div style="padding:12px; border-bottom:1px solid var(--border); cursor:pointer" onclick="document.getElementById(\'pid\').value=\'{p["id"]}\'; document.getElementById(\'q\').value=\'{p["nombre"]}\'; this.parentElement.style.display=\'none\'">{p["nombre"]} - ${p["precio"]}</div>' for p in prods])
    return f'''{CSS}<div class="card"><h2>Terminal</h2><table>{"".join([f"<tr><td>{i['n']}</td><td style='text-align:right'>${i['s']}</td></tr>" for i in carro])}</table>
        <div style="background:rgba(0,242,254,0.1); padding:15px; border-radius:15px; margin:15px 0"><h2>${total}</h2></div>
        <form action="/pagar" method="POST"><input name="tel" placeholder="WhatsApp Cliente" required><button>COBRAR</button></form>
        <div style="margin-top:20px"><input id="q" onkeyup="this.nextElementSibling.style.display='block'" placeholder="🔍 Buscar...">
        <div style="display:none; background:#1e293b; position:absolute; width:85%; z-index:10; border:1px solid var(--accent); max-height:200px; overflow-y:auto">{l_bus}</div>
        <form action="/add_carro" method="POST" style="display:flex; gap:10px; margin-top:10px"><input type="hidden" name="id" id="pid"><input name="val" type="number" step="0.01" placeholder="Cant" required><button style="width:60px">+</button></form></div>
        <a href="/hub" class="btn-nav">Menú</a></div>'''

@app.route('/add_carro', methods=['POST'])
def add_carro():
    p = query_db("SELECT * FROM productos WHERE id=?", (request.form['id'],), True)[0]
    val = float(request.form['val'])
    sub = val if p['unidad'] == 'KG' else round(val * p['precio'], 2)
    carro = session.get('carro', []); carro.append({'id': p['id'], 'n': p['nombre'], 'c': val/p['precio'] if p['unidad']=='KG' else val, 's': sub})
    session['carro'] = carro
    return redirect('/pos')

@app.route('/pagar', methods=['POST'])
def pagar():
    carro = session.get('carro', [])
    if not carro: return redirect('/pos')
    for i in carro:
        query_db("UPDATE productos SET stock = stock - ? WHERE id = ? AND stock IS NOT NULL", (i['c'], i['id']))
        query_db("INSERT INTO ventas (total, fecha, detalle, vendedor, dueño) VALUES (?,?,?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), i['n'], session['user'], session['dueño']))
    session['carro'] = []; return redirect('/pos')

# --- INVENTARIO ---
@app.route('/inventario')
def inventario():
    prods = query_db("SELECT * FROM productos WHERE dueño = ?", (session['dueño'],), True)
    html = f'''{CSS}<div class="card"><h2>Inventario</h2><form action="/agregar_producto" method="post">
        <input name="nombre" placeholder="PRODUCTO" required style="text-transform:uppercase;">
        <input name="precio" type="number" step="0.01" placeholder="PRECIO $" required>
        <input name="stock" type="number" step="0.1" placeholder="STOCK"><select name="unidad"><option value="PZ">PIEZA</option><option value="KG">KILO</option></select>
        <button>GUARDAR</button></form><hr style="opacity:0.1; margin:20px 0">'''
    for p in prods:
        html += f'<div style="text-align:left; border-bottom:1px solid #333; padding:10px; display:flex; justify-content:space-between"><span>{p["nombre"]} (${p["precio"]})<br><small style="color:var(--accent)">Stock: {p["stock"]} {p["unidad"]}</small></span><a href="/eliminar_producto/{p["id"]}" style="color:#f43f5e">🗑️</a></div>'
    return html + '<a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    query_db("INSERT INTO productos (nombre, precio, stock, unidad, dueño) VALUES (?,?,?,?,?)", 
             (request.form['nombre'].upper(), request.form['precio'], request.form['stock'], request.form['unidad'], session['dueño']))
    return redirect('/inventario')

@app.route('/eliminar_producto/<int:id>')
def eliminar_producto(id):
    query_db("DELETE FROM productos WHERE id=? AND dueño=?", (id, session['dueño']))
    return redirect('/inventario')

# --- GASTOS ---
@app.route('/proveedores')
def proveedores():
    pagos = query_db("SELECT * FROM pagos WHERE dueño = ?", (session['dueño'],), True)
    html = f'''{CSS}<div class="card"><h2>Gastos</h2><form action="/registrar_pago" method="post">
        <input name="concepto" placeholder="CONCEPTO" required style="text-transform:uppercase;">
        <input name="monto" type="number" step="0.01" placeholder="MONTO $" required><button>REGISTRAR</button></form><hr style="opacity:0.1; margin:20px 0">'''
    for pg in pagos:
        html += f'<div style="text-align:left; padding:8px; border-bottom:1px solid #333"><span>{pg["concepto"]}</span><b style="float:right; color:#f43f5e">-${pg["monto"]}</b></div>'
    return html + '<a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/registrar_pago', methods=['POST'])
def registrar_pago():
    query_db("INSERT INTO pagos (concepto, monto, responsable, dueño, fecha) VALUES (?,?,?,?,?)", 
             (request.form['concepto'].upper(), request.form['monto'], session['user'], session['dueño'], datetime.now().strftime("%H:%M")))
    return redirect('/proveedores')

# --- CORTE Y EXCEL ---
@app.route('/corte')
def corte():
    v = query_db("SELECT * FROM ventas WHERE dueño=?", (session['dueño'],), True)
    p = query_db("SELECT * FROM pagos WHERE dueño=?", (session['dueño'],), True)
    t_v, t_p = sum(i['total'] for i in v), sum(i['monto'] for i in p)
    return f'''{CSS}<div class="card"><h2>Corte</h2><div style="background:rgba(34,197,94,0.1); padding:20px; border-radius:20px; border:1px solid #22c55e">
        <small>NETO</small><h1>${t_v - t_p}</h1><p style="font-size:12px">Ventas: ${t_v} | Gastos: ${t_p}</p></div>
        <a href="/exportar_excel" class="btn-nav" style="background:#1d6f42; color:white; border:none">📑 EXPORTAR EXCEL</a>
        <a href="/hub" class="btn-nav">Volver</a></div>'''

@app.route('/exportar_excel')
def exportar_excel():
    conn = get_db_connection()
    df_v = pd.read_sql_query("SELECT id, fecha, vendedor, detalle, total as monto, 'VENTA' as tipo FROM ventas WHERE dueño=?", conn, params=(session['dueño'],))
    df_p = pd.read_sql_query("SELECT id, fecha, responsable, concepto, monto, 'GASTO' as tipo FROM pagos WHERE dueño=?", conn, params=(session['dueño'],))
    df = pd.concat([df_v, df_p])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False)
    output.seek(0); return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name="corte.xlsx")

# --- PERSONAL ---
@app.route('/gestion_personal')
def gestion_personal():
    pers = query_db("SELECT * FROM usuarios WHERE jefe = ? AND rango = 'Trabajador'", (session['dueño'],), True)
    html = f'''{CSS}<div class="card"><h2>Personal</h2><form action="/crear_trabajador" method="post">
        <input name="nombre" placeholder="NOMBRE" required style="text-transform:uppercase;">
        <input name="pin" placeholder="PIN" required><button>CREAR ACCESO</button></form><hr style="opacity:0.1; margin:20px 0">'''
    for p in pers:
        html += f'<div style="text-align:left; padding:10px; border-bottom:1px solid #333">👤 {p["nombre"]} - PIN: {p["clave"]}</div>'
    return html + '<a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/crear_trabajador', methods=['POST'])
def crear_trabajador():
    query_db("INSERT INTO usuarios (clave, nombre, rango, jefe) VALUES (?, ?, 'Trabajador', ?)", (request.form['pin'], request.form['nombre'].upper(), session['dueño']))
    return redirect('/gestion_personal')

# --- PANEL ADMINISTRADOR ---
@app.route('/gestion_dueños')
def gestion_dueños():
    if session['rango'] != 'Administrador': return redirect('/')
    dues = query_db("SELECT * FROM config", fetch=True)
    html = f'{CSS}<div class="card"><h2>Dueños</h2>'
    for d in dues:
        html += f'<div style="text-align:left; padding:10px; border-bottom:1px solid #333">🏢 {d["empresa"]}<br><small>{d["dueño"]} - {d["estado"]}</small></div>'
    return html + '<a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/ajustes')
def ajustes():
    c = query_db("SELECT * FROM config WHERE dueño=?", (session['dueño'],), True)
    emp = c[0]['empresa'] if c else ""
    return f'{CSS}<div class="card"><h2>Ajustes</h2><form action="/guardar_ajustes" method="POST"><input name="emp" value="{emp}"><button>GUARDAR</button></form><a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/guardar_ajustes', methods=['POST'])
def guardar_ajustes():
    query_db("UPDATE config SET empresa=? WHERE dueño=?", (request.form['emp'].upper(), session['dueño']))
    return redirect('/hub')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
