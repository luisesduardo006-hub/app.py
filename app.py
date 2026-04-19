import sqlite3
import os
import csv
import io
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, redirect, session, send_file

app = Flask(__name__)
app.secret_key = 'modern_glass_system_2026'

# ==========================================
# 1. NÚCLEO DE DATOS
# ==========================================

def ejecutar_db(db_name, query, params=(), fetch=False, commit=True):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        if commit:
            conn.commit()
    finally:
        conn.close()

def db_init_global():
    query = '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, 
                creado_por TEXT, estado TEXT, vencimiento TEXT)'''
    ejecutar_db('usuarios_master.db', query)
    ejecutar_db('usuarios_master.db', 
                "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ROOT-99", "DIOS ADMIN", "Super Admin", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def db_init_tienda(db_tienda):
    queries = [
        'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)',
        'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)',
        'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)',
        'CREATE TABLE IF NOT EXISTS configuracion (id INTEGER PRIMARY KEY, nombre_negocio TEXT, whatsapp TEXT)'
    ]
    for q in queries: ejecutar_db(db_tienda, q)
    check = ejecutar_db(db_tienda, "SELECT count(*) as c FROM configuracion", fetch=True)[0]
    if check['c'] == 0:
        ejecutar_db(db_tienda, "INSERT INTO configuracion (id, nombre_negocio, whatsapp) VALUES (1, 'Premium Store', '')")

# ==========================================
# 2. DISEÑO MODERNO (GLASSMORPHISM)
# ==========================================

CSS = '''
<style>
    :root {
        --primary: #6366f1;
        --secondary: #a855f7;
        --bg: #0f172a;
        --card: rgba(30, 41, 59, 0.7);
        --text: #f8fafc;
        --accent: #22d3ee;
    }
    * { box-sizing: border-box; transition: all 0.3s ease; }
    body { 
        background: radial-gradient(circle at top left, #1e1b4b, #0f172a); 
        color: var(--text); 
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
        margin: 0; padding: 20px; display: flex; align-items: center; justify-content: center; min-height: 100vh;
    }
    .glass-card { 
        background: var(--card); 
        backdrop-filter: blur(12px); 
        -webkit-backdrop-filter: blur(12px); 
        border: 1px solid rgba(255, 255, 255, 0.1); 
        border-radius: 24px; 
        padding: 30px; 
        width: 100%; max-width: 500px; 
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }
    h2, h3 { margin-top: 0; background: linear-gradient(to right, var(--accent), var(--secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; }
    input, select { 
        background: rgba(15, 23, 42, 0.6); 
        border: 1px solid rgba(255, 255, 255, 0.1); 
        color: white; padding: 14px; width: 100%; border-radius: 12px; margin-bottom: 15px; font-size: 16px;
    }
    input:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }
    button { 
        background: linear-gradient(135deg, var(--primary), var(--secondary)); 
        color: white; border: none; padding: 16px; width: 100%; border-radius: 12px; font-weight: bold; cursor: pointer; font-size: 16px; letter-spacing: 1px;
    }
    button:hover { transform: translateY(-2px); filter: brightness(1.1); box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4); }
    .nav-btn { 
        display: block; text-decoration: none; color: #94a3b8; padding: 12px; border-radius: 12px; margin-bottom: 8px; border: 1px solid transparent; 
    }
    .nav-btn:hover { background: rgba(255, 255, 255, 0.05); color: var(--accent); border-color: rgba(34, 211, 238, 0.3); }
    table { width: 100%; border-spacing: 0; margin-top: 20px; }
    th { color: #64748b; font-size: 12px; text-transform: uppercase; padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); }
    td { padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }
    .badge { padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; background: rgba(255,255,0,0.1); color: yellow; }
</style>
'''

# ==========================================
# 3. LÓGICA DE NEGOCIO
# ==========================================

def get_user(clv): return ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE clave=?", (clv,), True)

def get_db(u): return f"tienda_{u['creado_por'] if u['rango']=='Trabajador' else u['clave']}.db"

@app.route('/')
def home():
    session.clear()
    return f'{CSS}<div class="glass-card"><h2>Modern POS</h2><p style="color:#64748b">Inicia sesión para continuar</p><form action="/auth" method="post"><input type="text" name="c" placeholder="Clave de acceso" required autofocus><button>ENTRAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = get_user(request.form.get('c'))
    if not res: return redirect('/')
    u = res[0]
    session['u'] = u['clave']
    return redirect('/hub')

@app.route('/hub')
def hub():
    if 'u' not in session: return redirect('/')
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    db_init_tienda(db_t)
    conf = ejecutar_db(db_t, "SELECT * FROM configuracion WHERE id=1", fetch=True)[0]
    
    html = f'{CSS}<div class="glass-card"><h3>{conf["nombre_negocio"]}</h3><p style="font-size:13px; color:#94a3b8">{u["nombre"]} • {u["rango"]}</p><hr style="opacity:0.1">'
    
    if u['rango'] in ['Super Admin', 'Administrador']:
        html += '<a href="/m_dueños" class="nav-btn">💎 Gestión de Clientes</a>'
        if u['rango'] == 'Super Admin': html += '<a href="/m_personal" class="nav-btn">🛡️ Control de Admins</a>'
    
    elif u['rango'] in ['Dueño', 'Trabajador']:
        html += '<a href="/pos" class="nav-btn">🛒 Terminal de Venta</a>'
        html += '<a href="/stk" class="nav-btn">📦 Inventario Real</a>'
        html += '<a href="/pay" class="nav-btn">💸 Pago de Servicios</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/m_personal" class="nav-btn">👥 Gestión de Personal</a>'
            html += '<a href="/cfg" class="nav-btn">⚙️ Configuración</a>'
            html += '<a href="/end" class="nav-btn" style="color:var(--accent)">🏁 Realizar Corte Final</a>'
            
    html += '<hr style="opacity:0.1"><a href="/" style="color:var(--danger); font-size:12px; text-decoration:none; display:block; text-align:center">Cerrar Sesión Segura</a></div>'
    return html

@app.route('/pos')
def pos():
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    prods = ejecutar_db(db_t, "SELECT * FROM productos WHERE stock > 0 ORDER BY nombre ASC", True)
    car = session.get('car', [])
    tot = sum(i['s'] for i in car)
    
    ops = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    filas = "".join([f"<tr><td>{i['n']}</td><td>{i['c']}</td><td>${i['s']}</td></tr>" for i in car])
    
    return f'''{CSS}<div class="glass-card"><h3>🛒 Ventas</h3>
    <form action="/add_car" method="post"><select name="id">{ops}</select><input type="number" step="0.1" name="q" placeholder="Cantidad"><button>Añadir al Carrito</button></form>
    <table><tr><th>Producto</th><th>Cant.</th><th>Sub.</th></tr>{filas}</table>
    <h3 style="text-align:right; margin-top:15px">Total: ${tot}</h3>
    <a href="/checkout" class="btn-wa" style="background:var(--primary)">Confirmar Venta</a>
    <a href="/hub" class="nav-btn" style="text-align:center">Regresar</a></div>'''

@app.route('/add_car', methods=['POST'])
def add_car():
    u = get_user(session['u'])[0]
    p = ejecutar_db(get_db(u), "SELECT * FROM productos WHERE codigo=?", (request.form['id'],), True)[0]
    q = float(request.form['q'] or 1)
    car = session.get('car', [])
    car.append({'id': p['codigo'], 'n': p['nombre'], 'c': q, 's': round(p['precio']*q, 2)})
    session['car'] = car
    return redirect('/pos')

@app.route('/checkout')
def checkout():
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    car = session.get('car', [])
    if not car: return redirect('/pos')
    
    t_venta = sum(i['s'] for i in car)
    ticket = f"✨ *{u['nombre'].upper()}* \n----------------\n"
    for i in car:
        ejecutar_db(db_t, "UPDATE productos SET stock=stock-? WHERE codigo=?", (i['c'], i['id']))
        ejecutar_db(db_t, "INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
        ticket += f"🔹 {i['n']} (x{i['c']}) ${i['s']}\n"
    
    ticket += f"----------------\n✅ *TOTAL: ${t_venta}*"
    conf = ejecutar_db(db_t, "SELECT whatsapp FROM configuracion", fetch=True)[0]
    session['car'] = []
    url = f"https://api.whatsapp.com/send?phone={conf['whatsapp']}&text={urllib.parse.quote(ticket)}"
    return f"{CSS}<div class='glass-card'><h3>Venta Exitosa</h3><a href='{url}' target='_blank' class='btn-wa'>Enviar Ticket Digital</a><a href='/pos' class='nav-btn' style='text-align:center'>Siguiente Venta</a></div>"

@app.route('/stk')
def stk():
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    prods = ejecutar_db(db_t, "SELECT * FROM productos ORDER BY nombre ASC", True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>" for p in prods])
    
    add = f'<hr style="opacity:0.1"><form action="/p_save" method="post"><input name="c" placeholder="Código"><input name="n" placeholder="Nombre"><input name="p" placeholder="Precio"><input name="s" placeholder="Stock"><button>Actualizar Stock</button></form>' if u['rango']=='Dueño' else ""
    return f'{CSS}<div class="glass-card" style="max-width:600px"><h3>📦 Inventario</h3><table><tr><th>Item</th><th>Precio</th><th>Stock</th></tr>{filas}</table>{add}<a href="/hub" class="nav-btn" style="text-align:center">Regresar</a></div>'

@app.route('/p_save', methods=['POST'])
def p_save():
    u = get_user(session['u'])[0]
    ejecutar_db(get_db(u), "INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['c'], request.form['n'], request.form['p'], request.form['s'], 'PZ'))
    return redirect('/stk')

@app.route('/pay', methods=['GET', 'POST'])
def pay():
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    if request.method == 'POST':
        ejecutar_db(db_t, "INSERT INTO gastos (concepto, monto, fecha) VALUES (?,?,?)", (request.form['c'], request.form['m'], datetime.now().strftime("%Y-%m-%d")))
    
    gs = ejecutar_db(db_t, "SELECT * FROM gastos ORDER BY id DESC LIMIT 5", True)
    filas = "".join([f"<tr><td>{g['concepto']}</td><td>${g['monto']}</td></tr>" for g in gs])
    return f'''{CSS}<div class="glass-card"><h3>💸 Gastos</h3><form method="post"><input name="c" placeholder="Concepto"><input name="m" type="number" placeholder="Monto $"><button>Registrar Pago</button></form><table>{filas}</table><a href="/hub" class="nav-btn" style="text-align:center">Regresar</a></div>'''

@app.route('/m_personal')
def m_personal():
    u = get_user(session['u'])[0]
    target = "Administrador" if u['rango'] == "Super Admin" else "Trabajador"
    pers = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE creado_por=?", (u['clave'],), True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td><span class='badge'>{p['clave']}</span></td></tr>" for p in pers])
    return f'''{CSS}<div class="glass-card"><h3>👥 {target}es</h3><table>{filas}</table><hr style="opacity:0.1"><form action="/u_add" method="post"><input name="n" placeholder="Nombre completo"><input type="hidden" name="r" value="{target}"><button>Crear Acceso</button></form><a href="/hub" class="nav-btn" style="text-align:center">Regresar</a></div>'''

@app.route('/m_dueños')
def m_dueños():
    u = get_user(session['u'])[0]
    ds = ejecutar_db('usuarios_master.db', "SELECT * FROM usuarios WHERE rango='Dueño'", True)
    filas = "".join([f"<tr><td>{d['nombre']}</td><td><span class='badge'>{d['clave']}</span></td></tr>" for d in ds])
    return f'''{CSS}<div class="glass-card"><h3>💎 Dueños</h3><table>{filas}</table><hr style="opacity:0.1"><form action="/u_add" method="post"><input name="n" placeholder="Nombre del Negocio"><input type="hidden" name="r" value="Dueño"><button>Activar Nuevo Dueño</button></form><a href="/hub" class="nav-btn" style="text-align:center">Regresar</a></div>'''

@app.route('/u_add', methods=['POST'])
def u_add():
    j = get_user(session['u'])[0]
    clv = f"{request.form['r'][:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    v = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S") if request.form['r'] == "Dueño" else "2099-12-31 23:59:59"
    ejecutar_db('usuarios_master.db', "INSERT INTO usuarios VALUES (?,?,?,?,?,?)", (clv, request.form['n'], request.form['r'], j['clave'], "Activo", v))
    return redirect('/m_dueños' if request.form['r']=="Dueño" else '/m_personal')

@app.route('/cfg', methods=['GET', 'POST'])
def cfg():
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    if request.method == 'POST':
        ejecutar_db(db_t, "UPDATE configuracion SET nombre_negocio=?, whatsapp=? WHERE id=1", (request.form['n'], request.form['w']))
        return redirect('/hub')
    c = ejecutar_db(db_t, "SELECT * FROM configuracion", True)[0]
    return f'''{CSS}<div class="glass-card"><h3>⚙️ Perfil</h3><form method="post"><input name="n" value="{c['nombre_negocio']}"><input name="w" value="{c['whatsapp']}" placeholder="WhatsApp (521...)"><button>Guardar</button></form><a href="/hub" class="nav-btn" style="text-align:center">Regresar</a></div>'''

@app.route('/end')
def end():
    u = get_user(session['u'])[0]
    db_t = get_db(u)
    v = ejecutar_db(db_t, "SELECT sum(total) as s FROM ventas", True)[0]['s'] or 0
    g = ejecutar_db(db_t, "SELECT sum(monto) as s FROM gastos", True)[0]['s'] or 0
    msg = f"🏁 *CORTE DE CAJA*\n💰 Ventas: ${v}\n💸 Gastos: ${g}\n📈 Neto: ${v-g}"
    ejecutar_db(db_t, "DELETE FROM ventas"); ejecutar_db(db_t, "DELETE FROM gastos")
    c = ejecutar_db(db_t, "SELECT whatsapp FROM configuracion", True)[0]
    url = f"https://api.whatsapp.com/send?phone={c['whatsapp']}&text={urllib.parse.quote(msg)}"
    return f"{CSS}<div class='glass-card'><h3>Corte Finalizado</h3><p style='color:#94a3b8'>{msg.replace('\n','<br>')}</p><a href='{url}' target='_blank' class='btn-wa'>Enviar Reporte</a><a href='/hub' class='nav-btn' style='text-align:center'>Finalizar</a></div>"

if __name__ == "__main__":
    db_init_global()
    app.run(host='0.0.0.0', port=10000)
    
