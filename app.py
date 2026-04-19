import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import os
from flask import Flask, request, render_template_string, redirect

app = Flask(__name__)

# --- TUS FUNCIONES DE BASE DE DATOS (IDÉNTICAS) ---
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

def iniciar_db_usuarios():
    conn = sqlite3.connect('usuarios_sistema.db')
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT)''')
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?, ?, ?, ?, ?)", 
                     ("ADM-K97B", "ADMIN PRINCIPAL", "Administrador", "SISTEMA", "Activo"))
    return conn

# --- ESTILO VISUAL CONSOLA ---
CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 650px; margin: auto; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 8px 0; font-size: 1.1em; }
    .opcion:hover { background: #0f0; color: #000; }
    input, select { background: #000; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 100%; margin: 5px 0; }
    button { background: #0f0; color: #000; border: none; padding: 10px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
    hr { border: 0; border-top: 1px dashed #0f0; margin: 15px 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { border: 1px solid #0f0; padding: 5px; text-align: left; }
</style>
'''

@app.route('/')
def login_screen():
    return f'''{CSS}
    <div class="menu-box">
        <p>===================================</p>
        <p>🔑 INICIO DE SESIÓN</p>
        <p>===================================</p>
        <form action="/auth" method="post">
            <label>Clave de acceso:</label>
            <input type="text" name="clave" autofocus required>
            <button type="submit">ENTRAR</button>
        </form>
    </div>'''

@app.route('/auth', methods=['POST'])
def auth():
    clave = request.form.get('clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        if user['estado'] == "Suspendido":
            return f"{CSS}<div class='menu-box'>🚫 SERVICIO SUSPENDIDO. <a href='/' style='color:#0f0'>Volver</a></div>"
        
        db_nombre = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db = iniciar_db(db_nombre)
        conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu_html = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>Usuario: {user['nombre']} | Rango: {user['rango']}</p><hr>"

        if user['rango'] == 'Administrador':
            menu_html += f'''
                <a class="opcion" href="/usuarios/{clave}">1. GESTIONAR DUEÑOS (TABLA)</a>
                <a class="opcion" href="/">2. SALIR</a>'''
        elif user['rango'] == 'Dueño':
            menu_html += f'''
                <a class="opcion" href="/venta/{clave}">1. REALIZAR VENTA</a>
                <a class="opcion" href="/inventario/{clave}">2. INVENTARIO (EDITAR/VER)</a>
                <a class="opcion" href="/usuarios/{clave}">3. GESTIONAR MIS TRABAJADORES</a>
                <a class="opcion" href="/pago_proveedor/{clave}">4. PAGAR A PROVEEDOR</a>
                <a class="opcion" href="/config/{clave}">5. CONFIGURAR NEGOCIO</a>
                <a class="opcion" href="/corte/{clave}">6. ENVIAR CORTE DE CAJA</a>
                <a class="opcion" href="/">7. SALIR</a>'''
        elif user['rango'] == 'Trabajador':
            menu_html += f'''
                <a class="opcion" href="/venta/{clave}">1. REALIZAR VENTA</a>
                <a class="opcion" href="/inventario/{clave}">2. VER STOCK (SÓLO LECTURA)</a>
                <a class="opcion" href="/pago_proveedor/{clave}">3. PAGAR A PROVEEDOR</a>
                <a class="opcion" href="/">4. SALIR</a>'''
        
        menu_html += "</div>"
        return menu_html
    return f"{CSS}<div class='menu-box'>❌ Clave incorrecta. <a href='/' style='color:#0f0'>Reintentar</a></div>"

# --- TUS FUNCIONES FALTANTES AGREGADAS ---

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    rango_a_gestionar = "Dueño" if user['rango'] == "Administrador" else "Trabajador"
    mi_rama = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
    
    tabla = "<table><tr><th>CLAVE</th><th>NOMBRE</th><th>ESTADO</th></tr>"
    for u in mi_rama:
        tabla += f"<tr><td>{u['clave']}</td><td>{u['nombre']}</td><td>{u['estado']}</td></tr>"
    tabla += "</table>"

    return f'''{CSS}
    <div class="menu-box">
        <h3>--- PANEL DE GESTIÓN: {rango_a_gestionar.upper()}S ---</h3>
        {tabla}
        <hr>
        <form action="/add_user" method="post">
            <input type="hidden" name="admin_clave" value="{clave}">
            <input type="hidden" name="rango" value="{rango_a_gestionar}">
            <input name="nombre" placeholder="Nombre del {rango_a_gestionar}" required>
            <button type="submit">REGISTRAR {rango_a_gestionar.upper()}</button>
        </form>
        <a class="opcion" href="javascript:history.back()">[ Volver ]</a>
    </div>'''

@app.route('/add_user', methods=['POST'])
def add_user():
    admin_clave = request.form.get('admin_clave')
    nom = request.form.get('nombre')
    rango = request.form.get('rango')
    sufijo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    nueva_c = f"{nom[:3].upper()}-{sufijo}"
    db_u = iniciar_db_usuarios()
    with db_u:
        db_u.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)",
                     (nueva_c, nom, rango, admin_clave, "Activo"))
    return f"{CSS}<div class='menu-box'>✅ Registrado: {nueva_c}<br><form action='/auth' method='post'><input type='hidden' name='clave' value='{admin_clave}'><button type='submit'>VOLVER</button></form></div>"

