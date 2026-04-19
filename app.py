import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = 'SISTEMA_TOTAL_REPARADO_2026'

# --- MOTOR DE DATOS (PROTECCIÓN CONTRA ERROR 500) ---
def query_db(db, query, params=(), fetch=False):
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        print(f"Error en {db}: {e}")
        return []

def init_db():
    query_db('master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT, vencimiento TEXT)''')
    query_db('master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ADMIN-01", "CONTROL CENTRAL", "Administrador", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def db_negocio(u):
    db = f"negocio_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"negocio_{u['clave']}.db"
    # Estructura completa de tablas
    query_db(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    
    # Previene el error 500 en CFG asegurando que exista la fila 1
    if not query_db(db, "SELECT * FROM config WHERE id=1", fetch=True):
        query_db(db, "INSERT INTO config (id, empresa, whatsapp) VALUES (1, 'Mi Negocio', '52')")
    return db

# --- ESTILO MODERNO ---
CSS = '''
<style>
    :root { --p: #6366f1; --s: #a855f7; --bg: #0f172a; }
    body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; display: flex; justify-content: center; min-height: 100vh; padding: 20px; }
    .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; width: 100%; max-width: 400px; height: fit-content; }
    h2 { background: linear-gradient(90deg, #22d3ee, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 20px; font-weight: 800; }
    input, select { background: rgba(0,0,0,0.3); border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: linear-gradient(135deg, var(--p), var(--s)); color: white; border: none; padding: 14px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; }
    .nav { display: block; text-decoration: none; color: #94a3b8; padding: 12px; border-radius: 10px; margin-bottom: 8px; background: rgba(255,255,255,0.03); text-align: center; }
    .resumen-corte { background: rgba(0,0,0,0.2); padding: 15px; border-radius: 12px; border-left: 4px solid #22d3ee; margin-bottom: 15px; }
</style>
'''

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>INGRESAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if not res: return redirect('/')
    session['clv'] = res[0]['clave']
    return redirect('/hub')

@app.route('/hub')
def hub():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    conf = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
    
    html = f'{CSS}<div class="card"><h2>{conf["empresa"]}</h2>'
    if u['rango'] == 'Administrador': 
        html += '<a href="/admin" class="nav">💎 Clientes</a>'
    else:
        html += '<a href="/pos" class="nav">🛒 Caja</a>'
        html += '<a href="/stk" class="nav">📦 Inventario</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/cfg" class="nav">⚙️ Configuración</a>'
            html += '<a href="/end" class="nav" style="color:#22d3ee">🏁 Corte de Caja</a>'
    html += '<a href="/" style="color:#f43f5e; text-decoration:none; font-size:12px; display:block; text-align:center; margin-top:10px">Salir</a></div>'
    return html

# --- CONFIGURACIÓN (REPARADO) ---
@app.route('/cfg', methods=['GET', 'POST'])
def cfg():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    if request.method == 'POST':
        query_db(db, "UPDATE config SET empresa=?, whatsapp=? WHERE id=1", (request.form['e'], request.form['w']))
        return redirect('/hub')
    c = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
    return f'''{CSS}<div class="card"><h2>Ajustes</h2>
    <form method="POST">
        <input name="e" value="{c['empresa']}" placeholder="Nombre Negocio">
        <input name="w" value="{c['whatsapp']}" placeholder="WhatsApp (Ej: 521...)">
        <button>GUARDAR</button>
    </form><a href="/hub" class="nav">Volver</a></div>'''

# --- CORTE DE CAJA (REPARADO) ---
@app.route('/end')
def end():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    v_hoy = query_db(db, "SELECT SUM(total) as t FROM ventas", fetch=True)[0]['t'] or 0
    g_hoy = query_db(db, "SELECT SUM(monto) as t FROM gastos", fetch=True)[0]['t'] or 0
    return f'''{CSS}<div class="card"><h2>Corte</h2>
    <div class="resumen-corte">
        <p>Ventas: ${v_hoy}</p><p>Gastos: ${g_hoy}</p><hr><h3>Neto: ${v_hoy - g_hoy}</h3>
    </div>
    <form action="/confirm_end" method="POST"><button style="background:#f43f5e">CERRAR DÍA (BORRAR)</button></form>
    <a href="/hub" class="nav">Volver</a></div>'''

@app.route('/confirm_end', methods=['POST'])
def confirm_end():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    query_db(db, "DELETE FROM ventas"); query_db(db, "DELETE FROM gastos")
    return redirect('/hub')

# --- PUNTO DE VENTA (KILOS POR DINERO) ---
@app.route('/pos')
def pos():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    prods = query_db(db, "SELECT * FROM productos WHERE stock > 0", fetch=True)
    car = session.get('car', [])
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]}/{p["unidad"]})</option>' for p in prods])
    return f'''{CSS}<div class="card"><h2>Venta</h2>
    <form action="/add" method="POST"><select name="id">{ops}</select>
    <input name="v" step="0.01" type="number" placeholder="Dinero ($) o Cantidad (Pza)"><button>Añadir</button></form>
    <h3>Total: ${sum(i['s'] for i in car)}</h3>
    <a href="/pay" class="nav" style="background:var(--p); color:white">COBRAR</a>
    <a href="/hub" class="nav">Volver</a></div>'''

@app.route('/add', methods=['POST'])
def add():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    p = query_db(db, "SELECT * FROM productos WHERE codigo=?", (request.form['id'],), True)[0]
    v = float(request.form['v'] or 0)
    if p['unidad'] == 'Kg':
        cant = round(v / p['precio'], 3); sub = v
    else:
        cant = v; sub = round(v * p['precio'], 2)
    car = session.get('car', []); car.append({'n': p['nombre'], 'c': cant, 's': sub, 'u': p['unidad'], 'id': p['codigo']})
    session['car'] = car
    return redirect('/pos')

@app.route('/pay')
def pay():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    car = session.get('car', [])
    for i in car:
        query_db(db, "UPDATE productos SET stock=stock-? WHERE codigo=?", (i['c'], i['id']))
        query_db(db, "INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
    session['car'] = []; return redirect('/hub')

# --- INVENTARIO ---
@app.route('/stk')
def stk():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    ps = query_db(db, "SELECT * FROM productos", True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>{p['stock']}{p['unidad']}</td></tr>" for p in ps])
    return f'{CSS}<div class="card"><h2>Stock</h2><table>{filas}</table><hr><form action="/p_up" method="POST"><input name="c" placeholder="Código"><input name="n" placeholder="Nombre"><input name="p" placeholder="Precio"><input name="s" placeholder="Stock"><select name="u"><option value="Pza">Pieza</option><option value="Kg">Kilo</option></select><button>Guardar</button></form><a href="/hub" class="nav">Volver</a></div>'

@app.route('/p_up', methods=['POST'])
def p_up():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    query_db(db_negocio(u), "INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['c'], request.form['n'], request.form['p'], request.form['s'], request.form['u']))
    return redirect('/stk')

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
                            
