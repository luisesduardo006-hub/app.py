import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import os
from flask import Flask, request, render_template_string, redirect, url_for

app = Flask(__name__)

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def iniciar_db(nombre_db='punto_venta_v4.db'):
    conn = sqlite3.connect(nombre_db)
    conn.row_factory = sqlite3.Row 
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS productos 
                     (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, 
                      stock REAL, min_compra REAL, unidad TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ventas 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, 
                      pago REAL, cambio REAL, fecha TEXT, vendedor TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS gastos 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, 
                      monto REAL, fecha TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS configuracion 
                     (id INTEGER PRIMARY KEY, nombre_negocio TEXT, direccion TEXT, 
                      min_compra REAL, porc_desc REAL, telefono_dueno TEXT)''')
        
        res = conn.execute("SELECT COUNT(*) FROM configuracion").fetchone()
        if res[0] == 0:
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, direccion, min_compra, porc_desc, telefono_dueno) VALUES (1, 'MI TIENDITA PRO', 'Direccion General', 0, 0, '')")
    return conn

def iniciar_db_usuarios(nombre_db='usuarios_sistema.db'):
    conn = sqlite3.connect(nombre_db)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT)''')
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?, ?, ?, ?, ?)", 
                     ("ADM-K97B", "ADMIN PRINCIPAL", "Administrador", "SISTEMA", "Activo"))
    return conn

# --- ESTILOS VISUALES ---
CSS = '''
<style>
    body { font-family: sans-serif; background: #121212; color: white; text-align: center; padding: 20px; }
    .card { background: #1e1e1e; padding: 20px; border-radius: 10px; border: 1px solid #333; max-width: 500px; margin: auto; }
    input, select { display: block; width: 90%; margin: 10px auto; padding: 10px; background: #2b2b2b; color: white; border: 1px solid #444; }
    .btn { display: inline-block; padding: 10px 20px; background: #00a8ff; color: white; text-decoration: none; border-radius: 5px; border: none; cursor: pointer; margin: 5px; }
    .btn-red { background: #ff4757; }
    table { width: 100%; margin-top: 20px; border-collapse: collapse; }
    th, td { border: 1px solid #333; padding: 10px; }
</style>
'''

# --- RUTAS ---

@app.route('/')
def index():
    return f'''{CSS}
    <div class="card">
        <h2>🔑 Acceso al Sistema</h2>
        <form action="/login" method="post">
            <input type="text" name="clave" placeholder="Introduce tu clave" required>
            <button type="submit" class="btn">Entrar</button>
        </form>
    </div>'''

@app.route('/login', methods=['POST'])
def login():
    clave = request.form['clave']
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    if user:
        if user['estado'] == "Suspendido": return "<h1>🚫 Usuario Suspendido</h1>"
        return f'''{CSS}
        <div class="card">
            <h1>🏪 {user['nombre']}</h1>
            <p>Rango: {user['rango']}</p>
            <hr>
            <a href="/inventario" class="btn">📦 Inventario</a>
            <a href="/venta" class="btn">🛒 Venta</a>
            <a href="/usuarios/{user['clave']}" class="btn">👥 Usuarios</a>
            <a href="/" class="btn btn-red">Cerrar Sesión</a>
        </div>'''
    return "<h1>❌ Clave Incorrecta</h1><a href='/'>Volver</a>"

@app.route('/inventario')
def inventario():
    db = iniciar_db()
    prods = db.execute("SELECT * FROM productos").fetchall()
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>" for p in prods])
    return f'''{CSS}
    <div class="card" style="max-width: 800px;">
        <h2>📦 Inventario Actual</h2>
        <table><tr><th>Nombre</th><th>Precio</th><th>Stock</th></tr>{filas}</table>
        <hr>
        <h3>Agregar Producto</h3>
        <form action="/add_prod" method="post">
            <input type="text" name="cod" placeholder="Código" required>
            <input type="text" name="nom" placeholder="Nombre" required>
            <input type="number" step="0.01" name="pre" placeholder="Precio" required>
            <input type="number" step="0.01" name="sto" placeholder="Stock" required>
            <select name="uni"><option value="p">Pieza</option><option value="k">Kilo</option></select>
            <button type="submit" class="btn">Guardar</button>
        </form>
        <a href="/" class="btn btn-red">Volver</a>
    </div>'''

@app.route('/add_prod', methods=['POST'])
def add_prod():
    db = iniciar_db()
    with db:
        db.execute("INSERT OR REPLACE INTO productos (codigo, nombre, precio, stock, min_compra, unidad) VALUES (?,?,?,?,?,?)",
                   (request.form['cod'], request.form['nom'], request.form['pre'], request.form['sto'], 0, request.form['uni']))
    return redirect(url_for('inventario'))

@app.route('/usuarios/<creador>')
def usuarios(creador):
    db_u = iniciar_db_usuarios()
    users = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (creador,)).fetchall()
    filas = "".join([f"<tr><td>{u['nombre']}</td><td>{u['clave']}</td><td>{u['estado']}</td></tr>" for u in users])
    return f'''{CSS}
    <div class="card">
        <h2>👥 Gestión de Personal</h2>
        <table><tr><th>Nombre</th><th>Clave</th><th>Estado</th></tr>{filas}</table>
        <form action="/add_user" method="post">
            <input type="hidden" name="creador" value="{creador}">
            <input type="text" name="nom" placeholder="Nombre del trabajador" required>
            <button type="submit" class="btn">Crear Nuevo Trabajador</button>
        </form>
        <a href="/" class="btn btn-red">Volver</a>
    </div>'''

@app.route('/add_user', methods=['POST'])
def add_user():
    db_u = iniciar_db_usuarios()
    nom = request.form['nom']
    sufijo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    nueva_c = f"{nom[:3].upper()}-{sufijo}"
    with db_u:
        db_u.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)",
                     (nueva_c, nom, "Trabajador", request.form['creador'], "Activo"))
    return redirect(url_for('usuarios', creador=request.form['creador']))

@app.route('/venta')
def venta():
    db = iniciar_db()
    prods = db.execute("SELECT * FROM productos").fetchall()
    # Interfaz simple de venta
    return f'''{CSS}
    <div class="card">
        <h2>🛒 Nueva Venta</h2>
        <p>Selecciona un producto y presiona vender (Stock se descuenta automáticamente)</p>
        <form action="/procesar_venta" method="post">
            <select name="codigo">
                {"".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])}
            </select>
            <input type="number" name="cantidad" value="1" step="0.1">
            <button type="submit" class="btn">Realizar Venta</button>
        </form>
        <a href="/" class="btn btn-red">Volver</a>
    </div>'''

@app.route('/procesar_venta', methods=['POST'])
def procesar_venta():
    db = iniciar_db()
    cod = request.form['codigo']
    cant = float(request.form['cantidad'])
    p = db.execute("SELECT * FROM productos WHERE codigo = ?", (cod,)).fetchone()
    if p and p['stock'] >= cant:
        total = p['precio'] * cant
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        with db:
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (cant, cod))
            db.execute("INSERT INTO ventas (total, pago, cambio, fecha, vendedor) VALUES (?,?,?,?,?)",
                       (total, total, 0, fecha, "WEB"))
        return f"<h1>✅ Venta Exitosa: ${total}</h1><a href='/venta' class='btn'>Otra venta</a>"
    return "<h1>❌ Stock insuficiente</h1><a href='/venta'>Volver</a>"

if __name__ == "__main__":
    iniciar_db_usuarios()
    iniciar_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