@app.route('/config/<clave>')
def config(clave):
    db = iniciar_db(f"tienda_{clave}.db")
    c = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    return f'''{CSS}
    <div class="menu-box">
        <h3>⚙️ CONFIGURACIÓN</h3>
        <form action="/update_config" method="post">
            <input type="hidden" name="clave" value="{clave}">
            <label>Nombre del Negocio:</label>
            <input name="nn" value="{c['nombre_negocio']}">
            <label>Teléfono Dueño:</label>
            <input name="nt" value="{c['telefono_dueno']}">
            <button type="submit">ACTUALIZAR</button>
        </form>
        <a class="opcion" href="javascript:history.back()">[ Volver ]</a>
    </div>'''

@app.route('/update_config', methods=['POST'])
def update_config():
    clave = request.form.get('clave')
    nn, nt = request.form.get('nn'), request.form.get('nt')
    db = iniciar_db(f"tienda_{clave}.db")
    with db:
        db.execute("UPDATE configuracion SET nombre_negocio=?, telefono_dueno=? WHERE id=1", (nn, nt))
    return f"{CSS}<div class='menu-box'>✅ Actualizado.<form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit'>VOLVER</button></form></div>"

# --- MANTENEMOS LAS DEMÁS RUTAS (VENTA, INVENTARIO) ---
@app.route('/inventario/<clave>')
def inventario(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db_nombre = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
    db = iniciar_db(db_nombre)
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>COD</th><th>NOM</th><th>PRE</th><th>STK</th></tr>"
    for p in prods:
        tabla += f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>"
    tabla += "</table>"
    return f"{CSS}<div class='menu-box'><h3>📦 INVENTARIO</h3>{tabla}<hr><a class='opcion' href='javascript:history.back()'>[ Volver ]</a></div>"

@app.route('/venta/<clave>')
def venta(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db_nombre = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
    db = iniciar_db(db_nombre)
    prods = db.execute("SELECT * FROM productos WHERE stock > 0").fetchall()
    opciones = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    return f'''{CSS}
    <div class="menu-box">
        <h3>🛒 VENTA</h3>
        <form action="/procesar_venta" method="post">
            <input type="hidden" name="clave" value="{clave}">
            <select name="codigo">{opciones}</select>
            <input type="number" step="0.1" name="cant" placeholder="Cantidad/Dinero" required>
            <button type="submit">VENDER</button>
        </form>
        <a class="opcion" href="javascript:history.back()">[ Volver ]</a>
    </div>'''

@app.route('/procesar_venta', methods=['POST'])
def procesar_venta():
    clave = request.form.get('clave')
    cod, cant = request.form.get('codigo'), float(request.form.get('cant'))
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    p = db.execute("SELECT * FROM productos WHERE codigo = ?", (cod,)).fetchone()
    if p:
        total = p['precio'] * cant if p['unidad'] == 'p' else cant
        desc = cant if p['unidad'] == 'p' else cant / p['precio']
        with db:
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (desc, cod))
            db.execute("INSERT INTO ventas (total, pago, cambio, fecha, vendedor) VALUES (?,?,?,?,?)", (total, total, 0, datetime.now().strftime("%Y-%m-%d %H:%M"), user['nombre']))
    return f"{CSS}<div class='menu-box'>✅ Venta procesada.<form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit'>CONTINUAR</button></form></div>"

if __name__ == "__main__":
    iniciar_db_usuarios()
    iniciar_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
