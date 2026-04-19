import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session, render_template_string

app = Flask(__name__)
app.secret_key = 'SISTEMA_UNIFICADO_IRROMPIBLE_2026'

# ==========================================
# 1. MOTOR DE DATOS Y SEGURIDAD
# ==========================================

def query_db(db, query, params=(), fetch=False):
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        print(f"Error DB: {e}")
        return []

def init_db():
    # Base Maestra (Rentas y Jerarquías)
    query_db('master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, 
                creado_por TEXT, estado TEXT, vencimiento TEXT)''')
    query_db('master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ADMIN-01", "CONTROL CENTRAL", "Administrador", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def db_negocio(u):
    db = f"negocio_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"negocio_{u['clave']}.db"
    query_db(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    if not query_db(db, "SELECT * FROM config", fetch=True):
        query_db(db, "INSERT INTO config (id, empresa, whatsapp) VALUES (1, 'Mi Negocio', '521')")
    return db

# ==========================================
# 2. DISEÑO GLASSMORPHISM
# ==========================================

CSS = '''
<style>
    :root { --p: #6366f1; --s: #a855f7; --bg: #0f172a; }
    body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; display: flex; justify-content: center; min-height: 100vh; padding: 20px; }
    .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; width: 100%; max-width: 400px; height: fit-content; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
    h2 { background: linear-gradient(90deg, #22d3ee, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 20px; }
    input, select { background: rgba(0,0,0,0.3); border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: linear-gradient(135deg, var(--p), var(--s)); color: white; border: none; padding: 14px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; }
    .nav { display: block; text-decoration: none; color: #94a3b8; padding: 12px; border-radius: 10px; margin-bottom: 8px; background: rgba(255,255,255,0.03); border: 1px solid transparent; text-align: center; }
    .nav:hover { border-color: #22d3ee; color: #22d3ee; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; }
</style>
'''

# ==========================================
# 3. RUTAS DE ACCESO Y RENTA
# ==========================================

@app.route('/')
def home():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>INGRESAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if not res: return redirect('/')
    u = res[0]
    
    # VALIDACIÓN DE RENTA (CASCADA)
    v_str = u['vencimiento']
    if u['rango'] == 'Trabajador':
        jefe = query_db('master.db', "SELECT vencimiento FROM usuarios WHERE clave=?", (u['creado_por'],), True)[0]
        v_str = jefe['vencimiento']
    
    if datetime.now() > datetime.strptime(v_str, "%Y-%m-%d %H:%M:%S"):
        return f'{CSS}<div class="card"><h2 style="color:#f43f5e">Servicio Suspendido</h2><p>Contacte al Administrador por falta de pago.</p><a href="/" class="nav">Volver</a></div>'

    session['clv'] = u['clave']
    return redirect('/hub')

@app.route('/hub')
def hub():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    conf = query_db(db, "SELECT * FROM config", fetch=True)[0]
    
    html = f'{CSS}<div class="card"><h2>{conf["empresa"]}</h2><p style="color:#64748b; font-size:12px">{u["nombre"]} | {u["rango"]}</p>'
    if u['rango'] == 'Administrador':
        html += '<a href="/admin_duenos" class="nav">💎 Gestionar Clientes</a>'
    elif u['rango'] in ['Dueño', 'Trabajador']:
        html += '<a href="/pos" class="nav">🛒 Punto de Venta</a>'
        html += '<a href="/stk" class="nav">📦 Inventario</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/personal" class="nav">👥 Empleados</a>'
            html += '<a href="/cfg" class="nav">⚙️ Configuración</a>'
            html += '<a href="/end" class="nav" style="color:#22d3ee">🏁 Corte de Caja</a>'
    html += '<hr style="opacity:0.1"><a href="/" style="color:#f43f5e; font-size:12px; text-decoration:none">Cerrar Sesión</a></div>'
    return html

# ==========================================
# 4. PUNTO DE VENTA Y WHATSAPP
# ==========================================

@app.route('/pos')
def pos():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    prods = query_db(db, "SELECT * FROM productos WHERE stock > 0", fetch=True)
    car = session.get('car', [])
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]})</option>' for p in prods])
    filas = "".join([f'<tr><td>{i["n"]}</td><td>{i["c"]}</td><td>${i["s"]}</td></tr>' for i in car])
    return f'''{CSS}<div class="card"><h2>Venta</h2>
    <form action="/add" method="POST"><select name="id">{ops}</select><input name="q" type="number" step="0.1" placeholder="Cantidad"><button>Añadir</button></form>
    <table><tr><th>Ítem</th><th>Cant</th><th>Sub</th></tr>{filas}</table>
    <h3 style="text-align:right">Total: ${sum(i['s'] for i in car)}</h3>
    <a href="/pay" class="nav" style="background:var(--p); color:white">COBRAR Y TICKET</a>
    <a href="/hub" class="nav">Volver</a></div>'''

@app.route('/add', methods=['POST'])
def add():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    p = query_db(db_negocio(u), "SELECT * FROM productos WHERE codigo=?", (request.form['id'],), True)[0]
    q = float(request.form['q'] or 1)
    car = session.get('car', [])
    car.append({'id': p['codigo'], 'n': p['nombre'], 'c': q, 's': round(p['precio']*q, 2)})
    session['car'] = car
    return redirect('/pos')

@app.route('/pay')
def pay():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    car = session.get('car', [])
    if not car: return redirect('/pos')
    ticket = f"🧾 *{u['nombre']}*\n---\n"
    total = sum(i['s'] for i in car)
    for i in car:
        query_db(db, "UPDATE productos SET stock=stock-? WHERE codigo=?", (i['c'], i['id']))
        query_db(db, "INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
        ticket += f"• {i['n']} x{i['c']} = ${i['s']}\n"
    conf = query_db(db, "SELECT whatsapp FROM config", True)[0]
    session['car'] = []
    url = f"https://api.whatsapp.com/send?phone={conf['whatsapp']}&text={urllib.parse.quote(ticket + f'---\n*TOTAL: ${total}*')}"
    return f"{CSS}<div class='card'><h2>Cobrado</h2><a href='{url}' target='_blank' class='nav' style='background:#22c55e; color:white'>Enviar WhatsApp</a><a href='/pos' class='nav'>Nueva Venta</a></div>"

# ==========================================
# 5. GESTIÓN DE RENTAS Y EMPLEADOS
# ==========================================

@app.route('/admin_duenos')
def admin_duenos():
    clientes = query_db('master.db', "SELECT * FROM usuarios WHERE rango='Dueño'", fetch=True)
    filas = "".join([f"<tr><td>{c['nombre']}</td><td>{c['clave']}</td><td>{c['vencimiento'][:10]}</td></tr>" for c in clientes])
    return f'''{CSS}<div class="card" style="max-width:500px"><h2>Rentas</h2>
    <table><tr><th>Dueño</th><th>Clave</th><th>Vence</th></tr>{filas}</table><hr>
    <form action="/new_owner" method="POST"><input name="n" placeholder="Nombre Negocio"><button>Crear Dueño (30 días)</button></form>
    <a href="/hub" class="nav">Volver</a></div>'''

@app.route('/new_owner', methods=['POST'])
def new_owner():
    clv = f"DUE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    v = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    query_db('master.db', "INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (clv, request.form['n'], 'Dueño', session['clv'], 'Activo', v))
    return redirect('/admin_duenos')

@app.route('/personal')
def personal():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    ems = query_db('master.db', "SELECT * FROM usuarios WHERE creado_por=?", (u['clave'],), fetch=True)
    filas = "".join([f"<tr><td>{e['nombre']}</td><td>{e['clave']}</td></tr>" for e in ems])
    return f'''{CSS}<div class="card"><h2>Empleados</h2>
    <table><tr><th>Nombre</th><th>Clave</th></tr>{filas}</table><hr>
    <form action="/new_emp" method="POST"><input name="n" placeholder="Nombre Empleado"><button>Crear Acceso</button></form>
    <a href="/hub" class="nav">Volver</a></div>'''

@app.route('/new_emp', methods=['POST'])
def new_emp():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    clv = f"TRB-{''.join(random.choices(string.digits, k=4))}"
    query_db('master.db', "INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (clv, request.form['n'], 'Trabajador', u['clave'], 'Activo', u['vencimiento']))
    return redirect('/personal')

@app.route('/stk')
def stk():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    ps = query_db(db, "SELECT * FROM productos", True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>" for p in ps])
    form = f'<hr><form action="/p_up" method="POST"><input name="c" placeholder="Código"><input name="n" placeholder="Nombre"><input name="p" placeholder="Precio"><input name="s" placeholder="Stock"><button>Guardar</button></form>' if u['rango'] == 'Dueño' else ""
    return f'{CSS}<div class="card"><h2>Stock</h2><table>{filas}</table>{form}<a href="/hub" class="nav">Volver</a></div>'

@app.route('/p_up', methods=['POST'])
def p_up():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    query_db(db_negocio(u), "INSERT OR REPLACE INTO productos VALUES (?,?,?,?)", (request.form['c'], request.form['n'], request.form['p'], request.form['s']))
    return redirect('/stk')

@app.route('/cfg', methods=['GET', 'POST'])
def cfg():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    if request.method == 'POST':
        query_db(db, "UPDATE config SET empresa=?, whatsapp=? WHERE id=1", (request.form['e'], request.form['w']))
        return redirect('/hub')
    c = query_db(db, "SELECT * FROM config", True)[0]
    return f'{CSS}<div class="card"><h2>Ajustes</h2><form method="POST"><input name="e" value="{c["empresa"]}"><input name="w" value="{c["whatsapp"]}"><button>Guardar</button></form><a href="/hub" class="nav">Volver</a></div>'

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
    
