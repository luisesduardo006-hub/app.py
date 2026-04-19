import sqlite3
import os
import csv
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session, send_file

app = Flask(__name__)
app.secret_key = 'reparacion_total_blindada_2026'

# --- MOTOR DE DATOS REPARADO ---

def ejecutar_db(db_name, query, params=(), fetch=False):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        conn.commit()
    except Exception as e:
        print(f"Error DB: {e}")
        return []
    finally:
        conn.close()

def iniciar_sistema():
    # Base maestra de accesos
    ejecutar_db('usuarios_master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT, vencimiento TEXT)''')
    ejecutar_db('usuarios_master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ROOT-99", "ADMIN MAESTRO", "Super Admin", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def db_negocio(u_clv, rango, creado):
    clv = creado if rango == 'Trabajador' else u_clv
    db = f"tienda_{clv}.db"
    ejecutar_db(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)')
    ejecutar_db(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)')
    ejecutar_db(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)')
    ejecutar_db(db, 'CREATE TABLE IF NOT EXISTS configuracion (id INTEGER PRIMARY KEY, nombre_negocio TEXT, whatsapp TEXT)')
    if not ejecutar_db(db, "SELECT * FROM configuracion", fetch=True):
        ejecutar_db(db, "INSERT INTO configuracion (id, nombre_negocio, whatsapp) VALUES (1, 'Mi Negocio', '')")
    return db

# --- INTERFAZ GLASSMORPHISM ---

CSS = '''
<style>
    :root { --p: #6366f1; --s: #a855f7; --bg: #0f172a; --txt: #f8fafc; }
    body { background: #0f172a; color: var(--txt); font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
    .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); padding: 2rem; border-radius: 20px; width: 90%; max-width: 400px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
    h2 { background: linear-gradient(to right, #22d3ee, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 1rem; }
    input, select { background: rgba(0,0,0,0.3); border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; }
    button { background: linear-gradient(135deg, var(--p), var(--s)); color: white; border: none; padding: 14px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; }
    .nav { display: block; text-decoration: none; color: #94a3b8; padding: 10px; border-radius: 8px; margin-bottom: 5px; border: 1px solid transparent; }
    .nav:hover { background: rgba(255,255,255,0.05); color: #22d3ee; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
    td, th { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); text-align: left; }
</style>
'''

# --- RUTAS REPARADAS ---

@app.route('/')
def login_view():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso</h2><form action="/entrar" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>INGRESAR</button></form></div>'

@app.route('/entrar', methods=['POST'])
def entrar():
    clv = request.form.get('c')
    res = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (clv,), True)
    if res:
        session['clv'] = clv
        return redirect('/dashboard')
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'clv' not in session: return redirect('/')
    u = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u['clave'], u['rango'], u['creado_por'])
    conf = ejecutar_db(db, "SELECT * FROM configuracion", fetch=True)[0]
    
    html = f'{CSS}<div class="card"><h2>{conf["nombre_negocio"]}</h2><p style="color:#94a3b8; font-size:12px">{u["nombre"]} | {u["rango"]}</p><hr style="opacity:0.1">'
    
    if u['rango'] in ['Super Admin', 'Administrador']:
        html += '<a href="/clientes" class="nav">🏢 Gestionar Clientes</a>'
    elif u['rango'] in ['Dueño', 'Trabajador']:
        html += '<a href="/caja" class="nav">🛒 Punto de Venta</a>'
        html += '<a href="/inventario" class="nav">📦 Stock e Inventario</a>'
        html += '<a href="/gastos" class="nav">💸 Gastos/Servicios</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/personal" class="nav">👥 Mis Empleados</a>'
            html += '<a href="/config" class="nav">⚙️ Ajustes</a>'
            html += '<a href="/corte" class="nav" style="color:#22d3ee">🏁 Realizar Corte</a>'
    
    html += '<hr style="opacity:0.1"><a href="/" style="color:#ef4444; font-size:12px; text-decoration:none">Cerrar Sesión</a></div>'
    return html

