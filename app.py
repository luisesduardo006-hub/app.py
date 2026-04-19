import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime
from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = 'SISTEMA_TEST_FULL_V6'

# --- MOTOR DE DATOS ---
def query_db(query, params=(), fetch=False):
    try:
        with sqlite3.connect('sistema_v6.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        print(f"Error: {e}")
        return []

def init_db():
    # Creación de Tablas
    query_db('''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, jefe TEXT)''')
    query_db('CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT, dueño TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, detalle TEXT, vendedor TEXT, dueño TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS config (dueño TEXT PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    
    # --- DATOS DE PRUEBA (AUTO-CARGA) ---
    # 1. Super Admin
    query_db("INSERT OR IGNORE INTO usuarios VALUES ('ADMIN-01', 'SUPER ADMIN', 'Administrador', 'SISTEMA')")
    
    # 2. Dueño de Prueba
    query_db("INSERT OR IGNORE INTO usuarios VALUES ('DUE-99', 'TIENDA TEST', 'Dueño', 'ADMIN-01')")
    query_db("INSERT OR IGNORE INTO config VALUES ('DUE-99', 'TIENDA TEST', '52')")
    
    # 3. Trabajador de Prueba
    query_db("INSERT OR IGNORE INTO usuarios VALUES ('TRA-11', 'EMPLEADO UNO', 'Trabajador', 'DUE-99')")
    
    # 4. Inventario de Prueba (DUE-99 es el dueño)
    productos_test = [
        ('101', 'Huevo Blanco', 45.0, 50.0, 'Kg', 'DUE-99'),
        ('102', 'Coca-Cola 600ml', 18.5, 24.0, 'Pza', 'DUE-99'),
        ('103', 'Tortilla de Maíz', 22.0, 100.0, 'Kg', 'DUE-99')
    ]
    for p in productos_test:
        query_db("INSERT OR IGNORE INTO productos VALUES (?,?,?,?,?,?)", p)

# --- DISEÑO ---
CSS = '''
<style>
    :root { --p: #00d2ff; --bg: #0f172a; --card: #1e293b; }
    body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; }
    .card { background: var(--card); border-radius: 15px; padding: 20px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); margin-bottom: 20px; }
    h2 { color: var(--p); margin: 0 0 15px 0; border-bottom: 1px solid #334155; padding-bottom: 10px; }
    input, select { background: #0f172a; border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 8px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: linear-gradient(to right, #00d2ff, #3a7bd5); color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
    th { text-align: left; color: var(--p); border-bottom: 2px solid #334155; padding: 8px; }
    td { padding: 8px; border-bottom: 1px solid #334155; }
    .btn-nav { text-decoration: none; color: #94a3b8; display: block; text-align: center; padding: 10px; margin-top: 10px; background: #0f172a; border-radius: 8px; font-size: 14px; }
    .badge { padding: 3px 7px; border-radius: 5px; font-size: 10px; background: #334155; }
</style>
'''

@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso POS</h2><p style="font-size:10px; color:gray">Prueba: DUE-99 o TRA-11</p><form action="/auth" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>ENTRAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db("SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if res:
        session['clv'] = res[0]['clave']
        session['user'] = res[0]['nombre']
        session['rango'] = res[0]['rango']
        session['dueño'] = res[0]['jefe'] if res[0]['rango'] == 'Trabajador' else res[0]['clave']
        return redirect('/hub')
    return redirect('/')

@app.route('/hub')
def hub():
    if 'clv' not in session: return redirect('/')
    r = session['rango']
    c = query_db("SELECT empresa FROM config WHERE dueño=?", (session['dueño'],), True)
    empresa = c[0]['empresa'] if c else "SISTEMA ADMIN"
    html = f'{CSS}<div class="card"><h2>{empresa}</h2><p>Sesión: {session["user"]} <span class="badge">{r}</span></p>'
    if r == 'Administrador':
        html += '<a href="/gestion_personal" class="btn-nav" style="background:var(--p); color:black">💎 GESTIONAR DUEÑOS</a>'
    else:
        html += '<a href="/pos" class="btn-nav" style="background:#00d2ff; color:#0f172a; font-weight:bold">🛒 NUEVA VENTA</a>'
        html += '<a href="/inventario" class="btn-nav">📦 INVENTARIO</a>'
        if r == 'Dueño':
            html += '<a href="/gestion_personal" class="btn-nav">👥 GESTIONAR TRABAJADORES</a>'
            html += '<a href="/corte" class="btn-nav">📊 CORTE DE CAJA</a>'
            html += '<a href="/ajustes" class="btn-nav">⚙️ CONFIGURACIÓN</a>'
    html += '<a href="/" class="btn-nav" style="color:#f43f5e; margin-top:20px">Cerrar Sesión</a></div>'
    return html

@app.route('/gestion_personal')
def gestion_personal():
    if 'clv' not in session: return redirect('/')
    buscado = 'Dueño' if session['rango'] == 'Administrador' else 'Trabajador'
    lista = query_db("SELECT * FROM usuarios WHERE rango=? AND jefe=?", (buscado, session['clv']), True)
    filas = "".join([f"<tr><td>{u['nombre']}</td><td><code>{u['clave']}</code></td></tr>" for u in lista])
    return f'{CSS}<div class="card"><h2>Gestión</h2><table><tr><th>Nombre</th><th>Clave</th></tr>{filas}</table><hr><form action="/crear_usuario" method="POST"><input name="n" placeholder="Nombre" required><button>CREAR NUEVO</button></form><a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/crear_usuario', methods=['POST'])
def crear_usuario():
    nuevo_rango = 'Dueño' if session['rango'] == 'Administrador' else 'Trabajador'
    nueva_clv = f"{nuevo_rango[:2].upper()}-{random.randint(1000, 9999)}"
    query_db("INSERT INTO usuarios VALUES (?,?,?,?)", (nueva_clv, request.form['n'], nuevo_rango, session['clv']))
    if nuevo_rango == 'Dueño':
        query_db("INSERT OR IGNORE INTO config VALUES (?,?,?)", (nueva_clv, request.form['n'], '52'))
    return redirect('/gestion_personal')

@app.route('/inventario')
def inventario():
    ps = query_db("SELECT * FROM productos WHERE dueño=?", (session['dueño'],), True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']} {p['unidad']}</td></tr>" for p in ps])
    form = f'''<hr><form action="/save_prod" method="POST"><input name="c" placeholder="Código"><input name="n" placeholder="Nombre"><input name="p" step="0.01" type="number" placeholder="Precio"><input name="s" step="0.01" type="number" placeholder="Stock"><select name="u"><option value="Pza">Pieza</option><option value="Kg">Kilo</option></select><button>Guardar</button></form>''' if session['rango'] == 'Dueño' else ""
    return f'{CSS}<div class="card"><h2>Inventario</h2><table>{filas}</table>{form}<a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/save_prod', methods=['POST'])
def save_prod():
    query_db("INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?,?)", (request.form['c'], request.form['n'], request.form['p'], request.form['s'], request.form['u'], session['dueño']))
    return redirect('/inventario')

@app.route('/pos')
def pos():
    prods = query_db("SELECT * FROM productos WHERE dueño=? AND stock > 0", (session['dueño'],), True)
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]})</option>' for p in prods])
    carro = session.get('carro', [])
    total = sum(i['s'] for i in carro)
    return f'''{CSS}<div class="card"><h2>Caja</h2><form action="/add_carro" method="POST"><select name="id">{ops}</select><input name="val" type="number" step="0.01" placeholder="Monto $ o Cantidad" required><button>Añadir</button></form><h3>Total: ${total}</h3><a href="/pagar" class="btn-nav" style="background:#22c55e; color:white">COBRAR</a><a href="/hub" class="btn-nav">Regresar</a></div>'''

