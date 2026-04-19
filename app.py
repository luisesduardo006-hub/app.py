import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session, render_template_string

app = Flask(__name__)
app.secret_key = 'clave_secreta_pos_premium_ultra_v5'

# --- CONFIGURACIÓN DE BASE DE DATOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ejecutar_sql(db_name, query, params=(), fetch=False):
    db_path = os.path.join(BASE_DIR, db_name)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        print(f"ERROR SQL ({db_name}): {e}")
        return []

def inicializar_sistema():
    # Base Maestra: Usuarios y Control de Rentas
    ejecutar_sql('master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
        (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, vencimiento TEXT)''')
    
    # Usuario Maestro inicial (ADMIN-01)
    ejecutar_sql('master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?)",
        ("ADMIN-01", "SUPER ADMIN", "Administrador", "SISTEMA", "2099-12-31"))

def cargar_db_negocio(u):
    # Determinar qué base de datos abrir
    db = f"negocio_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"negocio_{u['clave']}.db"
    
    # Crear tablas necesarias si no existen
    ejecutar_sql(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)')
    ejecutar_sql(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT, detalle TEXT)')
    ejecutar_sql(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)')
    ejecutar_sql(db, 'CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    
    # Configuración inicial
    if not ejecutar_sql(db, "SELECT * FROM config", fetch=True):
        ejecutar_sql(db, "INSERT INTO config (id, empresa, whatsapp) VALUES (1, 'Mi Negocio', '52')")
    return db

# --- INTERFAZ VISUAL (CSS PREMIUM) ---
CSS = '''
<style>
    :root { --accent: #00d2ff; --grad: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%); }
    body { background: #0b0e14; color: #e0e6ed; font-family: 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; }
    .card { background: #1a1f29; border: 1px solid #2d3545; border-radius: 15px; padding: 25px; width: 100%; max-width: 450px; margin: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    h2 { margin: 0 0 20px; text-align: center; color: var(--accent); font-weight: 300; letter-spacing: 1px; }
    input, select { background: #0f131a; border: 1px solid #3d4659; color: white; padding: 12px; width: 100%; border-radius: 8px; margin-bottom: 12px; box-sizing: border-box; }
    button { background: var(--grad); color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.3s; }
    button:hover { opacity: 0.9; transform: scale(1.02); }
    .nav-btn { display: block; text-decoration: none; color: #8a99af; padding: 12px; text-align: center; border-radius: 8px; background: rgba(255,255,255,0.05); margin-bottom: 10px; }
    .nav-btn:hover { background: rgba(255,255,255,0.1); color: var(--accent); }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; }
    th, td { text-align: left; padding: 10px; border-bottom: 1px solid #2d3545; }
    .badge { padding: 4px 8px; border-radius: 5px; font-size: 10px; background: #3d4659; }
</style>
'''

# --- LOGICA DE RUTAS ---

@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso POS</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>ENTRAR AL SISTEMA</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if not u: return redirect('/')
    
    # Verificar Vencimiento
    vence = datetime.strptime(u[0]['vencimiento'], "%Y-%m-%d")
    if datetime.now() > vence:
        return f'{CSS}<div class="card"><h2 style="color:#ff4b2b">Cuenta Suspendida</h2><p>Contacte soporte para renovar su suscripción.</p><a href="/" class="nav-btn">Regresar</a></div>'
    
    session['clv'] = u[0]['clave']
    return redirect('/panel')

@app.route('/panel')
def panel():
    if 'clv' not in session: return redirect('/')
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    conf = ejecutar_sql(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
    
    html = f'{CSS}<div class="card"><h2>{conf["empresa"]}</h2><p style="text-align:center; color:#8a99af; font-size:12px">{u["nombre"]} | {u["rango"]}</p>'
    
    if u['rango'] == 'Administrador':
        html += '<a href="/admin_clientes" class="nav-btn">💎 Gestión de Clientes</a>'
    else:
        html += '<a href="/vender" class="nav-btn">🛒 Nueva Venta</a>'
        html += '<a href="/inventario" class="nav-btn">📦 Inventario</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/empleados" class="nav-btn">👥 Empleados</a>'
            html += '<a href="/ajustes" class="nav-btn">⚙️ Configuración</a>'
            html += '<a href="/corte" class="nav-btn" style="color:var(--accent)">🏁 Corte de Caja</a>'
            
    html += '<hr style="opacity:0.1; margin:20px 0"><a href="/" style="color:#ff4b2b; text-decoration:none; display:block; text-align:center; font-size:12px">Cerrar Sesión Segura</a></div>'
    return html

# --- FUNCIÓN DE VENTA PREMIUM (PIEZAS Y KILOS) ---

@app.route('/vender')
def vender():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    prods = ejecutar_sql(db, "SELECT * FROM productos WHERE stock > 0", fetch=True)
    carro = session.get('carro', [])
    
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]}/{p["unidad"]})</option>' for p in prods])
    filas = "".join([f'<tr><td>{i["nombre"]}</td><td>{i["cant"]} {i["uni"]}</td><td>${i["sub"]}</td></tr>' for i in carro])
    
    return f'''{CSS}<div class="card"><h2>Caja</h2>
    <form action="/agregar_carro" method="POST">
        <select name="id">{ops}</select>
        <input name="valor" type="number" step="0.01" placeholder="¿Cuánto? ($ para Kg / Cant para Pza)" required>
        <button type="submit">+ Añadir</button>
    </form>
    <table><tr><th>Producto</th><th>Cant</th><th>Subtotal</th></tr>{filas}</table>
    <h3 style="text-align:right">Total: ${sum(i['sub'] for i in carro)}</h3>
    <a href="/finalizar_venta" class="nav-btn" style="background:var(--accent); color:#1a1f29">COBRAR Y TICKET</a>
    <a href="/panel" class="nav-btn">Regresar</a></div>'''

@app.route('/agregar_carro', methods=['POST'])
def agregar_carro():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    p = ejecutar_sql(db, "SELECT * FROM productos WHERE codigo=?", (request.form['id'],), True)[0]
    val = float(request.form['valor'])
    
    # LÓGICA DE UNIDADES
    if p['unidad'] == 'Kg':
        cantidad = round(val / p['precio'], 3)
        subtotal = val # En kilos, el valor ingresado es el dinero
    else:
        cantidad = val
        subtotal = round(val * p['precio'], 2)
        
    carro = session.get('carro', [])
    carro.append({'id': p['codigo'], 'nombre': p['nombre'], 'cant': cantidad, 'sub': subtotal, 'uni': p['unidad']})
    session['carro'] = carro
    return redirect('/vender')

@app.route('/finalizar_venta')
def finalizar_venta():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    carro = session.get('carro', [])
    if not carro: return redirect('/vender')
    
    ticket = f"🧾 *{u['nombre']}*\n--------------------------\n"
    total = sum(i['sub'] for i in carro)
    
    for item in carro:
        # Descontar stock
        ejecutar_sql(db, "UPDATE productos SET stock = stock - ? WHERE codigo = ?", (item['cant'], item['id']))
        # Guardar venta
        ejecutar_sql(db, "INSERT INTO ventas (total, fecha, vendedor, detalle) VALUES (?,?,?,?)", 
                    (item['sub'], datetime.now().strftime("%Y-%m-%d %H:%M"), u['nombre'], item['nombre']))
        ticket += f"• {item['nombre']} ({item['cant']} {item['uni']}) -> ${item['sub']}\n"
    
    ticket += f"--------------------------\n*TOTAL: ${total}*\n¡Gracias por su compra!"
    conf = ejecutar_sql(db, "SELECT whatsapp FROM config", True)[0]
    session['carro'] = []
    
    # Generar URL de WhatsApp
    url_ws = f"https://api.whatsapp.com/send?phone={conf['whatsapp']}&text={urllib.parse.quote(ticket)}"
    return f'{CSS}<div class="card"><h2>¡Venta Exitosa!</h2><a href="{url_ws}" target="_blank" class="nav-btn" style="background:#25d366; color:white">ENVIAR TICKET WS</a><a href="/vender" class="nav-btn">Nueva Venta</a></div>'

# --- GESTIÓN DE INVENTARIO ---

@app.route('/inventario')
def inventario():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    ps = ejecutar_sql(db, "SELECT * FROM productos", True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']} {p['unidad']}</td></tr>" for p in ps])
    
    form = ""
    if u['rango'] == 'Dueño':
        form = f'''<hr><form action="/update_prod" method="POST">
            <input name="c" placeholder="Código Barras" required>
            <input name="n" placeholder="Nombre Producto" required>
            <input name="p" step="0.01" type="number" placeholder="Precio" required>
            <input name="s" step="0.01" type="number" placeholder="Stock Inicial" required>
            <select name="u"><option value="Pza">Pieza</option><option value="Kg">Kilo</option></select>
            <button>GUARDAR / ACTUALIZAR</button></form>'''
            
    return f'{CSS}<div class="card"><h2>Inventario</h2><table>{filas}</table>{form}<a href="/panel" class="nav-btn">Regresar</a></div>'

@app.route('/update_prod', methods=['POST'])
def update_prod():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    ejecutar_sql(db, "INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", 
                (request.form['c'], request.form['n'], request.form['p'], request.form['s'], request.form['u']))
    return redirect('/inventario')

# --- CORTE DE CAJA Y CONFIGURACIÓN ---

@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    if request.method == 'POST':
        ejecutar_sql(db, "UPDATE config SET empresa=?, whatsapp=? WHERE id=1", (request.form['e'], request.form['w']))
        return redirect('/panel')
    c = ejecutar_sql(db, "SELECT * FROM config", True)[0]
    return f'{CSS}<div class="card"><h2>Ajustes</h2><form method="POST"><input name="e" value="{c["empresa"]}"><input name="w" value="{c["whatsapp"]}"><button>GUARDAR</button></form><a href="/panel" class="nav-btn">Regresar</a></div>'

@app.route('/corte')
def corte():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    total_v = ejecutar_sql(db, "SELECT SUM(total) as t FROM ventas", fetch=True)[0]['t'] or 0
    return f'''{CSS}<div class="card"><h2>Corte del Día</h2><div style="background:#0f131a; padding:20px; border-radius:10px; margin-bottom:15px">
    <p>Ventas Totales: <b>${total_v}</b></p></div>
    <form action="/cerrar_caja" method="POST"><button style="background:#ff4b2b">CERRAR DÍA (REINICIAR)</button></form>
    <a href="/panel" class="nav-btn">Regresar</a></div>'''

@app.route('/cerrar_caja', methods=['POST'])
def cerrar_caja():
    u = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = cargar_db_negocio(u)
    ejecutar_sql(db, "DELETE FROM ventas")
    return redirect('/panel')

# --- ADMIN DE CLIENTES (RENTA) ---

@app.route('/admin_clientes')
def admin_clientes():
    cls = ejecutar_sql('master.db', "SELECT * FROM usuarios WHERE rango='Dueño'", True)
    filas = "".join([f"<tr><td>{c['nombre']}</td><td>{c['clave']}</td><td>{c['vencimiento']}</td></tr>" for c in cls])
    return f'''{CSS}<div class="card" style="max-width:600px"><h2>Rentas</h2><table>{filas}</table><hr>
    <form action="/crear_cliente" method="POST"><input name="n" placeholder="Nombre Negocio"><button>NUEVO CLIENTE (30 DÍAS)</button></form>
    <a href="/panel" class="nav-btn">Regresar</a></div>'''

@app.route('/crear_cliente', methods=['POST'])
def crear_cliente():
    clv = f"DUE-{''.join(random.choices(string.digits, k=4))}"
    vence = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    ejecutar_sql('master.db', "INSERT INTO usuarios VALUES (?,?,?,?,?)", (clv, request.form['n'], 'Dueño', 'ADMIN-01', vence))
    return redirect('/admin_clientes')

if __name__ == "__main__":
    inicializar_sistema()
    app.run(host='0.0.0.0', port=10000)
                                                                                
