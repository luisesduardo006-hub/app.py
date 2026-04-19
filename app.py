import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = 'sistema_tres_niveles_blindado_2026'

# ==========================================
# MOTOR DE DATOS (ARQUITECTURA DE 3 NIVELES)
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
        print(f"Error: {e}")
        return []

def init_db():
    # Base Maestra: Administrador -> Dueño -> Trabajador
    query_db('master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, 
                creado_por TEXT, estado TEXT, vencimiento TEXT)''')
    
    # El Administrador es el rango máximo ahora
    query_db('master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ADMIN-01", "CONTROL CENTRAL", "Administrador", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def get_db_path(u):
    # Si es trabajador, usa la DB de quien lo creó (el Dueño)
    return f"negocio_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"negocio_{u['clave']}.db"

def init_negocio(db):
    query_db(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, total REAL, fecha TEXT, vendedor TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY, concepto TEXT, monto REAL, fecha TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    if not query_db(db, "SELECT * FROM config", fetch=True):
        query_db(db, "INSERT INTO config (id, empresa, whatsapp) VALUES (1, 'Mi Negocio', '')")

# ==========================================
# DISEÑO Y ESTILO
# ==========================================

CSS = '''
<style>
    :root { --p: #4f46e5; --s: #9333ea; --bg: #020617; }
    body { background: var(--bg); color: #f8fafc; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
    .glass { background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; padding: 30px; width: 90%; max-width: 420px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }
    h2 { background: linear-gradient(to right, #38bdf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 0; }
    input, select { background: rgba(0,0,0,0.3); border: 1px solid #334155; color: white; padding: 14px; width: 100%; border-radius: 12px; margin-bottom: 12px; font-size: 16px; }
    button { background: linear-gradient(135deg, var(--p), var(--s)); color: white; border: none; padding: 16px; width: 100%; border-radius: 12px; font-weight: bold; cursor: pointer; }
    .nav-link { display: block; text-decoration: none; color: #94a3b8; padding: 12px; border-radius: 10px; margin-bottom: 8px; background: rgba(255,255,255,0.03); border: 1px solid transparent; }
    .nav-link:hover { border-color: #38bdf8; color: #38bdf8; }
    .expired { border: 2px solid #ef4444; color: #ef4444; padding: 15px; border-radius: 12px; text-align: center; }
</style>
'''

# ==========================================
# LOGICA DE RUTAS
# ==========================================

@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="glass"><h2>Acceso</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>ENTRAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    clv = request.form.get('c')
    res = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (clv,), True)
    if not res: return redirect('/')
    
    u = res[0]
    # VALIDACIÓN DE RENTA EN CASCADA
    v_str = u['vencimiento']
    if u['rango'] == 'Trabajador':
        jefe = query_db('master.db', "SELECT vencimiento FROM usuarios WHERE clave=?", (u['creado_por'],), True)[0]
        v_str = jefe['vencimiento']
    
    if datetime.now() > datetime.strptime(v_str, "%Y-%m-%d %H:%M:%S"):
        return f'{CSS}<div class="glass"><div class="expired">🚫 SERVICIO SUSPENDIDO<br><small>Contacte al Administrador</small></div><a href="/" class="nav-link" style="text-align:center; margin-top:15px">VOLVER</a></div>'

    session['u_clv'] = clv
    return redirect('/main')

@app.route('/main')
def main():
    if 'u_clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['u_clv'],), True)[0]
    db = get_db_path(u)
    init_negocio(db)
    conf = query_db(db, "SELECT * FROM config", fetch=True)[0]
    
    html = f'{CSS}<div class="glass"><h2>{conf["empresa"]}</h2><p style="color:#64748b">{u["nombre"]} | {u["rango"]}</p>'
    
    if u['rango'] == 'Administrador':
        html += '<a href="/admin_clientes" class="nav-link">💎 Gestionar Clientes (Dueños)</a>'
    elif u['rango'] in ['Dueño', 'Trabajador']:
        html += '<a href="/venta" class="nav-link">🛒 Nueva Venta</a>'
        html += '<a href="/inventario" class="nav-link">📦 Inventario</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/personal" class="nav-link">👥 Empleados</a>'
            html += '<a href="/config" class="nav-link">⚙️ Configuración</a>'
            html += '<a href="/corte" class="nav-link" style="color:#38bdf8">🏁 Corte de Caja</a>'
            
    html += '<hr style="opacity:0.1"><a href="/" style="color:#f43f5e; text-decoration:none; font-size:13px">Salir</a></div>'
    return html

@app.route('/venta')
def venta():
    if 'u_clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['u_clv'],), True)[0]
    db = get_db_path(u)
    prods = query_db(db, "SELECT * FROM productos WHERE stock > 0", fetch=True)
    car = session.get('car', [])
    
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]})</option>' for p in prods])
    return f'''{CSS}<div class="glass"><h2>Caja</h2>
    <form action="/add" method="POST"><select name="id">{ops}</select><input name="q" type="number" step="0.1" placeholder="Cantidad"><button>Añadir</button></form>
    <h3 style="text-align:right">Total: ${sum(i['s'] for i in car)}</h3>
    <a href="/pay" class="nav-link" style="background:var(--p); color:white; text-align:center">COBRAR TICKET</a>
    <a href="/main" class="nav-link" style="text-align:center">Volver</a></div>'''

@app.route('/pay')
def pay():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['u_clv'],), True)[0]
    db = get_db_path(u)
    car = session.get('car', [])
    if not car: return redirect('/venta')
    
    ticket = f"🧾 *{u['nombre']}* \n"
    for i in car:
        query_db(db, "UPDATE productos SET stock=stock-? WHERE codigo=?", (i['c'], i['id']))
        query_db(db, "INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
        ticket += f"• {i['n']} x{i['c']} ${i['s']}\n"
    
    conf = query_db(db, "SELECT whatsapp FROM config", True)[0]
    url = f"https://api.whatsapp.com/send?phone={conf['whatsapp']}&text={urllib.parse.quote(ticket + f'TOTAL: ${sum(i["s"] for i in car)}')}"
    session['car'] = []
    return f"{CSS}<div class='glass'><h2>Venta Lista</h2><a href='{url}' target='_blank' class='nav-link' style='background:#22c55e; color:white'>Enviar por WhatsApp</a><a href='/venta' class='nav-link'>Siguiente</a></div>"

@app.route('/admin_clientes')
def admin_clientes():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['u_clv'],), True)[0]
    clientes = query_db('master.db', "SELECT * FROM usuarios WHERE rango='Dueño'", fetch=True)
    filas = "".join([f"<tr><td>{c['nombre']}</td><td>{c['clave']}</td><td>{c['vencimiento'][:10]}</td></tr>" for c in clientes])
    
    return f'''{CSS}<div class="glass" style="max-width:600px"><h2>Rentas</h2>
    <table style="width:100%; font-size:13px"><tr><th>Negocio</th><th>Clave</th><th>Vence</th></tr>{filas}</table><hr>
    <form action="/nuevo_dueño" method="POST"><input name="n" placeholder="Nombre Negocio"><button>Registrar Cliente (30 días)</button></form>
    <a href="/main" class="nav-link">Volver</a></div>'''

@app.route('/nuevo_dueño', methods=['POST'])
def nuevo_dueño():
    clv = f"DUE-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    vence = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    query_db('master.db', "INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (clv, request.form['n'], 'Dueño', session['u_clv'], 'Activo', vence))
    return redirect('/admin_clientes')

# El resto de rutas (add car, inventario, config) se integran bajo esta misma lógica...

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
    