@app.route('/add_carro', methods=['POST'])
def add_carro():
    p = query_db("SELECT * FROM productos WHERE codigo=?", (request.form['id'],), True)[0]
    val = float(request.form['val'])
    cant = round(val / p['precio'], 3) if p['unidad'] == 'Kg' else val
    sub = val if p['unidad'] == 'Kg' else round(val * p['precio'], 2)
    carro = session.get('carro', []); carro.append({'id': p['codigo'], 'n': p['nombre'], 'c': cant, 's': sub, 'u': p['unidad']})
    session['carro'] = carro
    return redirect('/pos')

@app.route('/pagar')
def pagar():
    carro = session.get('carro', [])
    if not carro: return redirect('/pos')
    ticket = f"🧾 *{session['user']}*\n"
    total = sum(i['s'] for i in carro)
    for i in carro:
        query_db("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (i['c'], i['id']))
        query_db("INSERT INTO ventas (total, fecha, detalle, vendedor, dueño) VALUES (?,?,?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), i['n'], session['user'], session['dueño']))
        ticket += f"• {i['n']} ({i['c']}{i['u']}) ${i['s']}\n"
    conf = query_db("SELECT whatsapp FROM config WHERE dueño=?", (session['dueño'],), True)[0]
    session['carro'] = []
    return redirect(f"https://api.whatsapp.com/send?phone={conf['whatsapp']}&text={urllib.parse.quote(ticket + f'*TOTAL: ${total}*')}")

@app.route('/corte')
def corte():
    ventas = query_db("SELECT * FROM ventas WHERE dueño=? ORDER BY id DESC", (session['dueño'],), True)
    total = sum(v['total'] for v in ventas)
    filas = "".join([f"<tr><td>{v['fecha']}</td><td>{v['vendedor']}</td><td>${v['total']}</td></tr>" for v in ventas])
    return f'{CSS}<div class="card"><h2>Corte</h2><h1>${total}</h1><table>{filas}</table><form action="/reset" method="POST"><button style="background:#f43f5e; margin-top:10px">CERRAR CAJA</button></form><a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/reset', methods=['POST'])
def reset():
    query_db("DELETE FROM ventas WHERE dueño=?", (session['dueño'],))
    return redirect('/corte')

@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    if request.method == 'POST':
        query_db("UPDATE config SET empresa=?, whatsapp=? WHERE dueño=?", (request.form['e'], request.form['w'], session['dueño']))
        return redirect('/hub')
    c = query_db("SELECT * FROM config WHERE dueño=?", (session['dueño'],), True)[0]
    return f'{CSS}<div class="card"><h2>Ajustes</h2><form method="POST"><input name="e" value="{c["empresa"]}"><input name="w" value="{c["whatsapp"]}"><button>Guardar</button></form><a href="/hub" class="btn-nav">Volver</a></div>'

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
    