@app.route('/caja')
def caja():
    if 'clv' not in session: return redirect('/')
    u = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u['clave'], u['rango'], u['creado_por'])
    prods = ejecutar_db(db, "SELECT * FROM productos WHERE stock > 0", True)
    car = session.get('car', [])
    
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]})</option>' for p in prods])
    filas = "".join([f'<tr><td>{i["n"]}</td><td>{i["c"]}</td><td>${i["s"]}</td></tr>' for i in car])
    
    return f'''{CSS}<div class="card"><h2>Carrito</h2>
    <form action="/add" method="POST"><select name="id">{ops}</select><input name="q" type="number" step="0.1" placeholder="Cantidad"><button>Añadir</button></form>
    <table>{filas}</table><h3 style="text-align:right">${sum(i["s"] for i in car)}</h3>
    <a href="/cobrar" style="background:var(--p); color:white; text-decoration:none; display:block; text-align:center; padding:12px; border-radius:10px; font-weight:bold">COBRAR</a>
    <a href="/dashboard" class="nav" style="text-align:center; margin-top:10px">Volver</a></div>'''

@app.route('/add', methods=['POST'])
def add():
    u = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    p = ejecutar_db(db_negocio(u['clave'], u['rango'], u['creado_por']), "SELECT * FROM productos WHERE codigo=?", (request.form['id'],), True)[0]
    q = float(request.form['q'] or 1)
    car = session.get('car', [])
    car.append({'id': p['codigo'], 'n': p['nombre'], 'c': q, 's': round(p['precio']*q, 2)})
    session['car'] = car
    return redirect('/caja')

@app.route('/cobrar')
def cobrar():
    if 'clv' not in session: return redirect('/')
    u = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u['clave'], u['rango'], u['creado_por'])
    car = session.get('car', [])
    if not car: return redirect('/caja')
    
    ticket = f"🧾 *TICKET* \n"
    for i in car:
        ejecutar_db(db, "UPDATE productos SET stock=stock-? WHERE codigo=?", (i['c'], i['id']))
        ejecutar_db(db, "INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
        ticket += f"• {i['n']} x{i['c']} ${i['s']}\n"
    
    conf = ejecutar_db(db, "SELECT whatsapp FROM configuracion", True)[0]
    session['car'] = []
    url = f"https://api.whatsapp.com/send?phone={conf['whatsapp']}&text={urllib.parse.quote(ticket + f'TOTAL: ${sum(i["s"] for i in car)}')}"
    return f"{CSS}<div class='card'><h2>Éxito</h2><a href='{url}' target='_blank' class='nav'>Enviar WhatsApp</a><a href='/caja' class='nav'>Nueva Venta</a></div>"

@app.route('/inventario')
def inventario():
    if 'clv' not in session: return redirect('/')
    u = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u['clave'], u['rango'], u['creado_por'])
    prods = ejecutar_db(db, "SELECT * const FROM productos", True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>" for p in prods])
    
    form = f'<hr><form action="/p_save" method="POST"><input name="c" placeholder="Cod"><input name="n" placeholder="Nom"><input name="p" placeholder="Pre"><input name="s" placeholder="Stk"><button>Guardar</button></form>' if u['rango'] == 'Dueño' else ""
    return f'{CSS}<div class="card"><h2>Stock</h2><table>{filas}</table>{form}<a href="/dashboard" class="nav">Volver</a></div>'

@app.route('/p_save', methods=['POST'])
def p_save():
    u = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    ejecutar_db(db_negocio(u['clave'], u['rango'], u['creado_por']), "INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['c'], request.form['n'], request.form['p'], request.form['s'], 'PZ'))
    return redirect('/inventario')

# --- INICIO ---
if __name__ == "__main__":
    iniciar_sistema()
    app.run(host='0.0.0.0', port=10000)
    
