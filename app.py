import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = 'SISTEMA_ULTRA_ESTABLE_2026'

# --- CONFIGURACIÓN DE RUTAS DE BASE DE DATOS ---
# Esto asegura que Render pueda escribir los archivos .db sin errores de permisos
DB_FOLDER = os.getcwd()

def query_db(db_name, query, params=(), fetch=False):
    db_path = os.path.join(DB_FOLDER, db_name)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        # Si hay error, lo lanzamos para que Flask lo atrape y lo veamos
        raise Exception(f"Error en BD {db_name}: {str(e)}")

def init_db():
    query_db('master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT, vencimiento TEXT)''')
    query_db('master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ADMIN-01", "CONTROL CENTRAL", "Administrador", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def db_negocio(u):
    db = f"negocio_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"negocio_{u['clave']}.db"
    # Aseguramos todas las tablas con sus columnas exactas
    query_db(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    
    # Inicialización forzada de configuración
    conf = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)
    if not conf:
        query_db(db, "INSERT INTO config (id, empresa, whatsapp) VALUES (1, 'Mi Negocio', '52')")
    return db

# --- ESTILO ---
CSS = '''<style>
    body { background: #0f172a; color: white; font-family: sans-serif; display: flex; justify-content: center; padding: 20px; }
    .card { background: rgba(30, 41, 59, 0.8); padding: 25px; border-radius: 20px; width: 100%; max-width: 400px; border: 1px solid rgba(255,255,255,0.1); }
    h2 { color: #22d3ee; margin-top: 0; }
    input, select { background: #1e293b; border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: #6366f1; color: white; border: none; padding: 14px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; }
    .nav { display: block; text-decoration: none; color: #94a3b8; padding: 10px; text-align: center; margin-top: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; }
</style>'''

# --- RUTAS ---
@app.route('/')
def index():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave" required><button>ENTRAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if res:
        session['clv'] = res[0]['clave']
        return redirect('/hub')
    return redirect('/')

@app.route('/hub')
def hub():
    try:
        if 'clv' not in session: return redirect('/')
        u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
        db = db_negocio(u)
        c = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
        
        html = f'{CSS}<div class="card"><h2>{c["empresa"]}</h2>'
        if u['rango'] == 'Administrador':
            html += '<a href="/admin" class="nav">💎 Clientes</a>'
        else:
            html += '<a href="/pos" class="nav">🛒 Punto de Venta</a>'
            html += '<a href="/stk" class="nav">📦 Stock</a>'
            if u['rango'] == 'Dueño':
                html += '<a href="/cfg" class="nav">⚙️ Configuración</a>'
                html += '<a href="/end" class="nav" style="color:#22d3ee">🏁 Corte de Caja</a>'
        html += '<a href="/" class="nav" style="color:#f43f5e">Salir</a></div>'
        return html
    except Exception as e:
        return f"Error en HUB: {str(e)}"

@app.route('/cfg', methods=['GET', 'POST'])
def cfg():
    try:
        u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
        db = db_negocio(u)
        if request.method == 'POST':
            query_db(db, "UPDATE config SET empresa=?, whatsapp=? WHERE id=1", (request.form['e'], request.form['w']))
            return redirect('/hub')
        c = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
        return f'{CSS}<div class="card"><h2>Ajustes</h2><form method="POST"><input name="e" value="{c["empresa"]}"><input name="w" value="{c["whatsapp"]}"><button>Guardar</button></form><a href="/hub" class="nav">Volver</a></div>'
    except Exception as e:
        return f"Error en CFG: {str(e)}"

@app.route('/end')
def end():
    try:
        u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
        db = db_negocio(u)
        v = query_db(db, "SELECT SUM(total) as t FROM ventas", fetch=True)[0]['t'] or 0
        g = query_db(db, "SELECT SUM(monto) as t FROM gastos", fetch=True)[0]['t'] or 0
        return f'''{CSS}<div class="card"><h2>Corte</h2><p>Ventas: ${v}</p><p>Gastos: ${g}</p><h3>Neto: ${v-g}</h3>
        <form action="/do_end" method="POST"><button style="background:#f43f5e">Cerrar Caja</button></form>
        <a href="/hub" class="nav">Volver</a></div>'''
    except Exception as e:
        return f"Error en END: {str(e)}"

@app.route('/do_end', methods=['POST'])
def do_end():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    query_db(db, "DELETE FROM ventas"); query_db(db, "DELETE FROM gastos")
    return redirect('/hub')

# Rutas de POS y Stock simplificadas para evitar errores
@app.route('/pos')
def pos():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    ps = query_db(db, "SELECT * FROM productos WHERE stock > 0", fetch=True)
    ops = "".join([f'<option value="{p["codigo"]}">{p["nombre"]} (${p["precio"]})</option>' for p in ps])
    return f'{CSS}<div class="card"><h2>Venta</h2><form action="/add" method="POST"><select name="i">{ops}</select><input name="v" type="number" step="0.01" placeholder="Monto o Cantidad"><button>Añadir</button></form><a href="/hub" class="nav">Volver</a></div>'

@app.route('/add', methods=['POST'])
def add():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    p = query_db(db, "SELECT * FROM productos WHERE codigo=?", (request.form['i'],), True)[0]
    v = float(request.form['v'] or 0)
    # Lógica Kilos (Dinero) vs Piezas (Cantidad)
    cant = round(v / p['precio'], 3) if p['unidad'] == 'Kg' else v
    sub = v if p['unidad'] == 'Kg' else round(v * p['precio'], 2)
    query_db(db, "UPDATE productos SET stock=stock-? WHERE codigo=?", (cant, p['codigo']))
    query_db(db, "INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (sub, datetime.now().strftime("%H:%M"), u['nombre']))
    return redirect('/pos')

@app.route('/stk')
def stk():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    ps = query_db(db, "SELECT * FROM productos", fetch=True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>{p['stock']} {p['unidad']}</td></tr>" for p in ps])
    return f'''{CSS}<div class="card"><h2>Stock</h2><table>{filas}</table><hr>
    <form action="/p_up" method="POST"><input name="c" placeholder="Cod"><input name="n" placeholder="Nom"><input name="p" placeholder="Precio"><input name="s" placeholder="Stock">
    <select name="u"><option value="Pza">Pieza</option><option value="Kg">Kilo</option></select><button>Guardar</button></form><a href="/hub" class="nav">Volver</a></div>'''

@app.route('/p_up', methods=['POST'])
def p_up():
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    query_db(db, "INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['c'], request.form['n'], request.form['p'], request.form['s'], request.form['u']))
    return redirect('/stk')

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
    
